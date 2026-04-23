"""
Sufficiency Gate Evaluation — runs rule-based gate and always-proceed baseline
against sufficiency_eval.jsonl
Reports: gate accuracy, false-sufficient rate, false-insufficient rate, per-domain breakdown
"""

import os
import sys
import json
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from sufficiency_gate import check_sufficiency, baseline_check

EVAL_FILE = os.path.join(os.path.dirname(__file__), "sufficiency_eval.jsonl")
DOMAINS = ["pf", "payslip", "labour", "tax"]


def load_eval_data(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


# ── Metrics ────────────────────────────────────────────────────────────────────


def compute_metrics(examples, gate_fn):
    """
    Compute gate accuracy, false-sufficient rate, and false-insufficient rate.

    False-sufficient = gate says "proceed" but answer is "insufficient"
                       → DANGEROUS: retrieves on incomplete info → hallucinated answers
    False-insufficient = gate says "ask" but answer is "sufficient"
                       → ANNOYING: unnecessary question, but not harmful
    """
    domain_stats = {}
    failures = []

    for ex in examples:
        domain = ex["domain"]
        intent = ex["intent"]
        filled_slots = ex["filled_slots"]
        expected = ex["expected_decision"]  # "sufficient" or "insufficient"
        expected_missing = ex.get("expected_missing_slot")  # for insufficient cases

        result = gate_fn(filled_slots, domain)
        predicted = "sufficient" if result["sufficient"] else "insufficient"

        if domain not in domain_stats:
            domain_stats[domain] = {
                "correct": 0, "total": 0,
                "false_sufficient": 0, "true_insufficient": 0,
                "false_insufficient": 0, "true_sufficient": 0,
                "missing_slot_correct": 0, "missing_slot_total": 0,
            }
        stats = domain_stats[domain]
        stats["total"] += 1

        if predicted == expected:
            stats["correct"] += 1

        # Track false-sufficient and false-insufficient separately
        if expected == "insufficient":
            stats["true_insufficient"] += 1
            if predicted == "sufficient":
                stats["false_sufficient"] += 1
                failures.append({
                    "type": "FALSE_SUFFICIENT",
                    "domain": domain,
                    "intent": intent,
                    "filled": list(filled_slots.keys()),
                    "expected_missing": expected_missing,
                })
            else:
                # Check if we identified the right missing slot
                if expected_missing:
                    stats["missing_slot_total"] += 1
                    if expected_missing in result.get("missing", []):
                        stats["missing_slot_correct"] += 1
                    else:
                        failures.append({
                            "type": "WRONG_MISSING_SLOT",
                            "domain": domain,
                            "intent": intent,
                            "expected_missing": expected_missing,
                            "predicted_missing": result.get("missing", []),
                        })

        elif expected == "sufficient":
            stats["true_sufficient"] += 1
            if predicted == "insufficient":
                stats["false_insufficient"] += 1
                failures.append({
                    "type": "FALSE_INSUFFICIENT",
                    "domain": domain,
                    "intent": intent,
                    "filled": list(filled_slots.keys()),
                    "predicted_missing": result.get("missing", []),
                })

    # Compute final metrics
    results = {}
    total_correct, total_total = 0, 0
    total_fs, total_ti = 0, 0
    total_fi, total_ts = 0, 0

    for domain in DOMAINS:
        s = domain_stats.get(domain, {
            "correct": 0, "total": 0,
            "false_sufficient": 0, "true_insufficient": 0,
            "false_insufficient": 0, "true_sufficient": 0,
            "missing_slot_correct": 0, "missing_slot_total": 0,
        })
        total_correct += s["correct"]
        total_total += s["total"]
        total_fs += s["false_sufficient"]
        total_ti += s["true_insufficient"]
        total_fi += s["false_insufficient"]
        total_ts += s["true_sufficient"]

        accuracy = s["correct"] / s["total"] if s["total"] else 0
        fs_rate = s["false_sufficient"] / s["true_insufficient"] if s["true_insufficient"] else 0
        fi_rate = s["false_insufficient"] / s["true_sufficient"] if s["true_sufficient"] else 0
        ms_acc = s["missing_slot_correct"] / s["missing_slot_total"] if s["missing_slot_total"] else 0

        results[domain] = {
            "accuracy": round(accuracy, 3),
            "false_sufficient_rate": round(fs_rate, 3),
            "false_insufficient_rate": round(fi_rate, 3),
            "missing_slot_accuracy": round(ms_acc, 3),
            "examples": s["total"],
            "sufficient": s["true_sufficient"],
            "insufficient": s["true_insufficient"],
        }

    # Overall
    accuracy = total_correct / total_total if total_total else 0
    fs_rate = total_fs / total_ti if total_ti else 0
    fi_rate = total_fi / total_ts if total_ts else 0
    results["overall"] = {
        "accuracy": round(accuracy, 3),
        "false_sufficient_rate": round(fs_rate, 3),
        "false_insufficient_rate": round(fi_rate, 3),
        "examples": total_total,
    }

    return results, failures


# ── Display ────────────────────────────────────────────────────────────────────


def print_results(name, results, failures=None):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    overall = results["overall"]
    print(f"\n  Overall ({overall['examples']} examples):")
    print(f"    Gate Accuracy:          {overall['accuracy']}")
    print(f"    False-Sufficient Rate:  {overall['false_sufficient_rate']}  ← dangerous error")
    print(f"    False-Insufficient Rate: {overall['false_insufficient_rate']}  ← annoying error")

    print(f"\n  Per-domain:")
    print(f"  {'Domain':<10} {'Acc':>6} {'FS Rate':>8} {'FI Rate':>8} {'MissSlot':>9} {'N':>4}")
    print(f"  {'-'*47}")
    for d in DOMAINS:
        m = results.get(d, {})
        if m:
            print(f"  {d:<10} {m['accuracy']:>6.3f} {m['false_sufficient_rate']:>8.3f} {m['false_insufficient_rate']:>8.3f} {m['missing_slot_accuracy']:>9.3f} {m['examples']:>4}")

    if failures:
        # Group by type
        fs = [f for f in failures if f["type"] == "FALSE_SUFFICIENT"]
        fi = [f for f in failures if f["type"] == "FALSE_INSUFFICIENT"]
        wm = [f for f in failures if f["type"] == "WRONG_MISSING_SLOT"]

        if fs:
            print(f"\n  FALSE SUFFICIENT errors ({len(fs)}) — gate said proceed, should have blocked:")
            for f in fs[:8]:
                print(f"    [{f['domain']}] intent={f['intent']} | filled={f['filled']} | should ask: {f['expected_missing']}")

        if fi:
            print(f"\n  FALSE INSUFFICIENT errors ({len(fi)}) — gate blocked, should have proceeded:")
            for f in fi[:8]:
                print(f"    [{f['domain']}] intent={f['intent']} | filled={f['filled']} | gate asked for: {f['predicted_missing']}")

        if wm:
            print(f"\n  WRONG MISSING SLOT ({len(wm)}) — blocked correctly but asked about wrong slot:")
            for f in wm[:5]:
                print(f"    [{f['domain']}] intent={f['intent']} | expected={f['expected_missing']} | asked={f['predicted_missing']}")


def print_comparison(bl_results, gate_results):
    print(f"\n{'='*60}")
    print(f"  COMPARISON: ALWAYS-PROCEED BASELINE vs RULE-BASED GATE")
    print(f"{'='*60}")

    print(f"\n  {'Metric':<35} {'Baseline':>10} {'Gate':>10} {'Delta':>10}")
    print(f"  {'-'*65}")

    for metric, label in [
        ("accuracy", "Gate Accuracy"),
        ("false_sufficient_rate", "False-Sufficient Rate (danger)"),
        ("false_insufficient_rate", "False-Insufficient Rate (annoy)"),
    ]:
        bl_val = bl_results["overall"][metric]
        gate_val = gate_results["overall"][metric]
        delta = gate_val - bl_val
        # For false_sufficient_rate, negative delta is good
        print(f"  {label:<35} {bl_val:>10.3f} {gate_val:>10.3f} {delta:>+10.3f}")

    print(f"\n  Key insight:")
    bl_fs = bl_results["overall"]["false_sufficient_rate"]
    gate_fs = gate_results["overall"]["false_sufficient_rate"]
    print(f"    Baseline sends {bl_fs*100:.0f}% of incomplete queries to retrieval (all of them).")
    print(f"    Our gate reduces this to {gate_fs*100:.1f}%.")
    print(f"    This prevents hallucinated eligibility decisions from incomplete context.")


# ── Main ───────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sufficiency gate evaluation")
    parser.add_argument("--eval-file", default=EVAL_FILE,
                        help="Path to sufficiency_eval.jsonl")
    args = parser.parse_args()

    examples = load_eval_data(args.eval_file)
    print(f"Loaded {len(examples)} evaluation examples")
    for d in DOMAINS:
        count = sum(1 for e in examples if e["domain"] == d)
        suf = sum(1 for e in examples if e["domain"] == d and e["expected_decision"] == "sufficient")
        insuf = count - suf
        print(f"  {d}: {count} ({suf} sufficient, {insuf} insufficient)")

    # Always run both — no API calls needed for either
    print("\nRunning always-proceed baseline...")
    bl_results, bl_failures = compute_metrics(examples, baseline_check)
    print_results("ALWAYS-PROCEED BASELINE", bl_results, bl_failures)

    print("\nRunning rule-based gate...")
    gate_results, gate_failures = compute_metrics(examples, check_sufficiency)
    print_results("RULE-BASED SUFFICIENCY GATE", gate_results, gate_failures)

    print_comparison(bl_results, gate_results)
