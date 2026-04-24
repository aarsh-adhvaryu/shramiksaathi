"""
ShramikSaathi — Stage 1.3: Held-out eval (Option A, fixed passages).

Compares BASE LLaMA 3.1 8B vs LLaMA + LoRA on 20 hand-written prompts.
Each prompt supplies its own passages (Option A — isolates the generator).

Metrics per system (over 20 prompts):
    - Citation coverage    : fraction with >=1 valid citation
    - Fabrication count    : responses containing [DOC_ID] NOT in passages
    - Verdict correctness  : expected verdict keyword present (substring)
    - Key facts coverage   : fraction of key_facts_required found in response
    - Grounded answer rate : (cited AND no fabrication AND verdict present)

Run from project root on Lightning:
    python scripts/run_heldout_eval.py
"""

import os
import re
import json
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel


# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
EVAL_PATH = ROOT / "data" / "eval_heldout.jsonl"
KB_PATH = ROOT / "data" / "kb.jsonl"
ADAPTER_DIR = ROOT / "out" / "lora_v2"
OUT_PATH = ROOT / "data" / "eval_heldout_results.json"
REPORT_PATH = ROOT / "data" / "eval_heldout_report.md"

MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"

# ── Verbatim copy of generator system prompt from src/pipeline.py ─────────
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

DOC_ID_RE = re.compile(r"\[([A-Z][A-Z0-9_]+)\]")


def load_kb_content():
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
            from src.tools import parse_payslip, format_payslip_result

            payslip_result = parse_payslip(prompt["slots"])
            content = format_payslip_result(payslip_result)
            parts.append(
                f"[Source {i+1}] doc_id=TOOL_PAYSLIP_AUDIT | date=None | domain=payslip\n{content}"
            )
        elif did in kb:
            d = kb[did]
            parts.append(
                f"[Source {i+1}] doc_id={did} | date={d.get('effective_date')} | domain={d.get('domain','')}\n{d['content'][:1500]}"
            )
        else:
            parts.append(
                f"[Source {i+1}] doc_id={did} | date=None | domain=unknown\n[passage unavailable]"
            )
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
        {"role": "user", "content": user},
    ]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=3072).to(
        model.device
    )
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=None,
            top_p=None,
            pad_token_id=tokenizer.eos_token_id,
        )
    gen = out[0][inputs["input_ids"].shape[1] :]
    return tokenizer.decode(gen, skip_special_tokens=True).strip()


def score_response(response, prompt):
    allowed = set(prompt["passage_doc_ids"])
    cited = set(DOC_ID_RE.findall(response))
    fabricated = cited - allowed
    expected_cited = set(prompt["expected_cited_doc_ids"])

    rl = response.lower()

    # verdict keyword match
    verdict_map = {
        "eligible": ["eligible"],
        "not eligible": ["not eligible", "ineligible"],
        "correct": ["correct", "matches"],
        "incorrect": [
            "incorrect",
            "under-deducted",
            "over-deducted",
            "mismatch",
            "wrong",
        ],
        "applicable": ["applicable"],
        "not applicable": ["not applicable", "not allowed", "cannot claim"],
        "conditional": ["conditional", "depends", "if"],
        "informational": ["according to", "as per", "under", "section"],
        "mixed": ["however", "but", "although"],
    }
    keywords = verdict_map.get(prompt["expected_verdict"], [prompt["expected_verdict"]])
    verdict_ok = any(k in rl for k in keywords)

    # key facts
    kf = prompt.get("key_facts_required", [])
    kf_found = sum(1 for f in kf if f.lower() in rl)
    kf_rate = (kf_found / len(kf)) if kf else None

    return {
        "cited": sorted(cited),
        "fabricated": sorted(fabricated),
        "has_citation": len(cited) > 0,
        "has_fabrication": len(fabricated) > 0,
        "cited_expected_subset": expected_cited.issubset(cited),
        "verdict_present": verdict_ok,
        "key_facts_found": kf_found,
        "key_facts_total": len(kf),
        "key_facts_rate": kf_rate,
        "grounded_clean": (len(cited) > 0) and (len(fabricated) == 0) and verdict_ok,
    }


def aggregate(rows, key):
    """rows is a list of {"prompt": ..., "base": {...}, "lora": {...}}."""
    n = len(rows)
    vals = [r[key] for r in rows]
    bools = [v for v in vals if isinstance(v, bool)]
    nums = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if bools and len(bools) == n:
        return sum(bools) / n
    if nums:
        return sum(nums) / len(nums)
    return None


def summarize(results_system):
    n = len(results_system)
    return {
        "n": n,
        "citation_coverage": sum(r["has_citation"] for r in results_system) / n,
        "fabrication_count": sum(r["has_fabrication"] for r in results_system),
        "fabrication_rate": sum(r["has_fabrication"] for r in results_system) / n,
        "expected_cites_hit": sum(r["cited_expected_subset"] for r in results_system)
        / n,
        "verdict_accuracy": sum(r["verdict_present"] for r in results_system) / n,
        "grounded_clean": sum(r["grounded_clean"] for r in results_system) / n,
        "key_facts_mean": (
            sum(r["key_facts_rate"] or 0 for r in results_system)
            / max(1, sum(1 for r in results_system if r["key_facts_rate"] is not None))
        ),
    }


def main():
    import sys

    sys.path.insert(0, str(ROOT))
    print("=" * 70)
    print("Stage 1.3 — Held-out eval (Option A)")
    print("=" * 70)

    prompts = [json.loads(l) for l in open(EVAL_PATH) if l.strip()]
    print(f"[Eval] {len(prompts)} prompts")

    kb = load_kb_content()
    print(f"[KB]   {len(kb)} docs")

    # Validate doc_ids
    missing = set()
    for p in prompts:
        for did in p["passage_doc_ids"] + p["expected_cited_doc_ids"]:
            if did != "TOOL_PAYSLIP_AUDIT" and did not in kb:
                missing.add(did)
    if missing:
        print(f"[!] Missing doc_ids: {sorted(missing)}")
        print("    These prompts will score poorly. Fix and rerun.")
        return

    # Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Base model
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    print(f"\n[Model] Loading base {MODEL_ID} in 4-bit")
    t0 = time.time()
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        attn_implementation="sdpa",
    )
    base_model.eval()
    print(
        f"        Loaded in {time.time()-t0:.1f}s | VRAM {torch.cuda.memory_allocated()/1e9:.2f}GB"
    )

    # Run BASE
    print(f"\n[Run]   Generating BASE responses...")
    base_results = []
    for i, p in enumerate(prompts, 1):
        user = build_user_msg(p, kb)
        t0 = time.time()
        resp = generate(base_model, tokenizer, GENERATOR_PROMPT, user)
        dt = time.time() - t0
        scored = score_response(resp, p)
        base_results.append({"prompt_id": p["id"], "response": resp, **scored})
        print(
            f"  [{i}/{len(prompts)}] {p['id']}  cites={len(scored['cited'])}  fab={len(scored['fabricated'])}  verdict={scored['verdict_present']}  [{dt:.1f}s]"
        )

    # Attach LoRA
    print(f"\n[Model] Attaching LoRA from {ADAPTER_DIR}")
    lora_model = PeftModel.from_pretrained(base_model, str(ADAPTER_DIR))
    lora_model.eval()

    # Run LoRA
    print(f"\n[Run]   Generating LoRA responses...")
    lora_results = []
    for i, p in enumerate(prompts, 1):
        user = build_user_msg(p, kb)
        t0 = time.time()
        resp = generate(lora_model, tokenizer, GENERATOR_PROMPT, user)
        dt = time.time() - t0
        scored = score_response(resp, p)
        lora_results.append({"prompt_id": p["id"], "response": resp, **scored})
        print(
            f"  [{i}/{len(prompts)}] {p['id']}  cites={len(scored['cited'])}  fab={len(scored['fabricated'])}  verdict={scored['verdict_present']}  [{dt:.1f}s]"
        )

    # Summaries
    base_summary = summarize(base_results)
    lora_summary = summarize(lora_results)

    print(f"\n{'=' * 70}")
    print(f"SUMMARY (n={len(prompts)})")
    print(f"{'=' * 70}")
    print(f"{'Metric':<30} {'BASE':>12} {'LoRA':>12} {'Δ':>10}")
    for k in [
        "citation_coverage",
        "fabrication_rate",
        "expected_cites_hit",
        "verdict_accuracy",
        "grounded_clean",
        "key_facts_mean",
    ]:
        b, l = base_summary[k], lora_summary[k]
        delta = l - b
        print(f"{k:<30} {b:>12.3f} {l:>12.3f} {delta:>+10.3f}")
    print(
        f"{'fabrication_count':<30} {base_summary['fabrication_count']:>12} {lora_summary['fabrication_count']:>12}"
    )

    # Per-domain breakdown
    def by_domain(results, prompts):
        from collections import defaultdict

        buckets = defaultdict(list)
        for r, p in zip(results, prompts):
            buckets[p["domain"]].append(r)
        return {d: summarize(v) for d, v in buckets.items()}

    base_by_dom = by_domain(base_results, prompts)
    lora_by_dom = by_domain(lora_results, prompts)

    print(f"\nPer-domain grounded_clean:")
    for dom in ["pf", "payslip", "labour", "tax"]:
        b = base_by_dom.get(dom, {}).get("grounded_clean", 0)
        l = lora_by_dom.get(dom, {}).get("grounded_clean", 0)
        print(f"  {dom:<10}  BASE {b:.2f}  LoRA {l:.2f}  Δ{l-b:+.2f}")

    # Save full results
    out = {
        "n_prompts": len(prompts),
        "base_summary": base_summary,
        "lora_summary": lora_summary,
        "per_domain_base": base_by_dom,
        "per_domain_lora": lora_by_dom,
        "base_results": base_results,
        "lora_results": lora_results,
        "prompts": prompts,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n[Save] Full results: {OUT_PATH}")

    # Markdown report
    lines = [
        "# Stage 1.3 Held-out Eval Report\n",
        f"- Prompts: {len(prompts)}",
        f"- Adapter: `{ADAPTER_DIR}`\n",
        "## Summary\n",
        "| Metric | BASE | LoRA | Δ |",
        "|---|---:|---:|---:|",
    ]
    for k in [
        "citation_coverage",
        "fabrication_rate",
        "expected_cites_hit",
        "verdict_accuracy",
        "grounded_clean",
        "key_facts_mean",
    ]:
        b, l = base_summary[k], lora_summary[k]
        lines.append(f"| {k} | {b:.3f} | {l:.3f} | {l-b:+.3f} |")
    lines.append(
        f"| fabrication_count | {base_summary['fabrication_count']} | {lora_summary['fabrication_count']} | — |\n"
    )

    lines.append("## Per-domain grounded_clean\n")
    lines.append("| Domain | BASE | LoRA | Δ |")
    lines.append("|---|---:|---:|---:|")
    for dom in ["pf", "payslip", "labour", "tax"]:
        b = base_by_dom.get(dom, {}).get("grounded_clean", 0)
        l = lora_by_dom.get(dom, {}).get("grounded_clean", 0)
        lines.append(f"| {dom} | {b:.2f} | {l:.2f} | {l-b:+.2f} |")
    lines.append("")

    lines.append("## Side-by-side (per prompt)\n")
    for p, b, l in zip(prompts, base_results, lora_results):
        lines.append(f"### {p['id']} — {p['domain']}/{p['intent']}")
        lines.append(f"**Query:** {p['query']}")
        lines.append(
            f"**Expected verdict:** {p['expected_verdict']}  |  **Expected cites:** {p['expected_cited_doc_ids']}\n"
        )
        lines.append(
            f"#### BASE  cites={b['cited']}  fab={b['fabricated']}  verdict={b['verdict_present']}"
        )
        lines.append("```\n" + b["response"] + "\n```")
        lines.append(
            f"#### LoRA  cites={l['cited']}  fab={l['fabricated']}  verdict={l['verdict_present']}"
        )
        lines.append("```\n" + l["response"] + "\n```\n")
    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(lines))
    print(f"[Save] Report: {REPORT_PATH}")

    print(f"\n{'=' * 70}")
    print("Stage 1.3 complete.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
