"""
Condition Coverage Score — Novel Metric
Measures: fraction of mandatory eligibility conditions resolved before answering.
Baseline (no reasoner) = 0.00 by construction.
"""
import os, sys, json, time
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from eligibility_reasoner import run_eligibility_reasoner

EVAL_PATH = ROOT / "data" / "eval_heldout.jsonl"
KB_PATH   = ROOT / "data" / "kb.jsonl"
OUT_PATH  = ROOT / "data" / "condition_coverage_results.json"

# Intents that trigger the eligibility reasoner (from pipeline.py)
REASONING_INTENTS = {
    "full_withdrawal", "partial_withdrawal", "transfer",
    "tds_query", "kyc_issue",
    "verify_epf", "verify_esi", "check_deductions",
    "check_minimum_wage", "full_audit",
    "gratuity", "wrongful_termination", "maternity_benefit", "overtime_pay",
    "tds_on_salary", "tds_on_pf", "hra_exemption", "deductions_80c",
}


def load_kb():
    kb = {}
    with open(KB_PATH) as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                kb[d["doc_id"]] = d
    return kb


def build_passages(prompt, kb):
    passages = []
    for did in prompt["passage_doc_ids"]:
        if did == "TOOL_PAYSLIP_AUDIT":
            # Include tool output as a pseudo-passage for payslip queries
            passages.append({
                "doc_id": "TOOL_PAYSLIP_AUDIT",
                "content": "Payslip audit tool output — deduction calculations provided.",
                "domain": "payslip", "subdomain": "tool_output",
            })
        elif did in kb:
            passages.append(kb[did])
    return passages


def main():
    print("=" * 60)
    print("Condition Coverage Score — Novel Metric Evaluation")
    print("=" * 60)

    prompts = [json.loads(l) for l in open(EVAL_PATH) if l.strip()]
    kb = load_kb()

    # Filter to reasoning-eligible prompts only
    reasoning_prompts = [p for p in prompts if p["slots"].get("intent") in REASONING_INTENTS]
    print(f"[Data] {len(prompts)} total prompts | {len(reasoning_prompts)} have reasoning intents")

    if not reasoning_prompts:
        print("[!] No reasoning prompts found. Check intent values in eval_heldout.jsonl.")
        return

    # ── Baseline: no reasoner → coverage = 0.00 by construction ──
    baseline_results = []
    for p in reasoning_prompts:
        baseline_results.append({
            "id": p["id"], "domain": p["domain"],
            "intent": p["slots"].get("intent"),
            "coverage": 0.0,
            "conditions_total": 0,
            "conditions_resolved": 0,
            "decision": "ANSWER (no check)",
        })

    # ── Ours: run eligibility reasoner ──
    our_results = []
    print(f"\nRunning eligibility reasoner on {len(reasoning_prompts)} prompts...")
    for i, p in enumerate(reasoning_prompts, 1):
        passages = build_passages(p, kb)
        slots = p["slots"]
        domain = p["domain"]

        try:
            reasoning = run_eligibility_reasoner(passages, slots, domain=domain)
            n_met = len(reasoning.get("met", []))
            n_failed = len(reasoning.get("failed", []))
            n_warnings = len(reasoning.get("warnings", []))
            n_unresolved = len(reasoning.get("unresolved", []))
            total = n_met + n_failed + n_warnings + n_unresolved
            resolved = n_met + n_failed  # both met and failed are "resolved" (checked)
            coverage = reasoning.get("coverage", resolved / total if total > 0 else 0)

            our_results.append({
                "id": p["id"], "domain": domain,
                "intent": slots.get("intent"),
                "coverage": coverage,
                "conditions_total": total,
                "conditions_resolved": resolved,
                "decision": reasoning.get("decision", "?"),
                "met": n_met, "failed": n_failed,
                "warnings": n_warnings, "unresolved": n_unresolved,
            })
            print(f"  [{i}/{len(reasoning_prompts)}] {p['id']}  coverage={coverage:.2f}  "
                  f"total={total}  resolved={resolved}  decision={reasoning.get('decision')}")
        except Exception as e:
            print(f"  [{i}/{len(reasoning_prompts)}] {p['id']}  ERROR: {e}")
            our_results.append({
                "id": p["id"], "domain": domain,
                "intent": slots.get("intent"),
                "coverage": 0.0, "error": str(e),
            })
        time.sleep(0.5)  # rate limit buffer

    # ── Summary ──
    n = len(reasoning_prompts)
    baseline_mean = 0.0
    our_mean = sum(r["coverage"] for r in our_results) / n if n > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"  CONDITION COVERAGE SCORE RESULTS")
    print(f"{'=' * 60}")
    print(f"  Reasoning prompts evaluated: {n}")
    print(f"  Baseline (no reasoner):  {baseline_mean:.3f}")
    print(f"  ShramikSaathi:           {our_mean:.3f}")
    print(f"  Delta:                   {our_mean - baseline_mean:+.3f}")

    # Per-domain
    by_domain = defaultdict(list)
    for r in our_results:
        by_domain[r["domain"]].append(r)
    print(f"\n  Per-domain coverage:")
    print(f"  {'Domain':<10} {'Baseline':>10} {'Ours':>10} {'N':>5}")
    for dom in ["pf", "payslip", "labour", "tax"]:
        if dom in by_domain:
            dr = by_domain[dom]
            dm = sum(r["coverage"] for r in dr) / len(dr)
            print(f"  {dom:<10} {'0.000':>10} {dm:>10.3f} {len(dr):>5}")

    # Per-query detail
    print(f"\n  Per-query breakdown:")
    for r in our_results:
        status = "✓" if r["coverage"] >= 0.5 else "⚠" if r["coverage"] > 0 else "✗"
        print(f"    {status} {r['id']:<15} coverage={r['coverage']:.2f}  "
              f"decision={r.get('decision','?')}  total={r.get('conditions_total',0)}")

    out = {
        "n_prompts": n,
        "baseline_mean_coverage": baseline_mean,
        "our_mean_coverage": round(our_mean, 3),
        "delta": round(our_mean - baseline_mean, 3),
        "baseline_results": baseline_results,
        "our_results": our_results,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n[Save] {OUT_PATH}")


if __name__ == "__main__":
    main()
