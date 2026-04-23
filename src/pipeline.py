"""
ShramikSaathi — Cross-domain Pipeline (FINAL)
Orchestrates: Router → Slot Extractor → Sufficiency Gate → ReAct Loop → Eligibility Reasoner → Generator
Covers: PF/EPFO, Payslip Audit, Labour Rights, Income Tax

All fixes incorporated:
- Re-routes every turn (domain switch resets slots)
- ReAct loop with 3 tools (SearchKB, GetPolicy, ParsePayslip)
- Subdomain filter for reasoner (generator sees all passages)
- Safe .get() access for condition trace
- Rate limit retry on all Groq calls
- Path-agnostic KB loading (works from project root or src/)
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
# Allow running from project root (D:\epfo_copilot) or from src/

_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from cross_domain_router import route, llm_route
from slot_extractor import extract_slots, merge_slots
from sufficiency_gate import check_sufficiency, CONTEXT_FREE_INTENTS
from eligibility_reasoner import run_eligibility_reasoner
from react_loop import react_retrieve
from search_kb import SearchKB

# ── Resolve KB paths relative to project root, not cwd ───────────────────────
_PROJECT_ROOT = _SRC_DIR.parent
_INDEX_PATH = _PROJECT_ROOT / "index" / "faiss_index.bin"
_STORE_PATH = _PROJECT_ROOT / "index" / "chunk_store.json"

kb = SearchKB(
    index_path=str(_INDEX_PATH),
    store_path=str(_STORE_PATH),
)


# ── Groq API call with rate limit retry ────────────────────────────────────────

def _groq_call(messages, temperature=0.2, max_tokens=800):
    """Groq API call with automatic rate limit retry."""
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
                print(f"[Pipeline] Rate limited — waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    return "[Error: rate limit exceeded after retries]"


# ── Intent → relevant subdomains mapping ───────────────────────────────────────

INTENT_SUBDOMAINS = {
    # PF
    "full_withdrawal":      ["withdrawal"],
    "partial_withdrawal":   ["withdrawal"],
    "transfer":             ["transfer"],
    "kyc_issue":            ["kyc", "uan"],
    "tds_query":            ["taxation"],
    "employer_complaint":   ["employer", "grievance"],
    "pension":              ["pension"],
    "nomination_update":    ["nomination"],

    # Payslip
    "verify_epf":           ["epf_deduction", "tool_output"],
    "verify_esi":           ["esi_deduction", "tool_output"],
    "check_deductions":     ["professional_tax", "epf_deduction", "esi_deduction", "tool_output"],
    "check_minimum_wage":   ["minimum_wage"],
    "full_audit":           ["epf_deduction", "esi_deduction", "professional_tax", "wage_structure", "tool_output"],
    "check_bonus":          ["bonuses"],

    # Labour
    "gratuity":             ["gratuity"],
    "wrongful_termination": ["termination"],
    "maternity_benefit":    ["maternity"],
    "overtime_pay":         ["overtime"],
    "notice_period":        ["termination"],

    # Tax
    "tds_on_salary":        ["tds_salary"],
    "tds_on_pf":            ["tds_pf"],
    "hra_exemption":        ["hra"],
    "deductions_80c":       ["deductions"],
    "refund_status":        ["refund"],
    "form16":               ["tds_salary"],
    "itr_filing":           ["tds_salary", "deductions"],
}


def _filter_passages_for_reasoner(passages: list, intent: str) -> list:
    relevant_subdomains = INTENT_SUBDOMAINS.get(intent)
    if not relevant_subdomains:
        return passages
    filtered = [p for p in passages if p.get("subdomain", "") in relevant_subdomains]
    if not filtered:
        print(f"[Pipeline] Subdomain filter returned 0 — falling back to all {len(passages)} passages")
        return passages
    print(f"[Pipeline] Subdomain filter: {len(passages)} → {len(filtered)} passages for reasoner (subdomains: {relevant_subdomains})")
    return filtered


REASONING_INTENTS = {
    "full_withdrawal", "partial_withdrawal", "transfer",
    "tds_query", "kyc_issue",
    "verify_epf", "verify_esi", "check_deductions",
    "check_minimum_wage", "full_audit",
    "gratuity", "wrongful_termination", "maternity_benefit", "overtime_pay",
    "tds_on_salary", "tds_on_pf", "hra_exemption", "deductions_80c",
}


GENERATOR_PROMPT = """You are ShramikSaathi, an Indian worker rights support copilot.
You help workers with PF/EPFO, payslip audit, labour rights, and income tax queries.

You will be given:
1. The user's query
2. The detected domain
3. Retrieved KB passages with doc_ids and dates
4. An eligibility reasoning trace (if applicable)
5. Filled slots

Your job: produce a clear, cited, structured answer.

RULES:
- Every factual claim must cite its doc_id in brackets e.g. [GRATUITY_ACT_S4_ELIG]
- CITATION RULE: Only cite doc_ids that appear verbatim in the RETRIEVED PASSAGES section.
  Never invent new doc_ids, suffixes, or section numbers. If a claim needs a citation but no
  passage supports it, omit the citation rather than fabricate one.
- If eligibility reasoning is provided, include the condition trace in your answer
- If decision is ANSWER + eligible=True  → confirm eligibility, give next steps
- If decision is ANSWER + eligible=False → clearly state not eligible, explain why, cite condition
- If decision is ESCALATE → say KB lacks info, suggest appropriate grievance portal
- For informational queries → answer directly from passages with citations
- Keep answers structured: result first, then steps, then warnings/caveats
- Never make up information not in the passages
- Use simple language — the user may not know legal terminology
- For payslip queries: show the calculation (expected vs actual deduction)
- For tax queries: show the applicable slab or formula with numbers
- For labour queries: cite the specific Act and Section number"""


def _build_generator_input(query, domain, passages, reasoning, slots):
    passages_text = kb.format_for_prompt(passages)
    reasoning_text = ""

    if reasoning:
        decision = reasoning.get("decision", "")
        eligible = reasoning.get("eligible")
        coverage = reasoning.get("coverage", 0)
        met = reasoning.get("met", [])
        failed = reasoning.get("failed", [])
        warnings = reasoning.get("warnings", [])
        unresolved = reasoning.get("unresolved", [])

        lines = [
            "ELIGIBILITY REASONING TRACE:",
            f"  Decision : {decision}",
        ]
        if eligible is not None:
            lines.append(f"  Eligible : {eligible}")
        lines.append(f"  Coverage : {coverage}")

        if met:
            lines.append("  Met conditions:")
            for c in met:
                lines.append(
                    f"    ✓ {c.get('field','?')} {c.get('operator','?')} {c.get('value','?')} [{c.get('doc_id', '?')}]"
                )
        if failed:
            lines.append("  Failed conditions:")
            for c in failed:
                lines.append(
                    f"    ✗ {c.get('field','?')} {c.get('operator','?')} {c.get('value','?')} [{c.get('doc_id', '?')}] (user value: {c.get('slot_value')})"
                )
        if warnings:
            lines.append("  Warnings (non-blocking):")
            for c in warnings:
                lines.append(
                    f"    ⚠ {c.get('field','?')} {c.get('operator','?')} {c.get('value','?')} [{c.get('doc_id', '?')}]"
                )
        if unresolved:
            lines.append("  Unresolved:")
            for c in unresolved:
                lines.append(f"    ? {c.get('field','?')} — slot missing")

        reasoning_text = "\n".join(lines)

    filled_slots = {k: v for k, v in slots.items() if v is not None}

    return f"""USER QUERY:
{query}

DOMAIN: {domain}

RETRIEVED PASSAGES:
{passages_text}

{reasoning_text}

SLOTS FILLED:
{json.dumps(filled_slots, indent=2)}

Produce the final answer now."""


def _generate_answer(query, domain, passages, reasoning, slots):
    user_content = _build_generator_input(query, domain, passages, reasoning, slots)
    return _groq_call([
        {"role": "system", "content": GENERATOR_PROMPT},
        {"role": "user", "content": user_content},
    ])


def run_pipeline(user_query: str, session: dict) -> dict:
    """Full cross-domain pipeline."""
    history = session.get("history", [])
    slots = session.get("slots", {})
    domain = session.get("domain", None)
    turn = session.get("turn", 0) + 1

    # Step 1: Cross-domain Router
    router_result = llm_route(user_query)
    new_domain = router_result["domain"]
    confidence = router_result["confidence"]

    if domain is not None and new_domain != domain:
        print(f"[Pipeline] Domain switch: {domain} → {new_domain} — resetting slots")
        slots = {}

    domain = new_domain
    print(f"\n[Pipeline] Turn {turn} | Router → {domain} (conf={confidence})")

    # Step 2: Slot Extraction
    new_slots = extract_slots(user_query, domain, chat_history=history)
    slots = merge_slots(slots, new_slots)
    intent = slots.get("intent", "general")

    print(f"[Pipeline] Intent: {intent}")
    print(f"[Pipeline] Slots: { {k:v for k,v in slots.items() if v is not None} }")

    # Step 3: Sufficiency Gate
    gate = check_sufficiency(slots, domain)

    if not gate["sufficient"]:
        question = gate["question"]
        print(f"[Pipeline] Gate blocked — missing: {gate['missing']} — asking: {question}")
        history.append({"role": "user", "content": user_query})
        history.append({"role": "assistant", "content": question})
        return {
            "response": question,
            "decision": "ASK",
            "coverage": 0.0,
            "domain": domain,
            "slots": slots,
            "history": history,
            "turn": turn,
            "ask_again": True,
        }

    # Step 4: ReAct Retrieval Loop
    print(f"[Pipeline] Gate passed — starting ReAct retrieval for domain={domain}...")
    passages = react_retrieve(user_query, domain, intent, slots, kb)
    print(f"[Pipeline] Retrieved {len(passages)} passages: {[p.get('doc_id', '?') for p in passages]}")

    # Step 5: Eligibility Reasoner
    reasoning = None
    if intent in REASONING_INTENTS:
        reasoner_passages = _filter_passages_for_reasoner(passages, intent)
        print(f"[Pipeline] Running eligibility reasoner...")
        reasoning = run_eligibility_reasoner(reasoner_passages, slots, domain=domain)
        print(f"[Pipeline] Decision: {reasoning['decision']} | Coverage: {reasoning['coverage']}")

        if reasoning["decision"] == "ASK":
            question = reasoning["question"]
            history.append({"role": "user", "content": user_query})
            history.append({"role": "assistant", "content": question})
            return {
                "response": question,
                "decision": "ASK",
                "coverage": reasoning["coverage"],
                "domain": domain,
                "slots": slots,
                "history": history,
                "turn": turn,
                "ask_again": True,
            }

    # Step 6: Generate Answer
    print(f"[Pipeline] Generating answer...")
    answer = _generate_answer(user_query, domain, passages, reasoning, slots)

    history.append({"role": "user", "content": user_query})
    history.append({"role": "assistant", "content": answer})

    return {
        "response": answer,
        "decision": reasoning["decision"] if reasoning else "ANSWER",
        "coverage": reasoning["coverage"] if reasoning else 1.0,
        "domain": domain,
        "slots": slots,
        "history": history,
        "turn": turn,
        "ask_again": False,
    }


# ── CLI loop ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("ShramikSaathi — Cross-domain Pipeline")
    print("Domains: PF/EPFO | Payslip Audit | Labour Rights | Income Tax")
    print("Type 'exit' to quit, 'reset' to start new session")
    print("=" * 60)

    session = {"slots": {}, "history": [], "turn": 0, "domain": None}

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue
        if user_input.lower() == "exit":
            break
        if user_input.lower() == "reset":
            session = {"slots": {}, "history": [], "turn": 0, "domain": None}
            print("[Session reset]")
            continue

        result = run_pipeline(user_input, session)
        session = result

        print(f"\nCopilot: {result['response']}")
        print(
            f"\n[Meta] Domain={result['domain']} | Decision={result['decision']} | "
            f"Coverage={result['coverage']} | Turn={result['turn']}"
        )
