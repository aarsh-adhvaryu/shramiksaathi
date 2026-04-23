"""
FAISS Index Builder — builds vector index from merged multi-domain kb.jsonl
Run from src/: python build_faiss_index.py
"""

import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from pathlib import Path


# ─── Config ────────────────────────────────────────────────────────
ENCODER_MODEL = "all-MiniLM-L6-v2"
KB_JSONL = "../data/kb.jsonl"
INDEX_OUT = "../index/faiss_index.bin"
STORE_OUT = "../index/chunk_store.json"


# ─── Load chunks ──────────────────────────────────────────────────
def load_chunks():
    chunks = []

    if not Path(KB_JSONL).exists():
        print(f"ERROR: {KB_JSONL} not found. Run scripts/merge_kb.py first.")
        return chunks

    with open(KB_JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                doc = json.loads(line)
                # Ensure minimum required fields
                if doc.get("content") and len(doc["content"]) > 10:
                    chunks.append(doc)

    print(f"  Loaded {len(chunks)} chunks from {KB_JSONL}")

    # Domain distribution
    from collections import Counter
    dist = Counter(c.get("domain", "?") for c in chunks)
    for domain, count in sorted(dist.items()):
        print(f"    {domain}: {count}")

    return chunks


# ─── Encode with MiniLM ───────────────────────────────────────────
def build_index(chunks):
    print(f"\nTotal chunks to index: {len(chunks)}")

    print(f"Loading encoder: {ENCODER_MODEL} ...")
    encoder = SentenceTransformer(ENCODER_MODEL)

    # Combine title + content for richer embeddings
    texts = []
    for c in chunks:
        title = c.get("title", "")
        content = c.get("content", "")
        combined = f"{title}: {content}" if title else content
        # Truncate to ~500 words to stay within model limits
        words = combined.split()[:500]
        texts.append(" ".join(words))

    print("Encoding chunks ...")
    embeddings = encoder.encode(texts, show_progress_bar=True, batch_size=64)
    embeddings = np.array(embeddings, dtype="float32")
    print(f"Embedding shape: {embeddings.shape}")

    # Build FAISS index
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    print(f"FAISS index built: {index.ntotal} vectors, dim={dim}")

    return index, chunks, encoder


# ─── Save to disk ─────────────────────────────────────────────────
def save(index, chunks):
    Path(INDEX_OUT).parent.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, INDEX_OUT)
    print(f"Saved FAISS index → {INDEX_OUT}")

    with open(STORE_OUT, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)
    print(f"Saved chunk store → {STORE_OUT} ({len(chunks)} entries)")


# ─── Test queries ─────────────────────────────────────────────────
def test_query(index, chunks, encoder, query, top_k=3):
    q_emb = encoder.encode([query])
    q_emb = np.array(q_emb, dtype="float32")
    distances, indices = index.search(q_emb, top_k)

    print(f'\nQuery: "{query}"')
    for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
        c = chunks[idx]
        preview = c["content"][:100].replace("\n", " ")
        print(
            f"  [{rank+1}] dist={dist:.2f} | doc_id={c.get('doc_id','?')} | domain={c.get('domain','?')}"
        )
        print(f"       {preview}...")


# ─── Main ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    chunks = load_chunks()
    if not chunks:
        exit(1)

    index, chunks, encoder = build_index(chunks)
    save(index, chunks)

    print("\n" + "=" * 60)
    print("TEST QUERIES — cross-domain")
    print("=" * 60)

    # PF
    test_query(index, chunks, encoder, "How to withdraw PF after leaving job?")
    # Payslip
    test_query(index, chunks, encoder, "Is my ESI deduction correct if gross salary is 20000?")
    # Labour
    test_query(index, chunks, encoder, "Gratuity eligibility after 5 years of service")
    # Tax
    test_query(index, chunks, encoder, "HRA exemption calculation under section 10(13A)")

    print("\nDone. Files saved:")
    print(f"   {INDEX_OUT}")
    print(f"   {STORE_OUT}")
