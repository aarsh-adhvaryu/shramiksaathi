"""
ShramikSaathi — Retriever Fine-tuning
Fine-tunes all-MiniLM-L6-v2 on domain-specific (query, positive, hard_negative) triplets.
Rebuilds FAISS index with fine-tuned encoder.
Re-runs retriever eval to show improvement.

Run: python scripts/finetune_retriever.py
"""

import os, sys, json, re, random, time
from pathlib import Path
from collections import defaultdict

import numpy as np
import torch
from sentence_transformers import SentenceTransformer, InputExample, losses, evaluation
from torch.utils.data import DataLoader
from rank_bm25 import BM25Okapi
import faiss

ROOT = Path(__file__).resolve().parent.parent
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

SFT_PATH = ROOT / "data" / "sft_train.jsonl"
DPO_PATH = ROOT / "data" / "dpo_pairs.jsonl"
KB_PATH = ROOT / "data" / "kb.jsonl"
EVAL_PATH = ROOT / "data" / "eval_heldout.jsonl"
OUT_MODEL = ROOT / "out" / "retriever_finetuned"
OUT_INDEX = ROOT / "index" / "faiss_index_finetuned.bin"
OUT_RESULTS = ROOT / "data" / "retriever_finetune_results.json"

TOP_K = 5


def load_kb():
    kb = {}
    kb_list = []
    with open(KB_PATH) as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                kb[d["doc_id"]] = d
                kb_list.append(d)
    return kb, kb_list


def extract_training_pairs():
    """Extract (query, positive_doc_ids) from SFT and DPO datasets."""
    pairs = []

    # From SFT data
    if SFT_PATH.exists():
        with open(SFT_PATH) as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                fp = row.get("full_prompt", "") or row.get("prompt", "") or ""
                query, doc_ids = parse_prompt(fp)
                if query and doc_ids:
                    pairs.append({"query": query, "doc_ids": doc_ids, "source": "sft"})

    # From DPO data
    if DPO_PATH.exists():
        with open(DPO_PATH) as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                fp = row.get("full_prompt", "") or row.get("prompt", "") or ""
                query, doc_ids = parse_prompt(fp)
                if query and doc_ids:
                    pairs.append({"query": query, "doc_ids": doc_ids, "source": "dpo"})

    # Deduplicate by query
    seen = set()
    unique = []
    for p in pairs:
        q = p["query"].strip().lower()[:100]
        if q not in seen:
            seen.add(q)
            unique.append(p)

    return unique


def parse_prompt(full_prompt):
    """Extract query and doc_ids from a full prompt string."""
    query = None
    doc_ids = []

    # Extract query
    m = re.search(r'USER QUERY:\n(.+?)(?:\n\n|\nDOMAIN)', full_prompt, re.DOTALL)
    if m:
        query = m.group(1).strip()
    else:
        m = re.search(r'(?:query|question)[:\s]+(.+?)(?:\n\n|\n[A-Z])', full_prompt, re.IGNORECASE | re.DOTALL)
        if m:
            query = m.group(1).strip()

    # Extract doc_ids from passages
    doc_ids = re.findall(r'doc_id=([A-Z][A-Z0-9_]+(?:_chunk_\d+)?)', full_prompt)
    # Also try bracket format
    doc_ids += re.findall(r'\[([A-Z][A-Z0-9_]+(?:_chunk_\d+)?)\]', full_prompt)
    doc_ids = list(set(d for d in doc_ids if d != "TOOL_PAYSLIP_AUDIT"))

    return query, doc_ids


def build_triplets(pairs, kb, kb_list):
    """Build (query, positive_passage, hard_negative) triplets."""
    print("[Data] Building triplets with hard negatives...")

    # BM25 for hard negative mining
    doc_id_list = [d["doc_id"] for d in kb_list]
    tokenized = [d["content"].lower().split() for d in kb_list]
    bm25 = BM25Okapi(tokenized)

    triplets = []
    for p in pairs:
        query = p["query"]
        pos_ids = set(p["doc_ids"])

        # Get positive passages
        positives = []
        for did in pos_ids:
            if did in kb:
                positives.append(kb[did]["content"][:512])

        if not positives:
            continue

        # Hard negatives: BM25 top results that are NOT positive
        tokens = query.lower().split()
        scores = bm25.get_scores(tokens)
        ranked = np.argsort(scores)[::-1]

        negatives = []
        for idx in ranked:
            if doc_id_list[idx] not in pos_ids:
                negatives.append(kb_list[idx]["content"][:512])
                if len(negatives) >= 3:
                    break

        if not negatives:
            continue

        # Create triplets: each positive paired with each hard negative
        for pos in positives:
            for neg in negatives[:2]:
                triplets.append((query, pos, neg))

    random.shuffle(triplets)
    return triplets


def finetune(triplets):
    """Fine-tune all-MiniLM-L6-v2 with manual triplet loss training."""
    from torch.nn import TripletMarginLoss
    from torch.optim import AdamW
    from torch.optim.lr_scheduler import CosineAnnealingLR

    print("[Train] Loading base encoder...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    n_val = max(10, int(len(triplets) * 0.1))
    train_triplets = triplets[n_val:]
    print("[Train] " + str(len(train_triplets)) + " train triplets")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)

    optimizer = AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)
    loss_fn = TripletMarginLoss(margin=0.3)
    epochs = 3
    batch_size = 16
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs * (len(train_triplets) // batch_size + 1))

    print("[Train] Fine-tuning for " + str(epochs) + " epochs on " + str(device) + "...")
    t0 = time.time()
    model.train()

    for epoch in range(epochs):
        random.shuffle(train_triplets)
        total_loss = 0
        n_batches = 0

        for i in range(0, len(train_triplets), batch_size):
            batch = train_triplets[i:i+batch_size]
            queries = [t[0] for t in batch]
            positives = [t[1] for t in batch]
            negatives = [t[2] for t in batch]

            def embed(texts):
                tok = model.tokenize(texts)
                tok = {k: v.to(device) for k, v in tok.items() if hasattr(v, "to")}
                out = model(tok)
                return out["sentence_embedding"]

            q_emb = embed(queries)
            p_emb = embed(positives)
            n_emb = embed(negatives)

            loss = loss_fn(q_emb, p_emb, n_emb)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            scheduler.step()

            total_loss += loss.item()
            n_batches += 1

        avg_loss = total_loss / max(n_batches, 1)
        print("  Epoch " + str(epoch+1) + "/" + str(epochs) + " | loss=" + str(round(avg_loss, 4)))

    dt = time.time() - t0
    print("[Train] Done in " + str(round(dt / 60, 1)) + " min")

    OUT_MODEL.mkdir(parents=True, exist_ok=True)
    model.save(str(OUT_MODEL))
    print("[Train] Saved to " + str(OUT_MODEL))

    return model


def build_index(model, kb_list):
    """Build FAISS index with fine-tuned encoder."""
    print("[Index] Encoding " + str(len(kb_list)) + " documents...")
    texts = [d["content"][:512] for d in kb_list]
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=False)
    embeddings = embeddings.astype("float32")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    faiss.write_index(index, str(OUT_INDEX))
    print("[Index] Saved " + str(OUT_INDEX) + " (" + str(index.ntotal) + " vectors, dim=" + str(dim) + ")")
    return index


def evaluate(orig_model_name, finetuned_model, kb_list):
    """Compare original vs fine-tuned retriever on held-out prompts."""
    prompts = [json.loads(l) for l in open(EVAL_PATH) if l.strip()]
    kb_dict = {d["doc_id"]: d for d in kb_list}
    doc_id_list = [d["doc_id"] for d in kb_list]

    # Original encoder + index
    print("\n[Eval] Loading original encoder...")
    orig_model = SentenceTransformer(orig_model_name)
    orig_index = faiss.read_index(str(ROOT / "index" / "faiss_index.bin"))

    # Fine-tuned index
    ft_index = faiss.read_index(str(OUT_INDEX))

    results = {"original": [], "finetuned": []}

    for p in prompts:
        gold = set(d for d in p["passage_doc_ids"] if d != "TOOL_PAYSLIP_AUDIT")
        if not gold:
            continue

        query = p["query"]

        # Original
        q_orig = orig_model.encode([query], normalize_embeddings=False).astype("float32")
        _, orig_idx = orig_index.search(q_orig, TOP_K)
        orig_retrieved = [doc_id_list[i] for i in orig_idx[0] if i < len(doc_id_list)]
        orig_recall = len(set(orig_retrieved) & gold) / len(gold)
        orig_mrr = 0.0
        for rank, d in enumerate(orig_retrieved, 1):
            if d in gold:
                orig_mrr = 1.0 / rank
                break
        results["original"].append({"id": p["id"], "recall": orig_recall, "mrr": orig_mrr, "retrieved": orig_retrieved})

        # Fine-tuned
        q_ft = finetuned_model.encode([query], normalize_embeddings=False).astype("float32")
        _, ft_idx = ft_index.search(q_ft, TOP_K)
        ft_retrieved = [doc_id_list[i] for i in ft_idx[0] if i < len(doc_id_list)]
        ft_recall = len(set(ft_retrieved) & gold) / len(gold)
        ft_mrr = 0.0
        for rank, d in enumerate(ft_retrieved, 1):
            if d in gold:
                ft_mrr = 1.0 / rank
                break
        results["finetuned"].append({"id": p["id"], "recall": ft_recall, "mrr": ft_mrr, "retrieved": ft_retrieved})

    # Summary
    n = len(results["original"])
    orig_recall_mean = sum(r["recall"] for r in results["original"]) / n
    orig_mrr_mean = sum(r["mrr"] for r in results["original"]) / n
    ft_recall_mean = sum(r["recall"] for r in results["finetuned"]) / n
    ft_mrr_mean = sum(r["mrr"] for r in results["finetuned"]) / n

    print("")
    print("=" * 60)
    print("RETRIEVER FINE-TUNING RESULTS (n=" + str(n) + ")")
    print("=" * 60)
    print("Metric          Original    Fine-tuned    Delta")
    print("-" * 55)
    print("Recall@5        " + str(round(orig_recall_mean, 3)).ljust(12) + str(round(ft_recall_mean, 3)).ljust(14) + str(round(ft_recall_mean - orig_recall_mean, 3)))
    print("MRR@5           " + str(round(orig_mrr_mean, 3)).ljust(12) + str(round(ft_mrr_mean, 3)).ljust(14) + str(round(ft_mrr_mean - orig_mrr_mean, 3)))

    # Also compare against BM25
    bm25_tokenized = [d["content"].lower().split() for d in kb_list]
    bm25 = BM25Okapi(bm25_tokenized)
    bm25_results = []
    for p in prompts:
        gold = set(d for d in p["passage_doc_ids"] if d != "TOOL_PAYSLIP_AUDIT")
        if not gold:
            continue
        tokens = p["query"].lower().split()
        scores = bm25.get_scores(tokens)
        top_idx = np.argsort(scores)[::-1][:TOP_K]
        retrieved = [doc_id_list[i] for i in top_idx]
        recall = len(set(retrieved) & gold) / len(gold)
        mrr = 0.0
        for rank, d in enumerate(retrieved, 1):
            if d in gold:
                mrr = 1.0 / rank
                break
        bm25_results.append({"recall": recall, "mrr": mrr})

    bm25_recall = sum(r["recall"] for r in bm25_results) / len(bm25_results)
    bm25_mrr = sum(r["mrr"] for r in bm25_results) / len(bm25_results)

    print("")
    print("Full comparison:")
    print("             BM25        Original    Fine-tuned")
    print("Recall@5     " + str(round(bm25_recall, 3)).ljust(12) + str(round(orig_recall_mean, 3)).ljust(12) + str(round(ft_recall_mean, 3)))
    print("MRR@5        " + str(round(bm25_mrr, 3)).ljust(12) + str(round(orig_mrr_mean, 3)).ljust(12) + str(round(ft_mrr_mean, 3)))

    out = {
        "n_prompts": n,
        "bm25": {"recall_at_5": round(bm25_recall, 3), "mrr_at_5": round(bm25_mrr, 3)},
        "original": {"recall_at_5": round(orig_recall_mean, 3), "mrr_at_5": round(orig_mrr_mean, 3)},
        "finetuned": {"recall_at_5": round(ft_recall_mean, 3), "mrr_at_5": round(ft_mrr_mean, 3)},
        "per_query": results,
    }
    with open(OUT_RESULTS, "w") as f:
        json.dump(out, f, indent=2)
    print("\n[Save] " + str(OUT_RESULTS))

    return out


def main():
    print("=" * 60)
    print("ShramikSaathi — Retriever Fine-tuning")
    print("=" * 60)

    kb, kb_list = load_kb()
    print("[Data] " + str(len(kb)) + " KB documents")

    # Step 1: Extract training pairs
    pairs = extract_training_pairs()
    print("[Data] Extracted " + str(len(pairs)) + " unique (query, doc_ids) pairs")

    # Step 2: Build triplets with hard negatives
    triplets = build_triplets(pairs, kb, kb_list)
    print("[Data] " + str(len(triplets)) + " training triplets")

    if len(triplets) < 20:
        print("[!] Too few triplets. Check data extraction.")
        return

    # Step 3: Fine-tune
    model = finetune(triplets)

    # Step 4: Build new FAISS index
    build_index(model, kb_list)

    # Step 5: Evaluate
    evaluate("all-MiniLM-L6-v2", model, kb_list)

    print("")
    print("=" * 60)
    print("Done. Fine-tuned retriever saved to " + str(OUT_MODEL))
    print("New FAISS index at " + str(OUT_INDEX))
    print("=" * 60)


if __name__ == "__main__":
    main()