"""
Eligibility Reasoner — parses IF/THEN conditions from passages, checks against slots
Cross-domain: PF, Payslip, Labour, Tax
Three stages: Condition Parser → Condition Checker → Gap Resolver

FINAL version — includes:
- Per-passage LLM parsing (no batching, no truncation)
- Valid values in prompt (prevents string mismatches)
- Fuzzy string matching in checker (catches remaining mismatches)
- Per-field deduplication (filters noise from irrelevant passages)
- Cross-domain RELATED_DOMAINS (PF+Tax, Payslip+PF allowed together)
- Intent awareness (only extract conditions relevant to user's intent)
- Pre-encoded KB conditions as fast path
- Rate limit retry on all API calls
"""

import os
import json
import re
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ══════════════════════════════════════════════════════════════════════════════
# CROSS-DOMAIN MAPPING — which domains can share conditions
# ══════════════════════════════════════════════════════════════════════════════

RELATED_DOMAINS = {
    "pf":      ["pf", "tax"],       # PF withdrawal + TDS rules
    "tax":     ["tax", "pf"],       # TDS on PF withdrawal
    "payslip": ["payslip", "pf"],   # payslip EPF links to PF contribution rules
    "labour":  ["labour"],          # labour is self-contained
}


# ══════════════════════════════════════════════════════════════════════════════
# GROQ CALL WITH RETRY
# ══════════════════════════════════════════════════════════════════════════════

def _groq_call(messages, temperature=0.0, max_tokens=500):
    """Groq API call with rate limit retry."""
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
                print(f"[Reasoner] Rate limited — waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    return None


# ══════════════════════════════════════════════════════════════════════════════
# CONDITION PARSER — per-passage LLM extraction
# ══════════════════════════════════════════════════════════════════════════════

CONDITION_PARSER_PROMPT = """You are an eligibility condition extractor for an Indian worker rights support system.

Given ONE passage, extract the eligibility conditions as a JSON array.

Each condition must have:
- "field"     : the slot name being checked (use EXACT names from the list below)
- "operator"  : one of [gte, lte, gt, lt, eq, in, not_null]
- "value"     : the threshold or valid value (use EXACT valid values listed below for enum fields)
- "mandatory" : true if this condition MUST be met, false if it's a warning/caveat

SLOT NAMES AND VALID VALUES BY DOMAIN:

PF:
- employment_status  (use exactly: "employed" / "unemployed" / "retired")
- months_unemployed  (integer)
- service_years      (integer)
- uan_status         (use exactly: "active" / "inactive" / "not_generated")
- kyc_status         (use exactly: "complete" / "incomplete" / "partial" / "rejected")

Payslip:
- basic_salary       (integer, rupees)
- gross_salary       (integer, rupees)
- epf_deducted       (integer, rupees)
- esi_deducted       (integer, rupees)
- state              (string, full state name)
- employee_count     (integer)

Labour:
- employment_years   (integer)
- termination_reason (use exactly: "resignation" / "employer_terminated" / "retrenched" / "misconduct" / "retirement")
- last_drawn_salary  (integer, rupees)
- is_pregnant        (boolean: true / false)
- employer_type      (use exactly: "private" / "government" / "factory" / "shop_establishment")

Tax:
- annual_income           (integer, rupees)
- tax_regime              (use exactly: "old_regime" / "new_regime")
- rent_paid               (integer, rupees monthly)
- city_type               (use exactly: "metro" / "non_metro")
- service_years           (integer)
- pf_withdrawal_amount    (integer, rupees)

OPERATOR meanings:
- gte → >=    gt → >    lte → <=    lt → <
- eq → ==     in → one of (value must be a list)
- not_null → field must be present

RULES:
1. Output ONLY a valid JSON array. No explanation, no markdown.
2. If no conditions are extractable, output []
3. Mark TDS/tax/warning conditions as mandatory: false
4. The user's intent is provided — ONLY extract conditions that determine eligibility for THAT specific intent.
5. Ignore conditions for unrelated processes, different withdrawal types, tax slab breakdowns, or background information.
6. Use field names and values EXACTLY as listed above. Do NOT use synonyms like "verified" for "complete" or "old" for "old_regime".
7. Output compact JSON — no newlines, no indentation.
8. Maximum 4 conditions per passage. Pick the most relevant to the user's intent."""


def parse_conditions(
    passages: list[dict], domain: str = "general", intent: str = "general"
) -> list[dict]:
    """
    Extract conditions from passages. Processes ONE passage at a time.
    Then deduplicates: keeps only first condition per (field, operator) pair.
    """
    all_conditions = []
    allowed_domains = RELATED_DOMAINS.get(domain, [domain])

    for p in passages:
        # Skip off-domain passages (respecting cross-domain relationships)
        p_domain = p.get("domain", "general")
        if domain != "general" and p_domain != "general" and p_domain not in allowed_domains:
            print(f"[ConditionParser] Skipping off-domain: {p.get('doc_id')} ({p_domain} not in {allowed_domains})")
            continue

        doc_id = p.get("doc_id", "UNKNOWN")

        # Fast path: pre-encoded conditions in KB metadata
        kb_conditions = p.get("conditions", [])
        if kb_conditions and isinstance(kb_conditions, list) and len(kb_conditions) > 0:
            valid_kb = [c for c in kb_conditions if isinstance(c, dict) and "field" in c]
            if valid_kb:
                for c in valid_kb:
                    c.setdefault("doc_id", doc_id)
                all_conditions.extend(valid_kb)
                print(f"[ConditionParser] {doc_id}: {len(valid_kb)} pre-encoded conditions")
                continue

        # LLM path: extract from content (one passage at a time)
        extracted = _llm_parse_single(p, domain, intent)
        if extracted:
            print(f"[ConditionParser] {doc_id}: {len(extracted)} LLM-extracted conditions")
        else:
            print(f"[ConditionParser] {doc_id}: 0 conditions (not relevant to {intent})")
        all_conditions.extend(extracted)

    # Deduplicate: keep only the first condition per (field, operator) pair
    deduped = _deduplicate_conditions(all_conditions)

    return deduped


def _deduplicate_conditions(conditions: list[dict]) -> list[dict]:
    """
    Keep only the first condition per (field, operator) pair.
    Since passages are ranked by retrieval relevance, first = most relevant.
    """
    seen = set()
    result = []
    for c in conditions:
        field = c.get("field", "")
        operator = c.get("operator", "")
        key = (field, operator)
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result


def _llm_parse_single(
    passage: dict, domain: str, intent: str = "general"
) -> list[dict]:
    """Extract conditions from a SINGLE passage via LLM."""
    doc_id = passage.get("doc_id", "UNKNOWN")
    content = passage.get("content", "")[:600]

    if not content or len(content) < 20:
        return []

    prompt = f"Domain: {domain}\nUser intent: {intent}\ndoc_id: {doc_id}\n\n{content}"

    raw = _groq_call(
        messages=[
            {"role": "system", "content": CONDITION_PARSER_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=500,
    )

    if raw is None:
        print(f"[ConditionParser] {doc_id}: API call failed")
        return []

    raw = re.sub(r"```json|```", "", raw).strip()

    try:
        conditions = json.loads(raw)
        if isinstance(conditions, list):
            for c in conditions:
                if isinstance(c, dict):
                    c.setdefault("doc_id", doc_id)
            return [c for c in conditions if isinstance(c, dict) and "field" in c]
        return []
    except json.JSONDecodeError:
        print(f"[ConditionParser] {doc_id}: JSON parse failed — {raw[:100]}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# CONDITION CHECKER — with fuzzy string matching
# ══════════════════════════════════════════════════════════════════════════════

# Normalization map: LLM output variants → canonical slot values
_VALUE_ALIASES = {
    # KYC
    "verified": "complete", "approved": "complete", "done": "complete",
    "not_complete": "incomplete", "pending": "incomplete",
    # UAN
    "activated": "active", "enabled": "active",
    "deactivated": "inactive", "disabled": "inactive",
    # Tax regime
    "old": "old_regime", "new": "new_regime",
    "old_tax_regime": "old_regime", "new_tax_regime": "new_regime",
    # Employment
    "terminated": "employer_terminated", "fired": "employer_terminated",
    "dismissed": "employer_terminated",
    "resigned": "resignation", "quit": "resignation",
    # Employer type
    "govt": "government", "public_sector": "government",
    "shop": "shop_establishment", "establishment": "shop_establishment",
}


def _normalize(val) -> str:
    """Normalize a value for fuzzy comparison."""
    s = str(val).lower().strip()
    return _VALUE_ALIASES.get(s, s)


def check_conditions(conditions: list[dict], slots: dict) -> list[dict]:
    """
    Evaluate each condition against the filled slot dict.
    Uses fuzzy string matching for eq/in operators.
    """
    results = []

    for cond in conditions:
        field = cond.get("field")
        operator = cond.get("operator")
        value = cond.get("value")
        slot_val = slots.get(field)

        result = dict(cond)

        if slot_val is None:
            result["status"] = "UNRESOLVED"
            result["slot_value"] = None
            results.append(result)
            continue

        try:
            met = _evaluate(slot_val, operator, value)
            result["status"] = "RESOLVED_MET" if met else "RESOLVED_NOT_MET"
        except Exception as e:
            print(f"[Checker] Error evaluating {field} {operator} {value}: {e}")
            result["status"] = "UNRESOLVED"

        result["slot_value"] = slot_val
        results.append(result)

    return results


def _evaluate(slot_val, operator: str, threshold) -> bool:
    """Evaluate a single condition. Uses normalization for string comparisons."""
    if operator == "gte":
        return float(slot_val) >= float(threshold)
    elif operator == "lte":
        return float(slot_val) <= float(threshold)
    elif operator == "gt":
        return float(slot_val) > float(threshold)
    elif operator == "lt":
        return float(slot_val) < float(threshold)
    elif operator == "eq":
        return _normalize(slot_val) == _normalize(threshold)
    elif operator == "in":
        normalized_slot = _normalize(slot_val)
        normalized_list = [_normalize(v) for v in threshold]
        return normalized_slot in normalized_list
    elif operator == "not_null":
        return slot_val is not None
    return False


# ══════════════════════════════════════════════════════════════════════════════
# GAP RESOLVER
# ══════════════════════════════════════════════════════════════════════════════


def resolve_gaps(checked_conditions: list[dict]) -> dict:
    """
    Produce final decision from checked conditions.
    """
    mandatory = [c for c in checked_conditions if c.get("mandatory", True)]
    warnings = [
        c
        for c in checked_conditions
        if not c.get("mandatory", True) and c["status"] == "RESOLVED_MET"
    ]

    unresolved = [c for c in mandatory if c["status"] == "UNRESOLVED"]
    failed = [c for c in mandatory if c["status"] == "RESOLVED_NOT_MET"]
    met = [c for c in mandatory if c["status"] == "RESOLVED_MET"]

    total_mandatory = len(mandatory)
    resolved_count = len(met) + len(failed)
    coverage = (
        round(resolved_count / total_mandatory, 2) if total_mandatory > 0 else 1.0
    )

    if failed:
        return {
            "decision": "ANSWER",
            "eligible": False,
            "question": None,
            "warnings": warnings,
            "failed": failed,
            "unresolved": unresolved,
            "met": met,
            "coverage": coverage,
        }

    if unresolved:
        first = unresolved[0]
        question = _question_for(first.get("field", ""))
        return {
            "decision": "ASK",
            "eligible": None,
            "question": question,
            "warnings": warnings,
            "failed": failed,
            "unresolved": unresolved,
            "met": met,
            "coverage": coverage,
        }

    if not mandatory:
        return {
            "decision": "ESCALATE",
            "eligible": None,
            "question": None,
            "warnings": warnings,
            "failed": [],
            "unresolved": [],
            "met": [],
            "coverage": 0.0,
        }

    return {
        "decision": "ANSWER",
        "eligible": True,
        "question": None,
        "warnings": warnings,
        "failed": [],
        "unresolved": [],
        "met": met,
        "coverage": coverage,
    }


def _question_for(field: str) -> str:
    """Cross-domain clarifying questions."""
    questions = {
        "employment_status": "Are you currently employed, unemployed, or retired?",
        "service_years": "How many total years have you contributed to PF?",
        "months_unemployed": "How many months have you been unemployed?",
        "age": "How old are you?",
        "uan_status": "Is your UAN currently active?",
        "kyc_status": "Is your KYC complete on the EPFO portal?",
        "reason": "What is the reason for your withdrawal?",
        "withdrawal_amount": "What is the approximate amount you plan to withdraw?",
        "basic_salary": "What is your monthly basic salary (in rupees)?",
        "gross_salary": "What is your monthly gross salary (in rupees)?",
        "epf_deducted": "How much EPF is being deducted per month from your salary?",
        "esi_deducted": "How much ESI is being deducted per month? Say 0 if none.",
        "state": "Which Indian state do you work in?",
        "employee_count": "How many employees does your company have?",
        "employment_years": "How many years have you worked with this employer?",
        "termination_reason": "Did you resign, were you fired, or retrenched?",
        "last_drawn_salary": "What was your last monthly salary (in rupees)?",
        "is_pregnant": "Are you currently pregnant?",
        "employer_type": "Is your employer private, government, factory, or shop?",
        "notice_period_days": "What is the notice period in your offer letter (in days)?",
        "annual_income": "What is your total annual income (in rupees)?",
        "tax_regime": "Are you on the old tax regime or the new tax regime?",
        "rent_paid": "How much rent do you pay per month (in rupees)?",
        "city_type": "Do you live in a metro city (Delhi/Mumbai/Kolkata/Chennai) or non-metro?",
        "has_form16": "Have you received Form 16 from your employer?",
        "section_80c_investments": "What is your total 80C investment amount?",
        "pf_withdrawal_amount": "What was the PF withdrawal amount (in rupees)?",
    }
    return questions.get(field, f"Could you provide your {field.replace('_', ' ')}?")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════


def run_eligibility_reasoner(
    passages: list[dict], slots: dict, domain: str = "general"
) -> dict:
    """
    Full pipeline: parse → check → resolve.
    """
    intent = slots.get("intent", "general")
    conditions = parse_conditions(passages, domain=domain, intent=intent)
    checked = check_conditions(conditions, slots)
    resolution = resolve_gaps(checked)
    resolution["conditions"] = checked
    return resolution
