from pathlib import Path
from pathlib import Path
from pathlib import Path
from pathlib import Path
"""
Cross-domain ReAct Retrieval Loop with Tools (FINAL)
LLM-driven: Thought → Action(Tool) → Observation → repeat or done.

Tools:
  SearchKB(query)        — semantic search over KB
  GetPolicy(doc_id)      — exact lookup by doc_id
  ParsePayslip()         — deterministic deduction calculator

Returns passages + tool outputs. The pipeline's Reasoner and Generator handle the rest.
"""

import os
import re
import json
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "llama-3.1-8b-instant"
MAX_LOOPS = 3

# ── ReAct system prompt ────────────────────────────────────────────────────────

REACT_PROMPT = """You are a retrieval and computation agent for ShramikSaathi, an Indian worker rights support system.
Your job is to gather information and compute results using the tools below.

You cover 4 domains:
- pf       — PF/EPF/EPFO: withdrawal, transfer, KYC, UAN, pension, employer issues
- payslip  — salary/payslip: EPF deduction, ESI deduction, professional tax, minimum wage
- labour   — labour rights: gratuity, termination, notice period, maternity, overtime
- tax      — income tax: TDS on salary, TDS on PF, HRA exemption, 80C/80D, ITR

You have 3 tools:

SearchKB("query") — semantic search over the knowledge base. Use for finding eligibility rules, Act sections, procedures.
GetPolicy("doc_id") — exact lookup of a specific document by its doc_id. Use when you already know the doc_id from a previous search.
ParsePayslip() — runs a deterministic payslip calculator using the user's salary slots. Use ONLY for payslip domain when the user provides salary/deduction numbers. No arguments needed — it uses the slots automatically.

Follow this EXACT format:

Thought: <what do I need to find or compute?>
Action: SearchKB("EPF Act Section 69 full withdrawal eligibility")

After receiving an Observation, decide next:

Thought: <what did I find? do I need more?>
Action: GetPolicy("EPF_ACT_S68_S69")
OR
Action: ParsePayslip()
OR
Done: I have enough information.

RULES:
1. Do at most 3 tool calls total. After 3, output "Done:".
2. For payslip queries with salary numbers → ALWAYS call ParsePayslip() to get exact calculations. Do NOT compute deductions yourself.
3. For eligibility queries → SearchKB for the relevant Act/Section first.
4. Use GetPolicy only when you need the full text of a specific doc_id you already found.
5. Write targeted SearchKB queries — include Act names, Section numbers, specific terms.
6. Never fabricate Observations. Only respond with Thought/Action or Done.
7. You are gathering information. Do NOT answer the user's question."""


# ── Groq call with retry ──────────────────────────────────────────────────────

def _groq_call(messages, temperature=0.1, max_tokens=300):
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                wait = 5 * (attempt + 1)
                print(f"[ReAct] Rate limited — waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    return None


# ── Parse actions from LLM response ──────────────────────────────────────────

def _parse_action(response_text):
    """
    Parse tool call from LLM output.
    Returns: (tool_name, argument) or (None, None)
    """
    # SearchKB("query")
    match = re.search(r'Action:\s*SearchKB\(["\'](.+?)["\']\)', response_text)
    if match:
        return "SearchKB", match.group(1)

    # GetPolicy("doc_id")
    match = re.search(r'Action:\s*GetPolicy\(["\'](.+?)["\']\)', response_text)
    if match:
        return "GetPolicy", match.group(1)

    # ParsePayslip() — no arguments
    match = re.search(r'Action:\s*ParsePayslip\(\)', response_text)
    if match:
        return "ParsePayslip", None

    return None, None


def _is_done(response_text):
    return "Done:" in response_text


# ── Main ReAct retrieval function ─────────────────────────────────────────────

def react_retrieve(
    user_query: str,
    domain: str,
    intent: str,
    slots: dict,
    kb,
    top_k: int = 4,
) -> list[dict]:
    """
    LLM-driven retrieval and computation using ReAct loop.

    Returns:
        list of passage dicts (same format as kb.search())
        Tool outputs are attached as extra entries with doc_id="TOOL_*"
    """
    # Lazy import to avoid circular imports
    from tools import PolicyStore, parse_payslip, format_payslip_result

    policy_store = PolicyStore(store_path=str(Path(__file__).resolve().parent.parent / "index" / "chunk_store.json"))

    # Build context
    filled = {k: v for k, v in slots.items() if v is not None}
    context = f"Domain: {domain}\nIntent: {intent}\nUser slots: {json.dumps(filled)}\n\nUser query: {user_query}"

    messages = [
        {"role": "system", "content": REACT_PROMPT},
        {"role": "user", "content": context},
    ]

    all_passages = []
    seen_doc_ids = set()
    tool_outputs = []

    for loop_num in range(MAX_LOOPS):
        llm_output = _groq_call(messages, temperature=0.1, max_tokens=300)

        if llm_output is None:
            print(f"[ReAct] Loop {loop_num + 1}: API call failed")
            break

        print(f"[ReAct] Loop {loop_num + 1}: {llm_output[:150]}")

        if _is_done(llm_output):
            print(f"[ReAct] Done after {loop_num + 1} loop(s)")
            break

        tool_name, tool_arg = _parse_action(llm_output)

        if tool_name is None:
            print(f"[ReAct] No action parsed — stopping")
            break

        # ── Execute tool ──────────────────────────────────────────────────
        observation = ""

        if tool_name == "SearchKB":
            print(f'[ReAct] SearchKB("{tool_arg}")')
            results = kb.search(tool_arg, top_k=top_k)

            new_results = []
            for r in results:
                doc_id = r.get("doc_id", "")
                if doc_id not in seen_doc_ids:
                    seen_doc_ids.add(doc_id)
                    new_results.append(r)
                    all_passages.append(r)

            print(f"[ReAct] Got {len(new_results)} new passages (total: {len(all_passages)})")

            obs_parts = []
            for r in new_results:
                obs_parts.append(
                    f"doc_id={r.get('doc_id','?')} | domain={r.get('domain','?')} | "
                    f"subdomain={r.get('subdomain','?')}\n{r.get('content','')[:300]}"
                )
            observation = "\n---\n".join(obs_parts) if obs_parts else "No new results."

        elif tool_name == "GetPolicy":
            print(f'[ReAct] GetPolicy("{tool_arg}")')
            observation = policy_store.get_formatted(tool_arg)

            doc = policy_store.get(tool_arg)
            if doc and tool_arg not in seen_doc_ids:
                seen_doc_ids.add(tool_arg)
                all_passages.append(doc)

        elif tool_name == "ParsePayslip":
            print(f"[ReAct] ParsePayslip()")
            payslip_result = parse_payslip(slots)
            observation = format_payslip_result(payslip_result)

            tool_outputs.append({
                "doc_id": "TOOL_PAYSLIP_AUDIT",
                "title": "Payslip Audit Calculation",
                "content": observation,
                "domain": "payslip",
                "subdomain": "tool_output",
                "effective_date": None,
                "source_url": "deterministic_calculator",
                "conditions": [],
            })
            print(f"[ReAct] Payslip audit computed — {len(payslip_result.get('deductions', []))} deductions checked")

        # Append to conversation
        messages.append({"role": "assistant", "content": llm_output})
        messages.append({"role": "user", "content": f"Observation:\n{observation}"})

    # Fallback if nothing retrieved
    if not all_passages and not tool_outputs:
        print(f"[ReAct] No passages retrieved — falling back to direct FAISS search")
        all_passages = kb.search(user_query, top_k=top_k)

    # Merge tool outputs into passages
    all_passages.extend(tool_outputs)

    # Domain priority sort
    domain_matched = [p for p in all_passages if p.get("domain") == domain]
    domain_other = [p for p in all_passages if p.get("domain") != domain]
    all_passages = domain_matched + domain_other

    return all_passages
