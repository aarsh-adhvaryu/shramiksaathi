"""
ShramikSaathi — 4-Config System-Level Ablation

Runs 20 held-out prompts through 4 system configurations:
  A — Vanilla RAG:      BM25 retrieval + raw LLaMA base
  B — + Pre-retrieval:   FAISS retrieval (domain-aware) + raw LLaMA base
  C — + Reasoner:        B + eligibility reasoner + raw LLaMA base
  D — Full ShramikSaathi: C + DPO generator (beta=0.05)

Metrics per config: citation_coverage, fabrication_rate, verdict_accuracy,
                    grounded_clean, condition_coverage

Run:  python eval/ablation_runner.py 2>&1 | tee data/ablation.log
"""

import os, sys, json, re, time
from pathlib import Path
from collections import defaultdict

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel
from rank_bm25 import BM25Okapi
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from search_kb import SearchKB
from eligibility_reasoner import run_eligibility_reasoner

EVAL_PATH   = ROOT / "data" / "eval_heldout.jsonl"
KB_PATH     = ROOT / "data" / "kb.jsonl"
DPO_ADAPTER = ROOT / "out" / "dpo_beta_050"
OUT_PATH    = ROOT / "data" / "ablation_results.json"

MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"
TOP_K = 5

DOC_ID_RE = re.compile(r'\[([A-Z][A-Z0-9_]+)\]')

REASONING_INTENTS = {
    "full_withdrawal", "partial_withdrawal", "transfer", "tds_query", "kyc_issue",
    "verify_epf", "verify_esi", "check_deductions", "check_minimum_wage", "full_audit",
    "gratuity", "wrongful_termination", "maternity_benefit", "overtime_pay",
    "tds_on_salary", "tds_on_pf", "hra_exemption", "deductions_80c",
}

GENERATOR_PROMPT = """You are ShramikSaathi, an Indian worker rights support copilot.
You help workers with PF/EPFO, payslip audit, labour rights, and income tax queries.

You will be given:
1. The user's query
2. Retrieved KB passages with doc_ids
3. An eligibility reasoning trace (if applicable)

Your job: produce a clear, cited, structured answer.

RULES:
- Every factual claim must cite its doc_id in brackets e.g. [GRATUITY_ACT_S4_ELIG]
- Only cite doc_ids from the RETRIEVED PASSAGES section
- Never invent doc_ids
- Keep answers structured: result first, then steps, then warnings
- Use simple language"""


# ════════════════════════════════════════════════════════════════════════
# DATA
# ════════════════════════════════════════════════════════════════════════

def load_kb():
    kb = {}
    kb_list = []
    with open(KB_PATH) as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                kb[d["doc_id"]] = d
                kb_list.append(d)
    return kb, kb_list


def load_prompts():
    return [json.loads(l) for l in open(EVAL_PATH) if l.strip()]


# ════════════════════════════════════════════════════════════════════════
# RETRIEVAL
# ════════════════════════════════════════════════════════════════════════

class BM25Retriever:
    def __init__(self, kb_list):
        print("[BM25] Building index...")
        self.doc_ids = [d["doc_id"] for d in kb_list]
        self.docs = kb_list
        tokenized = [d["content"].lower().split() for d in kb_list]
        self.bm25 = BM25Okapi(tokenized)

    def search(self, query, top_k=5):
        tokens = query.lower().split()
        scores = self.bm25.get_scores(tokens)
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [self.docs[i] for i in top_idx]


# ════════════════════════════════════════════════════════════════════════
# GENERATION
# ════════════════════════════════════════════════════════════════════════

def format_passages_text(passages):
    parts = []
    for i, p in enumerate(passages):
        did = p.get("doc_id", "?")
        date = p.get("effective_date", "")
        dom = p.get("domain", "")
        text = p.get("content", "")[:1200]
        parts.append(f"[Source {i+1}] doc_id={did} | date={date} | domain={dom}\n{text}")
    return "\n\n---\n\n".join(parts)


def build_prompt_A(query, passages):
    """Vanilla RAG: query + passages only."""
    return f"""USER QUERY:
{query}

RETRIEVED PASSAGES:
{format_passages_text(passages)}

Produce the final answer now. Cite doc_ids in brackets for every claim."""


def build_prompt_B(query, domain, slots, passages):
    """+ Pre-retrieval: includes domain and slots."""
    filled = {k: v for k, v in slots.items() if v is not None}
    return f"""USER QUERY:
{query}

DOMAIN: {domain}

RETRIEVED PASSAGES:
{format_passages_text(passages)}

SLOTS FILLED:
{json.dumps(filled, indent=2)}

Produce the final answer now. Cite doc_ids in brackets for every claim."""


def build_prompt_C(query, domain, slots, passages, reasoning):
    """+ Reasoner: includes reasoning trace."""
    filled = {k: v for k, v in slots.items() if v is not None}
    reasoning_text = ""
    if reasoning:
        lines = ["ELIGIBILITY REASONING TRACE:",
                 f"  Decision: {reasoning.get('decision', '')}"]
        if reasoning.get("eligible") is not None:
            lines.append(f"  Eligible: {reasoning['eligible']}")
        lines.append(f"  Coverage: {reasoning.get('coverage', 0)}")
        for c in reasoning.get("met", []):
            lines.append(f"    ✓ {c.get('field','?')} {c.get('operator','?')} {c.get('value','?')} [{c.get('doc_id','?')}]")
        for c in reasoning.get("failed", []):
            lines.append(f"    ✗ {c.get('field','?')} {c.get('operator','?')} {c.get('value','?')} [{c.get('doc_id','?')}]")
        for c in reasoning.get("warnings", []):
            lines.append(f"    ⚠ {c.get('field','?')} {c.get('operator','?')} {c.get('value','?')} [{c.get('doc_id','?')}]")
        for c in reasoning.get("unresolved", []):
            lines.append(f"    ? {c.get('field','?')} — slot missing")
        reasoning_text = "\n".join(lines)

    return f"""USER QUERY:
{query}

DOMAIN: {domain}

RETRIEVED PASSAGES:
{format_passages_text(passages)}

{reasoning_text}

SLOTS FILLED:
{json.dumps(filled, indent=2)}

Produce the final answer now. Cite doc_ids in brackets for every claim."""


def generate(model, tokenizer, user_content, max_new=600):
    messages = [
        {"role": "system", "content": GENERATOR_PROMPT},
        {"role": "user", "content": user_content},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=3072).to(model.device)
    with torch.no_grad():
        out = model.generate(
            **inputs, max_new_tokens=max_new, do_sample=False,
            temperature=None, top_p=None,
            pad_token_id=tokenizer.eos_token_id,
        )
    gen = out[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(gen, skip_special_tokens=True).strip()


# ════════════════════════════════════════════════════════════════════════
# SCORING
# ════════════════════════════════════════════════════════════════════════

def score(response, prompt, kb_doc_ids, condition_coverage=0.0):
    cited = set(DOC_ID_RE.findall(response))
    fabricated = cited - kb_doc_ids  # any doc_id not in KB at all
    rl = response.lower()

    verdict_map = {
        "eligible": ["eligible"], "not eligible": ["not eligible", "ineligible"],
        "correct": ["correct", "matches"],
        "incorrect": ["incorrect", "under-deducted", "over-deducted", "mismatch", "wrong"],
        "applicable": ["applicable"], "not applicable": ["not applicable", "not allowed", "cannot claim"],
        "conditional": ["conditional", "depends", "if"],
        "informational": ["according to", "as per", "under", "section"],
        "mixed": ["however", "but", "although"],
    }
    keywords = verdict_map.get(prompt["expected_verdict"], [prompt["expected_verdict"]])
    verdict_ok = any(k in rl for k in keywords)

    return {
        "has_citation": len(cited) > 0,
        "has_fabrication": len(fabricated) > 0,
        "verdict_present": verdict_ok,
        "grounded_clean": (len(cited) > 0) and (len(fabricated) == 0) and verdict_ok,
        "condition_coverage": condition_coverage,
        "n_cited": len(cited),
        "n_fabricated": len(fabricated),
    }


def summarize(results):
    n = len(results)
    return {
        "n": n,
        "citation_coverage": round(sum(r["has_citation"] for r in results) / n, 3),
        "fabrication_rate": round(sum(r["has_fabrication"] for r in results) / n, 3),
        "verdict_accuracy": round(sum(r["verdict_present"] for r in results) / n, 3),
        "grounded_clean": round(sum(r["grounded_clean"] for r in results) / n, 3),
        "condition_coverage": round(sum(r["condition_coverage"] for r in results) / n, 3),
    }


# ════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("ShramikSaathi — 4-Config System-Level Ablation")
    print("=" * 70)

    prompts = load_prompts()
    kb, kb_list = load_kb()
    kb_doc_ids = set(kb.keys())
    print(f"[Data] {len(prompts)} prompts | {len(kb)} KB docs")

    # ── Retrievers ──
    bm25 = BM25Retriever(kb_list)
    faiss_kb = SearchKB(
        index_path=str(ROOT / "index" / "faiss_index.bin"),
        store_path=str(ROOT / "index" / "chunk_store.json"),
    )

    # ── Tokenizer ──
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ── Base model (for configs A, B, C) ──
    print("\n[Model] Loading raw LLaMA base (no adapter) for configs A/B/C...")
    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
    )
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, quantization_config=bnb, torch_dtype=torch.bfloat16,
        device_map="auto", attn_implementation="sdpa",
    )
    base_model.eval()
    print(f"        VRAM: {torch.cuda.memory_allocated()/1e9:.2f}GB")

    all_results = {}

    # ════════════════════════════════════════════════════════════════════
    # CONFIG A — Vanilla RAG: BM25 + raw LLaMA
    # ════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 70}")
    print("Config A — Vanilla RAG (BM25 + raw LLaMA)")
    print(f"{'=' * 70}")
    results_a = []
    for i, p in enumerate(prompts, 1):
        passages = bm25.search(p["query"], TOP_K)
        user_content = build_prompt_A(p["query"], passages)
        t0 = time.time()
        resp = generate(base_model, tokenizer, user_content)
        dt = time.time() - t0
        s = score(resp, p, kb_doc_ids, condition_coverage=0.0)
        results_a.append({"prompt_id": p["id"], "response": resp, **s})
        print(f"  [{i}/{len(prompts)}] {p['id']}  gc={s['grounded_clean']}  cites={s['n_cited']}  fab={s['n_fabricated']}  [{dt:.1f}s]")
    all_results["A_vanilla_rag"] = results_a

    # ════════════════════════════════════════════════════════════════════
    # CONFIG B — + Pre-retrieval: FAISS + domain/slots + raw LLaMA
    # ════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 70}")
    print("Config B — + Pre-retrieval (FAISS + slots + raw LLaMA)")
    print(f"{'=' * 70}")
    results_b = []
    for i, p in enumerate(prompts, 1):
        passages = faiss_kb.search(p["query"], top_k=TOP_K)
        user_content = build_prompt_B(p["query"], p["domain"], p["slots"], passages)
        t0 = time.time()
        resp = generate(base_model, tokenizer, user_content)
        dt = time.time() - t0
        s = score(resp, p, kb_doc_ids, condition_coverage=0.0)
        results_b.append({"prompt_id": p["id"], "response": resp, **s})
        print(f"  [{i}/{len(prompts)}] {p['id']}  gc={s['grounded_clean']}  cites={s['n_cited']}  fab={s['n_fabricated']}  [{dt:.1f}s]")
    all_results["B_pre_retrieval"] = results_b

    # ════════════════════════════════════════════════════════════════════
    # CONFIG C — + Reasoner: FAISS + reasoner + raw LLaMA
    # ════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 70}")
    print("Config C — + Reasoner (FAISS + reasoner + raw LLaMA)")
    print(f"{'=' * 70}")
    results_c = []
    for i, p in enumerate(prompts, 1):
        passages = faiss_kb.search(p["query"], top_k=TOP_K)
        intent = p["slots"].get("intent", "general")
        reasoning = None
        cov = 0.0
        if intent in REASONING_INTENTS:
            try:
                reasoning = run_eligibility_reasoner(passages, p["slots"], domain=p["domain"])
                cov = reasoning.get("coverage", 0.0)
            except Exception as e:
                print(f"    [!] Reasoner error: {e}")
            time.sleep(0.5)

        user_content = build_prompt_C(p["query"], p["domain"], p["slots"], passages, reasoning)
        t0 = time.time()
        resp = generate(base_model, tokenizer, user_content)
        dt = time.time() - t0
        s = score(resp, p, kb_doc_ids, condition_coverage=cov)
        results_c.append({"prompt_id": p["id"], "response": resp, **s})
        print(f"  [{i}/{len(prompts)}] {p['id']}  gc={s['grounded_clean']}  cov={cov:.2f}  cites={s['n_cited']}  fab={s['n_fabricated']}  [{dt:.1f}s]")
    all_results["C_with_reasoner"] = results_c

    # ── Free base model, load DPO ──
    del base_model
    torch.cuda.empty_cache()

    print("\n[Model] Loading DPO model for config D...")
    dpo_base = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, quantization_config=bnb, torch_dtype=torch.bfloat16,
        device_map="auto", attn_implementation="sdpa",
    )
    dpo_model = PeftModel.from_pretrained(dpo_base, str(DPO_ADAPTER))
    dpo_model.eval()
    print(f"        VRAM: {torch.cuda.memory_allocated()/1e9:.2f}GB")

    # ════════════════════════════════════════════════════════════════════
    # CONFIG D — Full ShramikSaathi: FAISS + reasoner + DPO
    # ════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 70}")
    print("Config D — Full ShramikSaathi (FAISS + reasoner + DPO)")
    print(f"{'=' * 70}")
    results_d = []
    for i, p in enumerate(prompts, 1):
        passages = faiss_kb.search(p["query"], top_k=TOP_K)
        intent = p["slots"].get("intent", "general")
        reasoning = None
        cov = 0.0
        if intent in REASONING_INTENTS:
            try:
                reasoning = run_eligibility_reasoner(passages, p["slots"], domain=p["domain"])
                cov = reasoning.get("coverage", 0.0)
            except Exception as e:
                print(f"    [!] Reasoner error: {e}")
            time.sleep(0.5)

        user_content = build_prompt_C(p["query"], p["domain"], p["slots"], passages, reasoning)
        t0 = time.time()
        resp = generate(dpo_model, tokenizer, user_content)
        dt = time.time() - t0
        s = score(resp, p, kb_doc_ids, condition_coverage=cov)
        results_d.append({"prompt_id": p["id"], "response": resp, **s})
        print(f"  [{i}/{len(prompts)}] {p['id']}  gc={s['grounded_clean']}  cov={cov:.2f}  cites={s['n_cited']}  fab={s['n_fabricated']}  [{dt:.1f}s]")
    all_results["D_full_system"] = results_d

    del dpo_model, dpo_base
    torch.cuda.empty_cache()

    summaries = {k: summarize(v) for k, v in all_results.items()}

    print("")
    print("=" * 78)
    print("ABLATION RESULTS (n=20)")
    print("=" * 78)
    configs = list(all_results.keys())
    labels = {
        "A_vanilla_rag": "A: Vanilla RAG",
        "B_pre_retrieval": "B: +PreRetrieval",
        "C_with_reasoner": "C: +Reasoner",
        "D_full_system": "D: Full System",
    }

    header = f"{'Metric':<22}" + "".join(f"{labels.get(c,c):>18}" for c in configs)
    print(header)
    print("-" * (22 + 18 * len(configs)))
    for metric in ["citation_coverage", "fabrication_rate", "verdict_accuracy",
                   "grounded_clean", "condition_coverage"]:
        row = f"{metric:<22}"
        for c in configs:
            row += f"{summaries[c][metric]:>18.3f}"
        print(row)

    print("")
    print("Deltas from Config A:")
    print(f"{'Config':<22} {'grounded_clean':>18} {'cond_coverage':>18}")
    base_gc = summaries["A_vanilla_rag"]["grounded_clean"]
    base_cc = summaries["A_vanilla_rag"]["condition_coverage"]
    for c in configs:
        gc_d = summaries[c]["grounded_clean"] - base_gc
        cc_d = summaries[c]["condition_coverage"] - base_cc
        print(f"{labels.get(c,c):<22} {gc_d:>+18.3f} {cc_d:>+18.3f}")

    print("")
    print("Per-domain grounded_clean:")
    header = f"{'Domain':<10}" + "".join(f"{labels.get(c,c):>18}" for c in configs)
    print(header)
    for dom in ["pf", "payslip", "labour", "tax"]:
        row = f"{dom:<10}"
        for c in configs:
            dom_results = [r for r, p in zip(all_results[c], prompts) if p["domain"] == dom]
            if dom_results:
                gc = sum(r["grounded_clean"] for r in dom_results) / len(dom_results)
                row += f"{gc:>18.2f}"
            else:
                row += f"{'n/a':>18}"
        print(row)

    out = {
        "n_prompts": len(prompts),
        "configs": list(labels.values()),
        "summaries": summaries,
        "all_results": {k: v for k, v in all_results.items()},
    }
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("")
    print("[Save] " + str(OUT_PATH))
    print("")
    print("=" * 78)
    print("Ablation complete.")
    print("=" * 78)


if __name__ == "__main__":
    main()