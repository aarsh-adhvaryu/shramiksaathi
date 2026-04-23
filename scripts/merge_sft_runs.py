"""
Merge run-1 and run-2 incremental files into final train/val split.

Strategy:
    - Drop run-1 payslip examples (suspect tool-citation quality)
    - Keep run-1 everything else (pf, labour, tax)
    - Keep run-2 fully (payslip cleaner + tax extra)
    - Re-stratify train/val 90/10 by intent
"""
import json
import random
from pathlib import Path
from collections import Counter, defaultdict

random.seed(42)
ROOT = Path.home() / "shramiksaathi"
DATA = ROOT / "data"

FIRSTRUN = DATA / ".sft_incremental.firstrun.jsonl"
SECONDRUN = DATA / ".sft_incremental.jsonl"
TRAIN_OUT = DATA / "sft_train.jsonl"
VAL_OUT   = DATA / "sft_val.jsonl"
STATS_OUT = DATA / "sft_generation_stats.json"

def load(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

run1 = load(FIRSTRUN)
run2 = load(SECONDRUN)
print(f"Run 1: {len(run1)} examples")
print(f"Run 2: {len(run2)} examples")

# Drop run-1 payslip (dirty tool-citation quality)
run1_kept = [r for r in run1 if r["metadata"]["domain"] != "payslip"]
print(f"Run 1 after dropping payslip: {len(run1_kept)}")

merged = run1_kept + run2
print(f"Merged: {len(merged)} examples")

# Stratified 90/10 split by intent
by_intent = defaultdict(list)
for r in merged:
    by_intent[r["metadata"]["intent"]].append(r)

train, val = [], []
for intent, rows in by_intent.items():
    random.shuffle(rows)
    n_val = max(1, int(len(rows) * 0.10)) if len(rows) >= 10 else 0
    val.extend(rows[:n_val])
    train.extend(rows[n_val:])

random.shuffle(train)
random.shuffle(val)

with open(TRAIN_OUT, 'w') as f:
    for r in train:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
with open(VAL_OUT, 'w') as f:
    for r in val:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

stats = {
    "total": len(merged),
    "train": len(train),
    "val": len(val),
    "by_domain": dict(Counter(r["metadata"]["domain"] for r in merged)),
    "by_intent": dict(Counter(r["metadata"]["intent"] for r in merged)),
    "by_subdomain": dict(Counter(r["metadata"]["subdomain"] for r in merged)),
    "reasoning_yes": sum(1 for r in merged if r["metadata"]["has_reasoning"]),
    "reasoning_eligible_true": sum(1 for r in merged
                                   if r["metadata"].get("reasoning_eligible") is True),
    "reasoning_eligible_false": sum(1 for r in merged
                                    if r["metadata"].get("reasoning_eligible") is False),
    "source": {
        "run1_kept": len(run1_kept),
        "run2_kept": len(run2),
        "run1_payslip_dropped": len(run1) - len(run1_kept),
    }
}
with open(STATS_OUT, 'w') as f:
    json.dump(stats, f, indent=2)

print(f"\nTrain: {len(train)} -> {TRAIN_OUT}")
print(f"Val:   {len(val)}   -> {VAL_OUT}")
print(f"Stats: {STATS_OUT}\n")
print(json.dumps(stats, indent=2))