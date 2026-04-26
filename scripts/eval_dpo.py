"""
ShramikSaathi — Stage 2.3: DPO Held-out Evaluation

Runs the 20 Stage 1.3 held-out prompts against four systems:
  1. SFT-only LoRA                (baseline — existing Stage 1 adapter)
  2. SFT + DPO beta=0.05
  3. SFT + DPO beta=0.10
  4. SFT + DPO beta=0.20

Uses Option A (fixed passages per prompt) — isolates generator quality.

Decision rule:
  - Winner = adapter with highest grounded_clean score
  - If NO DPO adapter beats SFT-only on grounded_clean → keep SFT-only

Outputs:
  data/dpo_eval_results.json
  data/dpo_eval_report.md

Run from project root:
    python scripts/eval_dpo.py
"""

import os
import re
import json
import time
from pathlib import Path
from collections import defaultdict

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
EVAL_PATH   = ROOT / "data" / "eval_heldout.jsonl"
KB_PATH     = ROOT / "data" / "kb.jsonl"
SFT_ADAPTER = ROOT / "out" / "lora_v2"
DPO_ADAPTERS = {
    "dpo_beta_0.05": ROOT / "out" / "dpo_beta_050",
    "dpo_beta_0.10": ROOT / "out" / "dpo_beta_100",
    "dpo_beta_0.20": ROOT / "out" / "dpo_beta_200",
}
OUT_PATH    = ROOT / "data" / "dpo_eval_results.json"
REPORT_PATH = ROOT / "data" / "dpo_eval_report.md"

MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"

# ── Generator prompt (same as Stage 1.3 eval) ─────────────────────────────
GENERATOR_PROMPT = """You are ShramikSaathi, an Indian worker rights support copilot.
You help workers with PF/EPFO, payslip audit, labour rights, and income tax queries.

You will be given:
1. The user's query
2. The detected domain
3. Retrieved KB passages with doc_ids and dates
4. An eligibility reasoning trace (if applicable)
5. Filled slots

Your job: produce a clear, cited, structured answer.

RULES:
- Every factual claim must cite its doc_id in brackets e.g. [GRATUITY_ACT_S4_ELIG]
- CITATION RULE: Only cite doc_ids that appear verbatim in the RETRIEVED PASSAGES section.
  Never invent new doc_ids, suffixes, or section numbers. If a claim needs a citation but no
  passage supports it, omit the citation rather than fabricate one.
- If eligibility reasoning is provided, include the condition trace in your answer
- If decision is ANSWER + eligible=True  → confirm eligibility, give next steps
- If decision is ANSWER + eligible=False → clearly state not eligible, explain why, cite condition
- If decision is ESCALATE → say KB lacks info, suggest appropriate grievance portal
- For informational queries → answer directly from passages with citations
- Keep answers structured: result first, then steps, then warnings/caveats
- Never make up information not in the passages
- Use simple language — the user may not know legal terminology
- For payslip queries: show the calculation (expected vs actual deduction)
- For tax queries: show the applicable slab or formula with numbers
- For labour queries: cite the specific Act and Section number"""

DOC_ID_RE = re.compile(r'\[([A-Z][A-Z0-9_]+)\]')


# ── Helpers ────────────────────────────────────────────────────────────────

def load_kb():
    kb = {}
    with open(KB_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            kb[d["doc_id"]] = d
    return kb


def format_passages(prompt, kb):
    parts = []
    for i, did in enumerate(prompt["passage_doc_ids"]):
        if did == "TOOL_PAYSLIP_AUDIT":
            import sys
            sys.path.insert(0, str(ROOT / "src"))
            from tools import parse_payslip, format_payslip_result
            content = format_payslip_result(parse_payslip(prompt["slots"]))
            parts.append(f"[Source {i+1}] doc_id=TOOL_PAYSLIP_AUDIT | date=None | domain=payslip\n{content}")
        elif did in kb:
            d = kb[did]
            parts.append(
                f"[Source {i+1}] doc_id={did} | date={d.get('effective_date')} | domain={d.get('domain','')}\n{d['content'][:1500]}"
            )
        else:
            parts.append(f"[Source {i+1}] doc_id={did} | date=None | domain=unknown\n[passage unavailable]")
    return "\n\n---\n\n".join(parts)


def build_user_msg(prompt, kb):
    passages_text = format_passages(prompt, kb)
    filled_slots = {k: v for k, v in prompt["slots"].items() if v is not None}
    return f"""USER QUERY:
{prompt["query"]}

DOMAIN: {prompt["domain"]}

RETRIEVED PASSAGES:
{passages_text}



SLOTS FILLED:
{json.dumps(filled_slots, indent=2)}

Produce the final answer now. IMPORTANT: every factual claim must include [DOC_ID] in brackets — no exceptions. If you cannot cite, omit the claim."""


def generate(model, tokenizer, system, user, max_new_tokens=600):
    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=3072).to(model.device)
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=None,
            top_p=None,
            pad_token_id=tokenizer.eos_token_id,
        )
    gen = out[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(gen, skip_special_tokens=True).strip()


def score_response(response, prompt):
    allowed = set(prompt["passage_doc_ids"])
    cited = set(DOC_ID_RE.findall(response))
    fabricated = cited - allowed
    expected_cited = set(prompt["expected_cited_doc_ids"])

    rl = response.lower()
    verdict_map = {
        "eligible":         ["eligible"],
        "not eligible":     ["not eligible", "ineligible"],
        "correct":          ["correct", "matches"],
        "incorrect":        ["incorrect", "under-deducted", "over-deducted", "mismatch", "wrong"],
        "applicable":       ["applicable"],
        "not applicable":   ["not applicable", "not allowed", "cannot claim"],
        "conditional":      ["conditional", "depends", "if"],
        "informational":    ["according to", "as per", "under", "section"],
        "mixed":            ["however", "but", "although"],
    }
    keywords = verdict_map.get(prompt["expected_verdict"], [prompt["expected_verdict"]])
    verdict_ok = any(k in rl for k in keywords)

    kf = prompt.get("key_facts_required", [])
    kf_found = sum(1 for f in kf if f.lower() in rl)
    kf_rate = (kf_found / len(kf)) if kf else None

    return {
        "cited":                   sorted(cited),
        "fabricated":              sorted(fabricated),
        "has_citation":            len(cited) > 0,
        "has_fabrication":         len(fabricated) > 0,
        "cited_expected_subset":   expected_cited.issubset(cited),
        "verdict_present":         verdict_ok,
        "key_facts_found":         kf_found,
        "key_facts_total":         len(kf),
        "key_facts_rate":          kf_rate,
        "grounded_clean":          (len(cited) > 0) and (len(fabricated) == 0) and verdict_ok,
    }


def summarize(results):
    n = len(results)
    return {
        "n":                  n,
        "citation_coverage":  sum(r["has_citation"] for r in results) / n,
        "fabrication_count":  sum(r["has_fabrication"] for r in results),
        "fabrication_rate":   sum(r["has_fabrication"] for r in results) / n,
        "expected_cites_hit": sum(r["cited_expected_subset"] for r in results) / n,
        "verdict_accuracy":   sum(r["verdict_present"] for r in results) / n,
        "grounded_clean":     sum(r["grounded_clean"] for r in results) / n,
        "key_facts_mean":     (sum(r["key_facts_rate"] or 0 for r in results) /
                               max(1, sum(1 for r in results if r["key_facts_rate"] is not None))),
    }


def by_domain(results, prompts):
    buckets = defaultdict(list)
    for r, p in zip(results, prompts):
        buckets[p["domain"]].append(r)
    return {d: summarize(v) for d, v in buckets.items()}


def run_system(label, model, tokenizer, prompts, kb):
    print(f"\n[Run] {label}")
    results = []
    t_start = time.time()
    for i, p in enumerate(prompts, 1):
        user = build_user_msg(p, kb)
        t0 = time.time()
        resp = generate(model, tokenizer, GENERATOR_PROMPT, user)
        dt = time.time() - t0
        scored = score_response(resp, p)
        results.append({"prompt_id": p["id"], "response": resp, **scored})
        print(f"  [{i}/{len(prompts)}] {p['id']}  cites={len(scored['cited'])}  fab={len(scored['fabricated'])}  verdict={scored['verdict_present']}  [{dt:.1f}s]")
    print(f"[Run] {label} total {(time.time()-t_start)/60:.1f}min")
    return results


# ── Load base model once (helper) ─────────────────────────────────────────

def load_base_model(tokenizer):
    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
    )
    print(f"\n[Model] Loading base {MODEL_ID} in 4-bit")
    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, quantization_config=bnb, torch_dtype=torch.bfloat16,
        device_map="auto", attn_implementation="sdpa",
    )
    model.eval()
    print(f"        Loaded in {time.time()-t0:.1f}s | VRAM {torch.cuda.memory_allocated()/1e9:.2f}GB")
    return model


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    import sys
    sys.path.insert(0, str(ROOT))

    print("=" * 70)
    print("Stage 2.3 — DPO Held-out Evaluation")
    print("=" * 70)

    prompts = [json.loads(l) for l in open(EVAL_PATH) if l.strip()]
    kb = load_kb()
    print(f"[Data] {len(prompts)} prompts | {len(kb)} KB docs")

    # Validate
    missing = set()
    for p in prompts:
        for did in p["passage_doc_ids"] + p["expected_cited_doc_ids"]:
            if did != "TOOL_PAYSLIP_AUDIT" and did not in kb:
                missing.add(did)
    if missing:
        print(f"[!] Missing doc_ids: {sorted(missing)}")
        return

    # Tokenizer (shared across all runs)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    all_results = {}

    # ── System 1: SFT-only LoRA ──────────────────────────────────────────
    base_model = load_base_model(tokenizer)
    print(f"\n[Model] Attaching SFT LoRA from {SFT_ADAPTER}")
    sft_model = PeftModel.from_pretrained(base_model, str(SFT_ADAPTER))
    sft_model.eval()
    all_results["sft_only"] = run_system("SFT-only", sft_model, tokenizer, prompts, kb)

    # Cleanup SFT model before DPO runs
    del sft_model
    del base_model
    torch.cuda.empty_cache()

    # ── Systems 2-4: DPO adapters (each loaded fresh on top of base) ─────
    for dpo_label, dpo_path in DPO_ADAPTERS.items():
        print(f"\n[Model] Loading {dpo_label} from {dpo_path}")
        base_model = load_base_model(tokenizer)
        dpo_model = PeftModel.from_pretrained(base_model, str(dpo_path))
        dpo_model.eval()

        all_results[dpo_label] = run_system(dpo_label, dpo_model, tokenizer, prompts, kb)

        del dpo_model
        del base_model
        torch.cuda.empty_cache()

    # ── Summaries ────────────────────────────────────────────────────────
    summaries = {k: summarize(v) for k, v in all_results.items()}
    per_domain = {k: by_domain(v, prompts) for k, v in all_results.items()}

    print(f"\n{'=' * 78}")
    print(f"SUMMARY (n={len(prompts)})")
    print(f"{'=' * 78}")
    header = f"{'Metric':<22}" + "".join(f"{k:>15}" for k in all_results.keys())
    print(header)
    for metric in ["citation_coverage", "fabrication_rate", "expected_cites_hit",
                   "verdict_accuracy", "grounded_clean", "key_facts_mean"]:
        row = f"{metric:<22}"
        for sys_label in all_results.keys():
            row += f"{summaries[sys_label][metric]:>15.3f}"
        print(row)
    # fabrication_count
    row = f"{'fabrication_count':<22}"
    for sys_label in all_results.keys():
        row += f"{summaries[sys_label]['fabrication_count']:>15}"
    print(row)

    # Per-domain grounded_clean
    print(f"\nPer-domain grounded_clean:")
    header = f"{'Domain':<10}" + "".join(f"{k:>15}" for k in all_results.keys())
    print(header)
    for dom in ["pf", "payslip", "labour", "tax"]:
        row = f"{dom:<10}"
        for sys_label in all_results.keys():
            v = per_domain[sys_label].get(dom, {}).get("grounded_clean", 0)
            row += f"{v:>15.2f}"
        print(row)

    # ── Pick winner ──────────────────────────────────────────────────────
    print(f"\n{'=' * 78}")
    print("DECISION")
    print(f"{'=' * 78}")
    sft_score = summaries["sft_only"]["grounded_clean"]
    best_dpo_label = None
    best_dpo_score = -1.0
    for label in DPO_ADAPTERS.keys():
        s = summaries[label]["grounded_clean"]
        if s > best_dpo_score:
            best_dpo_score = s
            best_dpo_label = label

    print(f"SFT-only grounded_clean: {sft_score:.3f}")
    print(f"Best DPO: {best_dpo_label} with {best_dpo_score:.3f}")

    if best_dpo_score > sft_score:
        winner = best_dpo_label
        print(f"\n✓ WINNER: {winner} (beats SFT by {best_dpo_score - sft_score:+.3f})")
        print(f"\n  To push this adapter to HuggingFace, run:")
        print(f"    python scripts/push_dpo_winner.py {winner}")
    elif best_dpo_score == sft_score:
        winner = "sft_only"
        print(f"\n= TIE: DPO did not improve over SFT. Keep SFT-only.")
    else:
        winner = "sft_only"
        print(f"\n✗ SFT-only wins. DPO regressed by {best_dpo_score - sft_score:+.3f}.")
        print(f"  Keep SFT-only. Discard DPO adapters.")

    # ── Save ─────────────────────────────────────────────────────────────
    out = {
        "n_prompts":   len(prompts),
        "winner":      winner,
        "summaries":   summaries,
        "per_domain":  per_domain,
        "all_results": all_results,
        "prompts":     prompts,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n[Save] {OUT_PATH}")

    # ── Markdown report ──────────────────────────────────────────────────
    lines = [
        "# Stage 2.3 — DPO Held-out Evaluation Report\n",
        f"- Prompts: {len(prompts)}",
        f"- Systems: SFT-only + 3 DPO betas (0.05, 0.10, 0.20)",
        f"- Winner: **{winner}**\n",
        "## Summary\n",
        "| Metric | " + " | ".join(all_results.keys()) + " |",
        "|" + "|".join(["---"] * (len(all_results) + 1)) + "|",
    ]
    for metric in ["citation_coverage", "fabrication_rate", "expected_cites_hit",
                   "verdict_accuracy", "grounded_clean", "key_facts_mean"]:
        row = f"| {metric} |"
        for sys_label in all_results.keys():
            row += f" {summaries[sys_label][metric]:.3f} |"
        lines.append(row)
    row = f"| fabrication_count |"
    for sys_label in all_results.keys():
        row += f" {summaries[sys_label]['fabrication_count']} |"
    lines.append(row)
    lines.append("")

    lines.append("## Per-domain grounded_clean\n")
    lines.append("| Domain | " + " | ".join(all_results.keys()) + " |")
    lines.append("|" + "|".join(["---"] * (len(all_results) + 1)) + "|")
    for dom in ["pf", "payslip", "labour", "tax"]:
        row = f"| {dom} |"
        for sys_label in all_results.keys():
            v = per_domain[sys_label].get(dom, {}).get("grounded_clean", 0)
            row += f" {v:.2f} |"
        lines.append(row)
    lines.append("")

    lines.append("## Side-by-side samples\n")
    for p in prompts:
        lines.append(f"### {p['id']} — {p['domain']}/{p['intent']}")
        lines.append(f"**Query:** {p['query']}\n")
        lines.append(f"**Expected verdict:** {p['expected_verdict']}")
        lines.append(f"**Expected cites:** {p['expected_cited_doc_ids']}\n")
        for sys_label in all_results.keys():
            r = next(x for x in all_results[sys_label] if x["prompt_id"] == p["id"])
            lines.append(f"#### {sys_label}  cites={r['cited']}  fab={r['fabricated']}  verdict={r['verdict_present']}")
            lines.append("```")
            lines.append(r["response"])
            lines.append("```\n")

    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(lines))
    print(f"[Save] {REPORT_PATH}")

    print(f"\n{'=' * 78}")
    print(f"Stage 2.3 complete. Winner: {winner}")
    print(f"{'=' * 78}")


if __name__ == "__main__":
    main()
