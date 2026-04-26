"""
RAGAS-style Evaluation: Faithfulness + Answer Relevance
Uses Groq LLaMA as judge LLM (no OpenAI dependency).
Compares SFT-only vs DPO winner from dpo_eval_results.json.
"""
import os, sys, json, time, re
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DPO_EVAL_PATH = ROOT / "data" / "dpo_eval_results.json"
KB_PATH       = ROOT / "data" / "kb.jsonl"
OUT_PATH      = ROOT / "data" / "ragas_eval_results.json"

SYSTEMS_TO_EVAL = ["sft_only", "dpo_beta_0.05"]  # baseline vs winner

FAITHFULNESS_PROMPT = """You are an evaluation judge. Score the FAITHFULNESS of the assistant's response.

Faithfulness = are ALL factual claims in the response supported by the provided passages?

PASSAGES:
{passages}

RESPONSE:
{response}

Score on a scale of 1-5:
  1 = Most claims are unsupported or fabricated
  2 = Several claims lack passage support
  3 = Some claims supported, some not
  4 = Most claims supported by passages
  5 = All claims are directly supported by passages

Reply with ONLY a JSON object: {{"score": <1-5>, "reason": "<one sentence>"}}"""

RELEVANCE_PROMPT = """You are an evaluation judge. Score the ANSWER RELEVANCE of the response.

Answer Relevance = does the response directly and completely address the user's question?

USER QUERY:
{query}

RESPONSE:
{response}

Score on a scale of 1-5:
  1 = Response is irrelevant or off-topic
  2 = Partially addresses the query, misses key aspects
  3 = Addresses the main query but incomplete
  4 = Addresses the query well with minor gaps
  5 = Fully and directly addresses every aspect of the query

Reply with ONLY a JSON object: {{"score": <1-5>, "reason": "<one sentence>"}}"""


def groq_judge(prompt_text):
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt_text}],
                temperature=0.0, max_tokens=150,
            )
            text = resp.choices[0].message.content.strip()
            # Extract JSON from response
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"score": 3, "reason": "parse_error"}
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                time.sleep(5 * (attempt + 1))
            else:
                return {"score": 3, "reason": f"error: {str(e)[:50]}"}
    return {"score": 3, "reason": "rate_limit_exhausted"}


def load_kb():
    kb = {}
    with open(KB_PATH) as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                kb[d["doc_id"]] = d
    return kb


def get_passages_text(prompt, kb):
    parts = []
    for did in prompt.get("passage_doc_ids", []):
        if did in kb:
            parts.append(f"[{did}] {kb[did]['content'][:500]}")
        elif did == "TOOL_PAYSLIP_AUDIT":
            parts.append(f"[TOOL_PAYSLIP_AUDIT] Payslip calculation tool output")
    return "\n---\n".join(parts)


def main():
    print("=" * 60)
    print("RAGAS-style Eval: Faithfulness + Answer Relevance")
    print("=" * 60)

    with open(DPO_EVAL_PATH) as f:
        dpo_eval = json.load(f)

    prompts = dpo_eval["prompts"]
    kb = load_kb()
    print(f"[Data] {len(prompts)} prompts | Systems: {SYSTEMS_TO_EVAL}")

    all_scores = {}

    for sys_label in SYSTEMS_TO_EVAL:
        print(f"\n[Eval] Scoring {sys_label}...")
        sys_results = dpo_eval["all_results"][sys_label]
        scores = []

        for i, prompt in enumerate(prompts, 1):
            result = next(r for r in sys_results if r["prompt_id"] == prompt["id"])
            response = result["response"]
            passages_text = get_passages_text(prompt, kb)

            # Faithfulness
            faith_result = groq_judge(
                FAITHFULNESS_PROMPT.format(passages=passages_text, response=response)
            )
            time.sleep(1)  # rate limit

            # Answer Relevance
            rel_result = groq_judge(
                RELEVANCE_PROMPT.format(query=prompt["query"], response=response)
            )
            time.sleep(1)

            faith_score = faith_result.get("score", 3) / 5.0  # normalize to 0-1
            rel_score = rel_result.get("score", 3) / 5.0

            scores.append({
                "prompt_id": prompt["id"],
                "domain": prompt["domain"],
                "faithfulness": round(faith_score, 2),
                "faithfulness_reason": faith_result.get("reason", ""),
                "answer_relevance": round(rel_score, 2),
                "relevance_reason": rel_result.get("reason", ""),
            })
            print(f"  [{i}/{len(prompts)}] {prompt['id']}  faith={faith_score:.2f}  rel={rel_score:.2f}")

        all_scores[sys_label] = scores

    # ── Summary ──
    print(f"\n{'=' * 60}")
    print(f"  RAGAS RESULTS")
    print(f"{'=' * 60}")

    summaries = {}
    for sys_label, scores in all_scores.items():
        n = len(scores)
        mean_faith = sum(s["faithfulness"] for s in scores) / n
        mean_rel = sum(s["answer_relevance"] for s in scores) / n
        summaries[sys_label] = {
            "faithfulness": round(mean_faith, 3),
            "answer_relevance": round(mean_rel, 3),
        }

    header = f"  {'Metric':<22}" + "".join(f"{k:>15}" for k in SYSTEMS_TO_EVAL)
    print(header)
    for metric in ["faithfulness", "answer_relevance"]:
        row = f"  {metric:<22}"
        for sys_label in SYSTEMS_TO_EVAL:
            row += f"{summaries[sys_label][metric]:>15.3f}"
        print(row)

    # Per-domain
    print(f"\n  Per-domain faithfulness:")
    for dom in ["pf", "payslip", "labour", "tax"]:
        row = f"  {dom:<10}"
        for sys_label in SYSTEMS_TO_EVAL:
            dom_scores = [s for s in all_scores[sys_label] if s["domain"] == dom]
            if dom_scores:
                dm = sum(s["faithfulness"] for s in dom_scores) / len(dom_scores)
                row += f"{dm:>15.3f}"
            else:
                row += f"{'n/a':>15}"
        print(row)

    # Delta
    if len(SYSTEMS_TO_EVAL) == 2:
        s1, s2 = SYSTEMS_TO_EVAL
        print(f"\n  Delta ({s2} vs {s1}):")
        for metric in ["faithfulness", "answer_relevance"]:
            d = summaries[s2][metric] - summaries[s1][metric]
            print(f"    {metric}: {d:+.3f}")

    out = {
        "systems": SYSTEMS_TO_EVAL,
        "summaries": summaries,
        "all_scores": all_scores,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n[Save] {OUT_PATH}")


if __name__ == "__main__":
    main()
PYEOFcat > eval/ragas_eval_runner.py << 'PYEOF'
"""
RAGAS-style Evaluation: Faithfulness + Answer Relevance
Uses Groq LLaMA as judge LLM (no OpenAI dependency).
Compares SFT-only vs DPO winner from dpo_eval_results.json.
"""
import os, sys, json, time, re
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DPO_EVAL_PATH = ROOT / "data" / "dpo_eval_results.json"
KB_PATH       = ROOT / "data" / "kb.jsonl"
OUT_PATH      = ROOT / "data" / "ragas_eval_results.json"

SYSTEMS_TO_EVAL = ["sft_only", "dpo_beta_0.05"]  # baseline vs winner

FAITHFULNESS_PROMPT = """You are an evaluation judge. Score the FAITHFULNESS of the assistant's response.

Faithfulness = are ALL factual claims in the response supported by the provided passages?

PASSAGES:
{passages}

RESPONSE:
{response}

Score on a scale of 1-5:
  1 = Most claims are unsupported or fabricated
  2 = Several claims lack passage support
  3 = Some claims supported, some not
  4 = Most claims supported by passages
  5 = All claims are directly supported by passages

Reply with ONLY a JSON object: {{"score": <1-5>, "reason": "<one sentence>"}}"""

RELEVANCE_PROMPT = """You are an evaluation judge. Score the ANSWER RELEVANCE of the response.

Answer Relevance = does the response directly and completely address the user's question?

USER QUERY:
{query}

RESPONSE:
{response}

Score on a scale of 1-5:
  1 = Response is irrelevant or off-topic
  2 = Partially addresses the query, misses key aspects
  3 = Addresses the main query but incomplete
  4 = Addresses the query well with minor gaps
  5 = Fully and directly addresses every aspect of the query

Reply with ONLY a JSON object: {{"score": <1-5>, "reason": "<one sentence>"}}"""


def groq_judge(prompt_text):
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt_text}],
                temperature=0.0, max_tokens=150,
            )
            text = resp.choices[0].message.content.strip()
            # Extract JSON from response
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"score": 3, "reason": "parse_error"}
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                time.sleep(5 * (attempt + 1))
            else:
                return {"score": 3, "reason": f"error: {str(e)[:50]}"}
    return {"score": 3, "reason": "rate_limit_exhausted"}


def load_kb():
    kb = {}
    with open(KB_PATH) as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                kb[d["doc_id"]] = d
    return kb


def get_passages_text(prompt, kb):
    parts = []
    for did in prompt.get("passage_doc_ids", []):
        if did in kb:
            parts.append(f"[{did}] {kb[did]['content'][:500]}")
        elif did == "TOOL_PAYSLIP_AUDIT":
            parts.append(f"[TOOL_PAYSLIP_AUDIT] Payslip calculation tool output")
    return "\n---\n".join(parts)


def main():
    print("=" * 60)
    print("RAGAS-style Eval: Faithfulness + Answer Relevance")
    print("=" * 60)

    with open(DPO_EVAL_PATH) as f:
        dpo_eval = json.load(f)

    prompts = dpo_eval["prompts"]
    kb = load_kb()
    print(f"[Data] {len(prompts)} prompts | Systems: {SYSTEMS_TO_EVAL}")

    all_scores = {}

    for sys_label in SYSTEMS_TO_EVAL:
        print(f"\n[Eval] Scoring {sys_label}...")
        sys_results = dpo_eval["all_results"][sys_label]
        scores = []

        for i, prompt in enumerate(prompts, 1):
            result = next(r for r in sys_results if r["prompt_id"] == prompt["id"])
            response = result["response"]
            passages_text = get_passages_text(prompt, kb)

            # Faithfulness
            faith_result = groq_judge(
                FAITHFULNESS_PROMPT.format(passages=passages_text, response=response)
            )
            time.sleep(1)  # rate limit

            # Answer Relevance
            rel_result = groq_judge(
                RELEVANCE_PROMPT.format(query=prompt["query"], response=response)
            )
            time.sleep(1)

            faith_score = faith_result.get("score", 3) / 5.0  # normalize to 0-1
            rel_score = rel_result.get("score", 3) / 5.0

            scores.append({
                "prompt_id": prompt["id"],
                "domain": prompt["domain"],
                "faithfulness": round(faith_score, 2),
                "faithfulness_reason": faith_result.get("reason", ""),
                "answer_relevance": round(rel_score, 2),
                "relevance_reason": rel_result.get("reason", ""),
            })
            print(f"  [{i}/{len(prompts)}] {prompt['id']}  faith={faith_score:.2f}  rel={rel_score:.2f}")

        all_scores[sys_label] = scores

    # ── Summary ──
    print(f"\n{'=' * 60}")
    print(f"  RAGAS RESULTS")
    print(f"{'=' * 60}")

    summaries = {}
    for sys_label, scores in all_scores.items():
        n = len(scores)
        mean_faith = sum(s["faithfulness"] for s in scores) / n
        mean_rel = sum(s["answer_relevance"] for s in scores) / n
        summaries[sys_label] = {
            "faithfulness": round(mean_faith, 3),
            "answer_relevance": round(mean_rel, 3),
        }

    header = f"  {'Metric':<22}" + "".join(f"{k:>15}" for k in SYSTEMS_TO_EVAL)
    print(header)
    for metric in ["faithfulness", "answer_relevance"]:
        row = f"  {metric:<22}"
        for sys_label in SYSTEMS_TO_EVAL:
            row += f"{summaries[sys_label][metric]:>15.3f}"
        print(row)

    # Per-domain
    print(f"\n  Per-domain faithfulness:")
    for dom in ["pf", "payslip", "labour", "tax"]:
        row = f"  {dom:<10}"
        for sys_label in SYSTEMS_TO_EVAL:
            dom_scores = [s for s in all_scores[sys_label] if s["domain"] == dom]
            if dom_scores:
                dm = sum(s["faithfulness"] for s in dom_scores) / len(dom_scores)
                row += f"{dm:>15.3f}"
            else:
                row += f"{'n/a':>15}"
        print(row)

    # Delta
    if len(SYSTEMS_TO_EVAL) == 2:
        s1, s2 = SYSTEMS_TO_EVAL
        print(f"\n  Delta ({s2} vs {s1}):")
        for metric in ["faithfulness", "answer_relevance"]:
            d = summaries[s2][metric] - summaries[s1][metric]
            print(f"    {metric}: {d:+.3f}")

    out = {
        "systems": SYSTEMS_TO_EVAL,
        "summaries": summaries,
        "all_scores": all_scores,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n[Save] {OUT_PATH}")


if __name__ == "__main__":
    main()
