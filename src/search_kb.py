"""
SearchKB Tool — FAISS-backed retrieval for ShramikSaathi
"""

import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer


class SearchKB:
    def __init__(
        self,
        index_path="../index/faiss_index.bin",
        store_path="../index/chunk_store.json",
        model_name="all-MiniLM-L6-v2",
    ):
        print(f"Loading FAISS index from {index_path} ...")
        self.index = faiss.read_index(index_path)

        print(f"Loading chunk store from {store_path} ...")
        with open(store_path, encoding="utf-8") as f:
            self.chunks = json.load(f)

        print(f"Loading encoder: {model_name} ...")
        self.encoder = SentenceTransformer(model_name)

        print(f"SearchKB ready: {self.index.ntotal} chunks indexed.")

    def search(self, query, top_k=4):
        q_emb = self.encoder.encode([query])
        q_emb = np.array(q_emb, dtype="float32")

        distances, indices = self.index.search(q_emb, top_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[idx]
            results.append(
                {
                    "doc_id": chunk["doc_id"],
                    "chunk_id": chunk.get("chunk_id", ""),
                    "title": chunk.get("title", ""),
                    "content": chunk["content"],
                    "source_url": chunk.get("source_url", ""),
                    "effective_date": chunk.get("effective_date"),
                    "supersedes": chunk.get("supersedes"),
                    "domain": chunk.get("domain", ""),
                    "subdomain": chunk.get("subdomain", ""),
                    "conditions": chunk.get("conditions", []),
                    "forms": chunk.get("forms", []),
                    "score": float(dist),
                }
            )

        return self._rerank_by_date(results)

    def _rerank_by_date(self, results: list[dict]) -> list[dict]:
        """
        Post-retrieval re-ranker.

        Two rules:
        1. If a chunk is superseded by another chunk already in the results,
           drop the older one — the newer one is present and sufficient.
        2. Sort remaining results by effective_date descending so the most
           recent policy always appears first.
        """
        if not results:
            return results

        # doc_ids present in this result set
        result_ids = {r["doc_id"] for r in results}

        # Find which doc_ids are explicitly superseded by something in results
        superseded_by_result = set()
        for r in results:
            if r.get("supersedes") and r["supersedes"] in result_ids:
                superseded_by_result.add(r["supersedes"])

        # Drop superseded chunks
        filtered = [r for r in results if r["doc_id"] not in superseded_by_result]

        # Sort by effective_date descending (most recent first)
        filtered.sort(
            key=lambda r: r.get("effective_date") or "1900-01-01", reverse=True
        )

        return filtered

    def format_for_prompt(self, results):
        parts = []
        for i, r in enumerate(results):
            parts.append(
                f"[Source {i+1}] doc_id={r['doc_id']} | "
                f"date={r['effective_date']} | domain={r['domain']}\n"
                f"{r['content'][:1500]}"
            )
        return "\n\n---\n\n".join(parts)
