"""
Vanilla RAG Baseline Pipeline — BM25 + raw LLaMA, no intelligence.
This is Configuration 1 in the ablation table (Section 5.4).

query → BM25 keyword search → raw LLaMA generates answer

No router, no slot extraction, no sufficiency gate, no eligibility reasoner,
no tools, no domain awareness. This is what every basic RAG chatbot does.

STRICTLY FOR COMPARISON — never deployed.

Path-agnostic: works from project root or src/.
"""

import os
import sys
import json
import time
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Path-agnostic imports ─────────────────────────────────────────────────────
_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from bm25_retriever import BM25Retriever

# ── Resolve BM25 store path relative to project root ─────────────────────────
_PROJECT_ROOT = _SRC_DIR.parent
_STORE_PATH = _PROJECT_ROOT / "index" / "chunk_store.json"

bm25 = BM25Retriever(store_path=str(_STORE_PATH))

# ── Raw generator prompt — no structure, no domain awareness ───────────────────

BASELINE_PROMPT = """You are a helpful assistant that answers questions about Indian worker rights, PF, payslip, labour law, and income tax.

You will be given some reference passages. Answer the user's question based on those passages.

RULES:
- Use the information from the passages to answer.
- If the passages don't contain enough information, say so.
- Cite sources using their doc_id when possible."""


# ── Groq call with retry ──────────────────────────────────────────────────────

def _groq_call(messages, temperature=0.2, max_tokens=800):
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                wait = 5 * (attempt + 1)
                print(f"[Baseline] Rate limited — waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    return "[Error: rate limit exceeded]"


# ── Baseline pipeline ─────────────────────────────────────────────────────────

def run_baseline(user_query: str) -> dict:
    """Vanilla RAG: query → BM25 retrieve → raw LLaMA generate."""
    passages = bm25.search(user_query, top_k=5)
    passages_text = bm25.format_for_prompt(passages)

    user_content = f"""USER QUERY:
{user_query}

RETRIEVED PASSAGES:
{passages_text}

Answer the question based on the passages above."""

    answer = _groq_call([
        {"role": "system", "content": BASELINE_PROMPT},
        {"role": "user", "content": user_content},
    ])

    return {
        "response": answer,
        "passages": passages,
        "retriever": "bm25",
        "pipeline": "vanilla_rag",
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("VANILLA RAG BASELINE (BM25 + Raw LLaMA)")
    print("No router, no slots, no gate, no reasoner, no tools")
    print("=" * 60)

    test_queries = [
        "I left my job 3 months ago. My UAN is active and KYC is done. I want to withdraw my full PF balance.",
        "My basic salary is 20000 and employer is deducting 1800 as EPF. Is this correct?",
        "I resigned after working 6 years. My last drawn salary was 35000. Am I eligible for gratuity?",
        "Income is 12 lakh, old regime, paying rent 18000 per month in Mumbai. How much HRA exemption?",
        "mera PF nikalna hai job chhod diya 3 mahine ho gaye",
    ]

    for q in test_queries:
        print(f"\n{'─' * 60}")
        print(f"Query: {q}")
        print(f"{'─' * 60}")

        result = run_baseline(q)

        print(f"\nRetrieved: {[p['doc_id'] for p in result['passages']]}")
        print(f"\nBaseline Answer:\n{result['response']}")
        print(f"\n[Pipeline: {result['pipeline']} | Retriever: {result['retriever']}]")

        time.sleep(3)  # rate limit buffer
