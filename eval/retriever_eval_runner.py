"""
Retriever Eval: BM25 baseline vs FAISS + MiniLM
Gold passages from eval_heldout.jsonl (passage_doc_ids)
Metrics: Recall@5, MRR@5
"""
import os, sys, json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

EVAL_PATH  = ROOT / "data" / "eval_heldout.jsonl"
KB_PATH    = ROOT / "data" / "kb.jsonl"
INDEX_PATH = ROOT / "index" / "faiss_index.bin"
STORE_PATH = ROOT / "index" / "chunk_store.json"
OUT_PATH   = ROOT / "data" / "retriever_eval_results.json"

TOP_K = 5


def load_data():
    prompts = [json.loads(l) for l in open(EVAL_PATH) if l.strip()]
    kb_docs = []
    with open(KB_PATH) as f:
        for line in f:
            if line.strip():
                kb_docs.append(json.loads(line))
    return prompts, kb_docs


def get_gold_doc_ids(prompt):
    return [d for d in prompt["passage_doc_ids"] if d != "TOOL_PAYSLIP_AUDIT"]


def eval_bm25(prompts, kb_docs):
    print("\n[BM25] Building index...")
    doc_id_list = [d["doc_id"] for d in kb_docs]
    tokenized = [d["content"].lower().split() for d in kb_docs]
    bm25 = BM25Okapi(tokenized)

    results = []
    for p in prompts:
        gold = set(get_gold_doc_ids(p))
        if not gold:
            continue
        query_tokens = p["query"].lower().split()
        scores = bm25.get_scores(query_tokens)
        top_indices = np.argsort(scores)[::-1][:TOP_K]
        retrieved = [doc_id_list[i] for i in top_indices]

        hits = [d for d in retrieved if d in gold]
        recall = len(hits) / len(gold) if gold else 0
        mrr = 0.0
        for rank, d in enumerate(retrieved, 1):
            if d in gold:
                mrr = 1.0 / rank
                break

        results.append({
            "id": p["id"], "domain": p["domain"],
            "gold": sorted(gold), "retrieved": retrieved,
            "recall": recall, "mrr": mrr,
        })
    return results


def eval_faiss(prompts, kb_docs):
    print("\n[FAISS] Loading index + encoder...")
    encoder = SentenceTransformer("all-MiniLM-L6-v2")

    with open(STORE_PATH) as f:
        chunk_store = json.load(f)

    index = faiss.read_index(str(INDEX_PATH))
    # Build ordered doc_id list matching index order
    doc_id_list = [c["doc_id"] for c in chunk_store]

    results = []
    for p in prompts:
        gold = set(get_gold_doc_ids(p))
        if not gold:
            continue
        q_vec = encoder.encode([p["query"]], normalize_embeddings=False).astype("float32")
        distances, indices = index.search(q_vec, TOP_K)
        retrieved = [doc_id_list[i] for i in indices[0] if i < len(doc_id_list)]

        hits = [d for d in retrieved if d in gold]
        recall = len(hits) / len(gold) if gold else 0
        mrr = 0.0
        for rank, d in enumerate(retrieved, 1):
            if d in gold:
                mrr = 1.0 / rank
                break

        results.append({
            "id": p["id"], "domain": p["domain"],
            "gold": sorted(gold), "retrieved": retrieved,
            "recall": recall, "mrr": mrr,
        })
    return results


def summarize(results, label):
    n = len(results)
    mean_recall = sum(r["recall"] for r in results) / n
    mean_mrr = sum(r["mrr"] for r in results) / n
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(f"  Queries evaluated: {n}")
    print(f"  Recall@{TOP_K}:  {mean_recall:.3f}")
    print(f"  MRR@{TOP_K}:     {mean_mrr:.3f}")

    by_domain = defaultdict(list)
    for r in results:
        by_domain[r["domain"]].append(r)
    print(f"\n  Per-domain:")
    print(f"  {'Domain':<10} {'Recall@5':>10} {'MRR@5':>10} {'N':>5}")
    for dom in ["pf", "payslip", "labour", "tax"]:
        if dom in by_domain:
            dr = by_domain[dom]
            print(f"  {dom:<10} {sum(r['recall'] for r in dr)/len(dr):>10.3f} {sum(r['mrr'] for r in dr)/len(dr):>10.3f} {len(dr):>5}")

    return {"label": label, "n": n, "recall_at_5": round(mean_recall, 3), "mrr_at_5": round(mean_mrr, 3)}


def main():
    print("=" * 60)
    print("Retriever Eval: BM25 vs FAISS + MiniLM")
    print("=" * 60)

    prompts, kb_docs = load_data()
    print(f"[Data] {len(prompts)} prompts | {len(kb_docs)} KB docs")

    bm25_results = eval_bm25(prompts, kb_docs)
    faiss_results = eval_faiss(prompts, kb_docs)

    bm25_summary = summarize(bm25_results, "BM25 BASELINE")
    faiss_summary = summarize(faiss_results, "FAISS + MiniLM (OURS)")

    print(f"\n{'=' * 60}")
    print("  COMPARISON: BM25 vs FAISS")
    print(f"{'=' * 60}")
    print(f"  {'Metric':<20} {'BM25':>10} {'FAISS':>10} {'Delta':>10}")
    print(f"  {'-' * 50}")
    for metric in ["recall_at_5", "mrr_at_5"]:
        b = bm25_summary[metric]
        f = faiss_summary[metric]
        print(f"  {metric:<20} {b:>10.3f} {f:>10.3f} {f-b:>+10.3f}")

    out = {
        "bm25": {"summary": bm25_summary, "per_query": bm25_results},
        "faiss": {"summary": faiss_summary, "per_query": faiss_results},
    }
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n[Save] {OUT_PATH}")


if __name__ == "__main__":
    main()
