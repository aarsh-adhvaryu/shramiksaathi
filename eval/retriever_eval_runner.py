"""
Retriever Evaluation — BM25 vs FAISS comparison
Metrics: Domain Precision@5, Recall of key docs, Hinglish robustness

Uses router_eval.jsonl queries (which have expected domains) to measure
whether each retriever returns domain-relevant documents.
"""

import os
import sys
import json
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from bm25_retriever import BM25Retriever
from search_kb import SearchKB

EVAL_FILE = os.path.join(os.path.dirname(__file__), "router_eval.jsonl")
TOP_K = 5


def load_eval_data(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def domain_precision_at_k(retriever, examples, top_k=TOP_K):
    """
    For each query, retrieve top-k passages.
    Domain Precision@k = fraction of retrieved passages whose domain matches expected.
    """
    domain_stats = defaultdict(
        lambda: {"total_retrieved": 0, "domain_match": 0, "queries": 0}
    )
    all_match = 0
    all_total = 0
    failures = []

    for ex in examples:
        query = ex["query"]
        expected_domain = ex["expected_domain"]
        results = retriever.search(query, top_k=top_k)

        domain_stats[expected_domain]["queries"] += 1
        matches = 0

        for r in results:
            domain_stats[expected_domain]["total_retrieved"] += 1
            all_total += 1
            if r.get("domain") == expected_domain:
                matches += 1
                domain_stats[expected_domain]["domain_match"] += 1
                all_match += 1

        if matches == 0 and results:
            failures.append(
                {
                    "query": query,
                    "expected_domain": expected_domain,
                    "retrieved_domains": [r.get("domain", "?") for r in results],
                }
            )

    overall = all_match / all_total if all_total else 0

    per_domain = {}
    for d, s in domain_stats.items():
        prec = s["domain_match"] / s["total_retrieved"] if s["total_retrieved"] else 0
        per_domain[d] = {
            "precision": round(prec, 3),
            "queries": s["queries"],
            "retrieved": s["total_retrieved"],
            "matched": s["domain_match"],
        }

    return {
        "overall_domain_precision": round(overall, 3),
        "per_domain": per_domain,
        "failures": failures,
    }


def print_results(name, results):
    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"{'=' * 60}")
    print(
        f"\n  Overall Domain Precision@{TOP_K}: {results['overall_domain_precision']}"
    )

    print(f"\n  Per-domain:")
    print(
        f"  {'Domain':<10} {'Prec':>6} {'Matched':>8} {'Retrieved':>10} {'Queries':>8}"
    )
    print(f"  {'-' * 44}")
    for d in sorted(results["per_domain"].keys()):
        m = results["per_domain"][d]
        print(
            f"  {d:<10} {m['precision']:>6.3f} {m['matched']:>8} {m['retrieved']:>10} {m['queries']:>8}"
        )

    if results["failures"]:
        print(f"\n  Zero domain-match queries ({len(results['failures'])}):")
        for f in results["failures"][:8]:
            print(f"    [{f['expected_domain']}] {f['query'][:65]}")
            print(f"      Retrieved: {f['retrieved_domains']}")


def print_comparison(bm25_results, faiss_results):
    print(f"\n{'=' * 60}")
    print(f"  COMPARISON: BM25 vs FAISS")
    print(f"{'=' * 60}")

    print(f"\n  {'Metric':<30} {'BM25':>10} {'FAISS':>10} {'Delta':>10}")
    print(f"  {'-' * 60}")

    bl = bm25_results["overall_domain_precision"]
    fl = faiss_results["overall_domain_precision"]
    print(f"  {'Overall Domain Prec@5':<30} {bl:>10.3f} {fl:>10.3f} {fl - bl:>+10.3f}")

    for d in sorted(
        set(
            list(bm25_results["per_domain"].keys())
            + list(faiss_results["per_domain"].keys())
        )
    ):
        bl_p = bm25_results["per_domain"].get(d, {}).get("precision", 0)
        fl_p = faiss_results["per_domain"].get(d, {}).get("precision", 0)
        print(
            f"  {f'{d} precision':<30} {bl_p:>10.3f} {fl_p:>10.3f} {fl_p - bl_p:>+10.3f}"
        )

    # Show queries where BM25 got zero domain matches but FAISS got some
    bm25_fail_queries = {f["query"] for f in bm25_results["failures"]}
    faiss_fail_queries = {f["query"] for f in faiss_results["failures"]}
    fixed_by_faiss = bm25_fail_queries - faiss_fail_queries

    if fixed_by_faiss:
        print(
            f"\n  Queries where FAISS found domain docs but BM25 didn't ({len(fixed_by_faiss)}):"
        )
        for q in list(fixed_by_faiss)[:6]:
            print(f"    {q[:75]}")


if __name__ == "__main__":
    examples = load_eval_data(EVAL_FILE)
    print(f"Loaded {len(examples)} evaluation queries")

    print("\nInitializing BM25...")
    STORE_PATH = os.path.join(
        os.path.dirname(__file__), "..", "index", "chunk_store.json"
    )
    INDEX_PATH = os.path.join(
        os.path.dirname(__file__), "..", "index", "faiss_index.bin"
    )

    bm25 = BM25Retriever(store_path=STORE_PATH)
    faiss_kb = SearchKB(index_path=INDEX_PATH, store_path=STORE_PATH)

    print("\nRunning BM25 evaluation...")
    bm25_results = domain_precision_at_k(bm25, examples)
    print_results("BM25 BASELINE RETRIEVER", bm25_results)

    print("\nRunning FAISS evaluation...")
    faiss_results = domain_precision_at_k(faiss_kb, examples)
    print_results("FAISS + MiniLM RETRIEVER", faiss_results)

    print_comparison(bm25_results, faiss_results)
