"""
Router evaluation — runs baseline and LLM router against router_eval.jsonl
Reports: accuracy, per-domain P/R/F1, confusion matrix, failure analysis
"""

import os
import sys
import json
import time
from collections import defaultdict

# Add src/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from cross_domain_router import baseline_route, llm_route

EVAL_FILE = os.path.join(os.path.dirname(__file__), "router_eval.jsonl")
DOMAINS = ["pf", "payslip", "labour", "tax"]


def load_eval_data(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


# ── Metrics ────────────────────────────────────────────────────────────────────


def compute_metrics(examples, predictions):
    """
    Compute accuracy, per-domain P/R/F1, and confusion matrix.
    """
    correct = 0
    total = len(examples)

    # Confusion matrix: confusion[true][predicted] = count
    confusion = defaultdict(lambda: defaultdict(int))

    # Per-domain TP/FP/FN
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)

    failures = []

    for ex, pred in zip(examples, predictions):
        true = ex["expected_domain"]
        confusion[true][pred] += 1

        if pred == true:
            correct += 1
            tp[true] += 1
        else:
            fp[pred] += 1
            fn[true] += 1
            failures.append({
                "query": ex["query"],
                "expected": true,
                "predicted": pred,
            })

    accuracy = correct / total if total else 0

    # Per-domain precision, recall, F1
    domain_metrics = {}
    for d in DOMAINS:
        p = tp[d] / (tp[d] + fp[d]) if (tp[d] + fp[d]) else 0
        r = tp[d] / (tp[d] + fn[d]) if (tp[d] + fn[d]) else 0
        f1 = 2 * p * r / (p + r) if (p + r) else 0
        domain_metrics[d] = {
            "precision": round(p, 3),
            "recall": round(r, 3),
            "f1": round(f1, 3),
            "support": tp[d] + fn[d],
        }

    return {
        "accuracy": round(accuracy, 3),
        "domain_metrics": domain_metrics,
        "confusion": {t: dict(preds) for t, preds in confusion.items()},
        "failures": failures,
    }


# ── Display ────────────────────────────────────────────────────────────────────


def print_results(name, results):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    print(f"\n  Overall Accuracy: {results['accuracy']}")

    print(f"\n  Per-domain metrics:")
    print(f"  {'Domain':<10} {'Prec':>6} {'Rec':>6} {'F1':>6} {'Support':>8}")
    print(f"  {'-'*38}")
    for d in DOMAINS:
        m = results["domain_metrics"][d]
        print(f"  {d:<10} {m['precision']:>6.3f} {m['recall']:>6.3f} {m['f1']:>6.3f} {m['support']:>8}")

    print(f"\n  Confusion Matrix (rows=true, cols=predicted):")
    print(f"  {'':>10}", end="")
    for d in DOMAINS:
        print(f" {d:>8}", end="")
    print()
    for true_d in DOMAINS:
        print(f"  {true_d:>10}", end="")
        for pred_d in DOMAINS:
            count = results["confusion"].get(true_d, {}).get(pred_d, 0)
            print(f" {count:>8}", end="")
        print()

    if results["failures"]:
        print(f"\n  Failures ({len(results['failures'])}):")
        for f in results["failures"][:10]:  # show max 10
            print(f"    [{f['expected']} → {f['predicted']}] {f['query'][:75]}")


def print_comparison(baseline_results, llm_results):
    print(f"\n{'='*60}")
    print(f"  COMPARISON: BASELINE vs LLM")
    print(f"{'='*60}")
    print(f"\n  {'Metric':<25} {'Baseline':>10} {'LLM':>10} {'Delta':>10}")
    print(f"  {'-'*55}")
    print(f"  {'Overall Accuracy':<25} {baseline_results['accuracy']:>10.3f} {llm_results['accuracy']:>10.3f} {llm_results['accuracy'] - baseline_results['accuracy']:>+10.3f}")

    for d in DOMAINS:
        bl_f1 = baseline_results["domain_metrics"][d]["f1"]
        llm_f1 = llm_results["domain_metrics"][d]["f1"]
        print(f"  {f'{d} F1':<25} {bl_f1:>10.3f} {llm_f1:>10.3f} {llm_f1 - bl_f1:>+10.3f}")

    # Show queries baseline got wrong but LLM got right
    bl_failures = {f["query"] for f in baseline_results["failures"]}
    llm_failures = {f["query"] for f in llm_results["failures"]}
    fixed_by_llm = bl_failures - llm_failures
    broken_by_llm = llm_failures - bl_failures

    if fixed_by_llm:
        print(f"\n  Queries FIXED by LLM ({len(fixed_by_llm)}):")
        bl_failure_map = {f["query"]: f for f in baseline_results["failures"]}
        for q in list(fixed_by_llm)[:8]:
            f = bl_failure_map[q]
            print(f"    [{f['expected']} ← baseline said {f['predicted']}] {q[:70]}")

    if broken_by_llm:
        print(f"\n  Queries BROKEN by LLM ({len(broken_by_llm)}):")
        llm_failure_map = {f["query"]: f for f in llm_results["failures"]}
        for q in list(broken_by_llm)[:5]:
            f = llm_failure_map[q]
            print(f"    [{f['expected']} ← LLM said {f['predicted']}] {q[:70]}")


# ── Main ───────────────────────────────────────────────────────────────────────


def run_baseline(examples):
    predictions = [baseline_route(ex["query"]) for ex in examples]
    return compute_metrics(examples, predictions)


def run_llm(examples):
    predictions = []
    for i, ex in enumerate(examples):
        result = llm_route(ex["query"])
        predictions.append(result["domain"])
        # Rate limit protection
        if (i + 1) % 10 == 0:
            print(f"  ... processed {i+1}/{len(examples)}")
            time.sleep(1)
    return compute_metrics(examples, predictions)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Router evaluation")
    parser.add_argument("--baseline-only", action="store_true",
                        help="Run only the keyword baseline (no API calls)")
    parser.add_argument("--eval-file", default=EVAL_FILE,
                        help="Path to router_eval.jsonl")
    args = parser.parse_args()

    examples = load_eval_data(args.eval_file)
    print(f"Loaded {len(examples)} evaluation examples")

    # Always run baseline
    print("\nRunning keyword baseline...")
    bl_results = run_baseline(examples)
    print_results("KEYWORD BASELINE", bl_results)

    if not args.baseline_only:
        print("\nRunning LLM router...")
        llm_results = run_llm(examples)
        print_results("LLM ROUTER (zero-shot)", llm_results)
        print_comparison(bl_results, llm_results)
    else:
        print("\n(Skipping LLM — run without --baseline-only to include)")