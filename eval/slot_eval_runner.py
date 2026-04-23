"""
Slot Extractor Evaluation — runs baseline and LLM against slot_eval.jsonl
Reports: per-domain slot precision/recall/value accuracy, failure examples
"""

import os
import sys
import json
import time
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from slot_extractor import baseline_extract, extract_slots

EVAL_FILE = os.path.join(os.path.dirname(__file__), "slot_eval.jsonl")
DOMAINS = ["pf", "payslip", "labour", "tax"]

# Slots to skip in evaluation — intent is evaluated separately
SKIP_SLOTS = {"intent"}


def load_eval_data(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


# ── Metrics ────────────────────────────────────────────────────────────────────


def compute_metrics(examples, predictions):
    """
    Compute slot-level precision, recall, value accuracy per domain + overall.
    Also tracks intent accuracy separately and collects failure examples.
    """
    domain_stats = {}
    intent_stats = defaultdict(lambda: {"correct": 0, "total": 0})
    failures = []

    for ex, pred in zip(examples, predictions):
        domain = ex["domain"]
        expected = ex["expected_slots"]

        if domain not in domain_stats:
            domain_stats[domain] = {
                "tp": 0, "fp": 0, "fn": 0, "val_correct": 0,
                "slot_failures": [],
            }
        stats = domain_stats[domain]

        # Intent accuracy (separate metric)
        exp_intent = expected.get("intent")
        pred_intent = pred.get("intent")
        intent_stats[domain]["total"] += 1
        if exp_intent and pred_intent and str(exp_intent).lower() == str(pred_intent).lower():
            intent_stats[domain]["correct"] += 1

        # Slot-level evaluation (skip intent)
        all_keys = set(list(expected.keys()) + list(pred.keys())) - SKIP_SLOTS
        query_failures = []

        for key in all_keys:
            exp_val = expected.get(key)
            pred_val = pred.get(key)

            if exp_val is not None and pred_val is not None:
                stats["tp"] += 1
                if _values_match(pred_val, exp_val):
                    stats["val_correct"] += 1
                else:
                    query_failures.append(
                        f"  {key}: expected={exp_val}, got={pred_val}"
                    )
            elif exp_val is not None and pred_val is None:
                stats["fn"] += 1
                query_failures.append(f"  {key}: expected={exp_val}, got=None (MISSED)")
            elif exp_val is None and pred_val is not None:
                stats["fp"] += 1
                query_failures.append(
                    f"  {key}: expected=None, got={pred_val} (HALLUCINATED)"
                )

        if query_failures:
            failures.append({
                "domain": domain,
                "query": ex["query"],
                "issues": query_failures,
                "intent_ok": str(exp_intent).lower() == str(pred_intent).lower() if exp_intent and pred_intent else False,
            })

    # Compute final metrics
    results = {}
    total_tp, total_fp, total_fn, total_vc = 0, 0, 0, 0

    for domain in DOMAINS:
        s = domain_stats.get(domain, {"tp": 0, "fp": 0, "fn": 0, "val_correct": 0})
        tp, fp, fn, vc = s["tp"], s["fp"], s["fn"], s["val_correct"]
        total_tp += tp; total_fp += fp; total_fn += fn; total_vc += vc

        precision = tp / (tp + fp) if (tp + fp) else 0
        recall = tp / (tp + fn) if (tp + fn) else 0
        val_acc = vc / tp if tp else 0
        i_stats = intent_stats[domain]
        intent_acc = i_stats["correct"] / i_stats["total"] if i_stats["total"] else 0

        results[domain] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "value_accuracy": round(val_acc, 3),
            "intent_accuracy": round(intent_acc, 3),
            "tp": tp, "fp": fp, "fn": fn,
            "examples": i_stats["total"],
        }

    # Overall
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0
    val_acc = total_vc / total_tp if total_tp else 0

    total_intent_correct = sum(v["correct"] for v in intent_stats.values())
    total_intent = sum(v["total"] for v in intent_stats.values())
    intent_acc = total_intent_correct / total_intent if total_intent else 0

    results["overall"] = {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "value_accuracy": round(val_acc, 3),
        "intent_accuracy": round(intent_acc, 3),
    }

    return results, failures


def _values_match(pred, expected):
    """
    Flexible value comparison.
    Handles: string case, int/float truncation, bool variants.
    """
    # Both null
    if pred is None and expected is None:
        return True

    # Bool comparison
    if isinstance(expected, bool):
        if isinstance(pred, bool):
            return pred == expected
        return str(pred).lower() in (str(expected).lower(), "1" if expected else "0")

    # Numeric comparison (allow ±1 tolerance for rounding differences)
    try:
        return abs(int(float(str(pred))) - int(float(str(expected)))) <= 1
    except (ValueError, TypeError):
        pass

    # String comparison (case-insensitive, strip whitespace)
    return str(pred).lower().strip() == str(expected).lower().strip()


# ── Display ────────────────────────────────────────────────────────────────────


def print_results(name, results, failures=None):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    overall = results["overall"]
    print(f"\n  Overall:")
    print(f"    Slot Precision:   {overall['precision']}")
    print(f"    Slot Recall:      {overall['recall']}")
    print(f"    Value Accuracy:   {overall['value_accuracy']}")
    print(f"    Intent Accuracy:  {overall['intent_accuracy']}")

    print(f"\n  Per-domain:")
    print(f"  {'Domain':<10} {'Prec':>6} {'Rec':>6} {'ValAcc':>7} {'Intent':>7} {'N':>4}")
    print(f"  {'-'*42}")
    for d in DOMAINS:
        m = results.get(d, {})
        if m:
            print(f"  {d:<10} {m['precision']:>6.3f} {m['recall']:>6.3f} {m['value_accuracy']:>7.3f} {m['intent_accuracy']:>7.3f} {m.get('examples',0):>4}")

    if failures:
        print(f"\n  Failures ({len(failures)} queries with issues):")
        for f in failures[:12]:
            print(f"\n    [{f['domain']}] {f['query'][:70]}")
            for issue in f["issues"][:3]:
                print(f"      {issue}")


def print_comparison(bl_results, llm_results, bl_failures, llm_failures):
    print(f"\n{'='*60}")
    print(f"  COMPARISON: BASELINE vs LLM")
    print(f"{'='*60}")

    print(f"\n  {'Metric':<30} {'Baseline':>10} {'LLM':>10} {'Delta':>10}")
    print(f"  {'-'*60}")

    for metric in ["precision", "recall", "value_accuracy", "intent_accuracy"]:
        bl_val = bl_results["overall"][metric]
        llm_val = llm_results["overall"][metric]
        label = f"Overall {metric.replace('_', ' ').title()}"
        print(f"  {label:<30} {bl_val:>10.3f} {llm_val:>10.3f} {llm_val - bl_val:>+10.3f}")

    print()
    for d in DOMAINS:
        if d in bl_results and d in llm_results:
            for metric in ["precision", "recall", "value_accuracy"]:
                bl_val = bl_results[d][metric]
                llm_val = llm_results[d][metric]
                label = f"{d} {metric.replace('_', ' ')}"
                print(f"  {label:<30} {bl_val:>10.3f} {llm_val:>10.3f} {llm_val - bl_val:>+10.3f}")
            print()

    # Show what LLM fixed
    bl_fail_queries = {f["query"] for f in bl_failures}
    llm_fail_queries = {f["query"] for f in llm_failures}
    fixed = bl_fail_queries - llm_fail_queries
    broken = llm_fail_queries - bl_fail_queries

    if fixed:
        print(f"  Queries FIXED by LLM ({len(fixed)}):")
        for q in list(fixed)[:6]:
            print(f"    {q[:75]}")

    if broken:
        print(f"\n  Queries BROKEN by LLM ({len(broken)}):")
        for q in list(broken)[:6]:
            print(f"    {q[:75]}")


# ── Main ───────────────────────────────────────────────────────────────────────


def run_baseline(examples):
    predictions = [baseline_extract(ex["query"], ex["domain"]) for ex in examples]
    return compute_metrics(examples, predictions)


def run_llm(examples):
    predictions = []
    for i, ex in enumerate(examples):
        pred = extract_slots(ex["query"], ex["domain"])
        predictions.append(pred)
        if (i + 1) % 10 == 0:
            print(f"  ... processed {i+1}/{len(examples)}")
            time.sleep(1)
    return compute_metrics(examples, predictions)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Slot extractor evaluation")
    parser.add_argument("--baseline-only", action="store_true",
                        help="Run only the regex baseline (no API calls)")
    parser.add_argument("--eval-file", default=EVAL_FILE,
                        help="Path to slot_eval.jsonl")
    args = parser.parse_args()

    examples = load_eval_data(args.eval_file)
    print(f"Loaded {len(examples)} evaluation examples")
    for d in DOMAINS:
        count = sum(1 for e in examples if e["domain"] == d)
        print(f"  {d}: {count}")

    # Always run baseline
    print("\nRunning regex baseline...")
    bl_results, bl_failures = run_baseline(examples)
    print_results("REGEX/KEYWORD BASELINE", bl_results, bl_failures)

    if not args.baseline_only:
        print("\nRunning LLM slot extractor...")
        llm_results, llm_failures = run_llm(examples)
        print_results("LLM SLOT EXTRACTOR", llm_results, llm_failures)
        print_comparison(bl_results, llm_results, bl_failures, llm_failures)
    else:
        print("\n(Skipping LLM — run without --baseline-only to include)")
