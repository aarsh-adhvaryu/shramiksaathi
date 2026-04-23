"""
Merge all domain KB files into a single kb.jsonl for FAISS indexing.
Run from project root: python scripts/merge_kb.py
"""

import json
from pathlib import Path

# ── Input files ────────────────────────────────────────────────────────────────
# Adjust these paths to match your project layout

KB_FILES = {
    "pf":      "data/pf_kb.jsonl",
    "payslip": "data/payslip_kb.jsonl",
    "labour":  "data/labour_kb.jsonl",
    "tax":     "data/tax_kb.jsonl",
}

OUTPUT = "data/kb.jsonl"


def merge():
    all_docs = []
    doc_ids_seen = set()

    for domain, path in KB_FILES.items():
        p = Path(path)
        if not p.exists():
            print(f"  SKIP {path} — file not found")
            continue

        count = 0
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                doc = json.loads(line)

                # Ensure domain field is set correctly
                if "domain" not in doc or not doc["domain"]:
                    doc["domain"] = domain

                # Deduplicate by doc_id + chunk_index
                chunk_key = f"{doc.get('doc_id', '')}_{doc.get('chunk_index', 0)}"
                if chunk_key in doc_ids_seen:
                    continue
                doc_ids_seen.add(chunk_key)

                all_docs.append(doc)
                count += 1

        print(f"  {domain}: {count} docs from {path}")

    # Write merged output
    Path(OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        for doc in all_docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"\n  Merged: {len(all_docs)} total docs → {OUTPUT}")

    # Domain distribution
    from collections import Counter
    dist = Counter(d.get("domain", "?") for d in all_docs)
    for domain, count in sorted(dist.items()):
        print(f"    {domain}: {count}")


if __name__ == "__main__":
    print("Merging KB files...\n")
    merge()
    print("\nDone.")
