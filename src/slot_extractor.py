"""
Cross-domain Slot Extractor — extracts structured facts from user query per domain
LLM version (domain-specific prompts) + regex/keyword baseline
Supports: pf, payslip, labour, tax
"""

import os
import re
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS — one per domain, keys match eval data exactly
# ══════════════════════════════════════════════════════════════════════════════

SLOT_SCHEMA_PF = {
    "intent": None,
    "employment_status": None,
    "months_unemployed": None,
    "service_years": None,
    "uan_status": None,
    "kyc_status": None,
    "employer_name": None,
    "incident_type": None,
}

SLOT_SCHEMA_PAYSLIP = {
    "intent": None,
    "basic_salary": None,
    "gross_salary": None,
    "epf_deducted": None,
    "esi_deducted": None,
    "state": None,
    "employee_count": None,
}

SLOT_SCHEMA_LABOUR = {
    "intent": None,
    "employment_years": None,
    "termination_reason": None,
    "last_drawn_salary": None,
    "is_pregnant": None,
    "employer_type": None,
    "state": None,
    "notice_period_days": None,
}

SLOT_SCHEMA_TAX = {
    "intent": None,
    "annual_income": None,
    "tax_regime": None,
    "rent_paid": None,
    "city_type": None,
    "has_form16": None,
    "section_80c_investments": None,
    "pf_withdrawal_amount": None,
    "service_years": None,
}

SCHEMA_BY_DOMAIN = {
    "pf": SLOT_SCHEMA_PF,
    "payslip": SLOT_SCHEMA_PAYSLIP,
    "labour": SLOT_SCHEMA_LABOUR,
    "tax": SLOT_SCHEMA_TAX,
}


# ══════════════════════════════════════════════════════════════════════════════
# VALID VALUES — for enum validation
# ══════════════════════════════════════════════════════════════════════════════

VALID_VALUES = {
    # PF
    "pf_intent": [
        "full_withdrawal", "partial_withdrawal", "transfer",
        "kyc_issue", "tds_query", "employer_complaint",
        "pension", "nomination_update", "general",
    ],
    "employment_status": ["employed", "unemployed", "retired", "nominee"],
    "uan_status": ["active", "inactive", "not_generated"],
    "kyc_status": ["complete", "incomplete", "partial", "rejected"],
    "incident_type": ["non_deposit", "wrong_amount", "delayed_deposit"],

    # Payslip
    "payslip_intent": [
        "verify_epf", "verify_esi", "check_deductions",
        "check_minimum_wage", "full_audit", "check_bonus", "general",
    ],

    # Labour
    "labour_intent": [
        "gratuity", "wrongful_termination", "notice_period",
        "maternity_benefit", "overtime_pay", "general",
    ],
    "termination_reason": [
        "resignation", "employer_terminated", "retrenched",
        "misconduct", "retirement", "contract_ended",
    ],
    "employer_type": [
        "private", "government", "factory",
        "shop_establishment", "contractor",
    ],

    # Tax
    "tax_intent": [
        "tds_on_salary", "tds_on_pf", "hra_exemption",
        "deductions_80c", "form16", "refund_status",
        "itr_filing", "general",
    ],
    "tax_regime": ["old_regime", "new_regime"],
    "city_type": ["metro", "non_metro"],
}

# Metro cities for tax HRA: Delhi, Mumbai, Kolkata, Chennai (only these 4)
METRO_CITIES = {"delhi", "mumbai", "kolkata", "chennai", "new delhi"}


# ══════════════════════════════════════════════════════════════════════════════
# INDIAN STATE MAPPING — for normalizing state names from queries
# ══════════════════════════════════════════════════════════════════════════════

STATE_ALIASES = {
    "up": "Uttar Pradesh", "uttar pradesh": "Uttar Pradesh",
    "mp": "Madhya Pradesh", "madhya pradesh": "Madhya Pradesh",
    "maharashtra": "Maharashtra", "mh": "Maharashtra",
    "karnataka": "Karnataka", "bangalore": "Karnataka", "bengaluru": "Karnataka",
    "tamil nadu": "Tamil Nadu", "tn": "Tamil Nadu", "chennai": "Tamil Nadu",
    "kerala": "Kerala",
    "telangana": "Telangana", "hyderabad": "Telangana",
    "andhra pradesh": "Andhra Pradesh", "ap": "Andhra Pradesh",
    "gujarat": "Gujarat",
    "rajasthan": "Rajasthan",
    "punjab": "Punjab",
    "haryana": "Haryana", "gurgaon": "Haryana", "gurugram": "Haryana",
    "delhi": "Delhi", "new delhi": "Delhi", "noida": "Uttar Pradesh",
    "west bengal": "West Bengal", "wb": "West Bengal", "kolkata": "West Bengal",
    "bihar": "Bihar",
    "odisha": "Odisha",
    "assam": "Assam",
    "jharkhand": "Jharkhand",
    "chhattisgarh": "Chhattisgarh",
    "uttarakhand": "Uttarakhand",
    "goa": "Goa",
    "mumbai": "Maharashtra", "pune": "Maharashtra",
}


# ══════════════════════════════════════════════════════════════════════════════
# LLM PROMPTS — one per domain
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT_PF = """You are a slot extractor for an Indian PF/EPFO support system.

Read the user's query and extract structured information into a fixed JSON schema.

INTENT values (pick exactly one):
- full_withdrawal       → user wants to withdraw full PF balance after leaving job
- partial_withdrawal    → user wants advance/partial PF withdrawal (medical, house, education)
- transfer              → user wants to transfer PF between employers
- kyc_issue             → user has KYC/Aadhaar/UAN seeding problems
- tds_query             → user asking about TDS deducted on PF withdrawal
- employer_complaint    → user reporting employer not depositing PF or depositing wrong amount
- pension               → user asking about EPS pension
- nomination_update     → user wants to update PF nomination
- general               → does not fit above

CONTEXT SLOTS — extract only if clearly stated or strongly implied:
- employment_status     → employed / unemployed / retired / nominee
- months_unemployed     → integer (round down: "6 weeks" = 1, "2.5 months" = 2)
- service_years         → integer (round down: "3.5 years" = 3, "4 years 11 months" = 4)
- uan_status            → active / inactive / not_generated
- kyc_status            → complete / incomplete / partial / rejected ("done"/"approved" = complete)
- employer_name         → company name as lowercase string, only if explicitly mentioned
- incident_type         → non_deposit / wrong_amount / delayed_deposit (only for employer_complaint)

RULES:
1. Return ONLY a valid JSON object. No explanation, no markdown.
2. Use null for any slot not present in the query.
3. Do not infer or guess — only extract what is explicitly stated or strongly implied.
4. intent must always be non-null.
5. If user "left job" / "quit" / "resigned" → employment_status = "unemployed"
6. If user is working / "currently employed" / mentions current company → employment_status = "employed"

EXAMPLES:

Query: "I quit exactly 4 months ago. UAN is perfectly active and KYC approved. Need total settlement."
Output: {"intent": "full_withdrawal", "employment_status": "unemployed", "months_unemployed": 4, "service_years": null, "uan_status": "active", "kyc_status": "complete", "employer_name": null, "incident_type": null}

Query: "company reliance retail deducted pf but not showing in portal"
Output: {"intent": "employer_complaint", "employment_status": null, "months_unemployed": null, "service_years": null, "uan_status": null, "kyc_status": null, "employer_name": "reliance retail", "incident_type": "non_deposit"}

Query: "aadhar name mismatch kyc reject ho raha"
Output: {"intent": "kyc_issue", "employment_status": null, "months_unemployed": null, "service_years": null, "uan_status": null, "kyc_status": "rejected", "employer_name": null, "incident_type": null}

OUTPUT FORMAT:
{"intent": "...", "employment_status": null, "months_unemployed": null, "service_years": null, "uan_status": null, "kyc_status": null, "employer_name": null, "incident_type": null}"""


SYSTEM_PROMPT_PAYSLIP = """You are a slot extractor for an Indian payslip audit system.

Read the user's query and extract structured information into a fixed JSON schema.

INTENT values (pick exactly one):
- verify_epf            → user wants to verify if EPF deduction is correct
- verify_esi            → user wants to verify if ESI deduction is correct
- check_deductions      → user asking about professional tax or general deduction queries
- check_minimum_wage    → user wants to check if salary meets minimum wage
- full_audit            → user wants complete payslip audit (multiple deductions)
- check_bonus           → user asking about statutory bonus entitlement
- general               → does not fit above

CONTEXT SLOTS — extract only if clearly stated or strongly implied:
- basic_salary          → integer in rupees (monthly)
- gross_salary          → integer in rupees (monthly)
- epf_deducted          → integer in rupees (monthly PF deduction shown on payslip)
- esi_deducted          → integer in rupees (monthly ESI deducted). If user says "no ESI deducted" → 0
- state                 → full Indian state name (e.g. "Maharashtra" not "MH"). Infer from city: Mumbai/Pune → Maharashtra, Bangalore → Karnataka, Delhi → Delhi, etc.
- employee_count        → integer (number of employees in the company/establishment)

RULES:
1. Return ONLY a valid JSON object. No explanation, no markdown.
2. Use null for any slot not present in the query.
3. Do not infer or guess — only extract what is explicitly stated or strongly implied.
4. intent must always be non-null.
5. Salary amounts are monthly and in Indian rupees unless stated otherwise.
6. Infer state from city names: Mumbai → Maharashtra, Bangalore/Bengaluru → Karnataka, Delhi/Noida → Delhi/UP, Hyderabad → Telangana, Chennai → Tamil Nadu, Kolkata → West Bengal.

EXAMPLES:

Query: "basic is around 18500 and esi they cut is around 500, verify esi"
Output: {"intent": "verify_esi", "basic_salary": 18500, "gross_salary": null, "epf_deducted": null, "esi_deducted": 500, "state": null, "employee_count": null}

Query: "working at a bangalore IT firm, gross 28000, no ESI being deducted, is that correct?"
Output: {"intent": "verify_esi", "basic_salary": null, "gross_salary": 28000, "esi_deducted": 0, "state": "Karnataka", "epf_deducted": null, "employee_count": null}

Query: "gross is 12000, working in UP, is my salary above minimum wage for unskilled worker"
Output: {"intent": "check_minimum_wage", "basic_salary": null, "gross_salary": 12000, "state": "Uttar Pradesh", "epf_deducted": null, "esi_deducted": null, "employee_count": null}

OUTPUT FORMAT:
{"intent": "...", "basic_salary": null, "gross_salary": null, "epf_deducted": null, "esi_deducted": null, "state": null, "employee_count": null}"""


SYSTEM_PROMPT_LABOUR = """You are a slot extractor for an Indian labour rights support system.

Read the user's query and extract structured information into a fixed JSON schema.

INTENT values (pick exactly one):
- gratuity              → user asking about gratuity eligibility or calculation
- wrongful_termination  → user was fired/terminated and wants to know rights
- notice_period         → user asking about notice period rules, buyout, penalty
- maternity_benefit     → user asking about maternity leave entitlement
- overtime_pay          → user asking about overtime pay rights
- general               → does not fit above

CONTEXT SLOTS — extract only if clearly stated or strongly implied:
- employment_years      → integer (round down: "6 years 2 months" = 6, "2.5 years" = 2)
- termination_reason    → resignation / employer_terminated / retrenched / misconduct / retirement / contract_ended
                          "quit"/"resigned"/"left" = resignation. "fired"/"dismissed"/"terminated by company" = employer_terminated
- last_drawn_salary     → integer in rupees (monthly). Can be basic or gross — take whichever is mentioned.
- is_pregnant           → true / false / null. "expecting mother"/"pregnant" = true
- employer_type         → private / government / factory / shop_establishment / contractor
                          "govt school"/"sarkari" = government. "shop"/"retail shop" = shop_establishment
- state                 → full Indian state name. Infer from city names.
- notice_period_days    → integer (days). "60 days notice" = 60, "2 months notice" = 60, "1 month notice" = 30

RULES:
1. Return ONLY a valid JSON object. No explanation, no markdown.
2. Use null for any slot not present in the query.
3. Do not infer or guess — only extract what is explicitly stated or strongly implied.
4. intent must always be non-null.
5. "fired without cause" / "terminated randomly" → termination_reason = "employer_terminated"
6. "dismissed for misconduct" → termination_reason = "misconduct"

EXAMPLES:

Query: "resigned after working for 6 years 2 months. last drawn salary gross was 40500."
Output: {"intent": "gratuity", "employment_years": 6, "termination_reason": "resignation", "last_drawn_salary": 40500, "is_pregnant": null, "employer_type": null, "state": null, "notice_period_days": null}

Query: "fired without notice, worked 3 years in a private company, want to know my retrenchment rights"
Output: {"intent": "wrongful_termination", "employment_years": 3, "termination_reason": "employer_terminated", "last_drawn_salary": null, "is_pregnant": null, "employer_type": "private", "state": null, "notice_period_days": null}

Query: "factory work 12 hours daily, no overtime paid, Gujarat factory"
Output: {"intent": "overtime_pay", "employment_years": null, "termination_reason": null, "last_drawn_salary": null, "is_pregnant": null, "employer_type": "factory", "state": "Gujarat", "notice_period_days": null}

OUTPUT FORMAT:
{"intent": "...", "employment_years": null, "termination_reason": null, "last_drawn_salary": null, "is_pregnant": null, "employer_type": null, "state": null, "notice_period_days": null}"""


SYSTEM_PROMPT_TAX = """You are a slot extractor for an Indian income tax support system.

Read the user's query and extract structured information into a fixed JSON schema.

INTENT values (pick exactly one):
- tds_on_salary         → user asking about TDS deducted on salary or tax liability
- tds_on_pf             → user asking about TDS on PF withdrawal
- hra_exemption         → user asking about HRA exemption calculation
- deductions_80c        → user asking about 80C/80D deductions
- form16                → user asking about Form 16 (not received, how to use, etc.)
- refund_status         → user asking about IT refund status
- itr_filing            → user asking about ITR filing process
- general               → does not fit above

CONTEXT SLOTS — extract only if clearly stated or strongly implied:
- annual_income         → integer in rupees. "14.5 lakhs" = 1450000, "11 lpa" = 1100000, "6.5 lakh" = 650000
- tax_regime            → old_regime / new_regime. "old regime" = old_regime, "new regime"/"new scheme" = new_regime
- rent_paid             → integer in rupees (MONTHLY rent)
- city_type             → metro / non_metro. ONLY Delhi, Mumbai, Kolkata, Chennai are metro. ALL other cities (including Bangalore, Hyderabad, Pune) are non_metro.
- has_form16            → true / false. "form 16 nahi mila" = false, "have form 16" = true
- section_80c_investments → integer in rupees. "1.2 lakh 80C" = 120000
- pf_withdrawal_amount  → integer in rupees (PF amount withdrawn — for TDS on PF queries)
- service_years         → integer (round down: "3.5 years" = 3, "4 years 11 months" = 4)

RULES:
1. Return ONLY a valid JSON object. No explanation, no markdown.
2. Use null for any slot not present in the query.
3. Do not infer or guess — only extract what is explicitly stated or strongly implied.
4. intent must always be non-null.
5. Convert lakhs to rupees: 1 lakh = 100000, 1 lpa = 100000.
6. METRO cities for HRA: ONLY Delhi, Mumbai, Kolkata, Chennai. Bangalore is NON-METRO.

EXAMPLES:

Query: "income is 14.5 lakhs, opt for the old regime, paying rent 25000 in metro. checking hra."
Output: {"intent": "hra_exemption", "annual_income": 1450000, "tax_regime": "old_regime", "rent_paid": 25000, "city_type": "metro", "has_form16": null, "section_80c_investments": null, "pf_withdrawal_amount": null, "service_years": null}

Query: "I withdrew PF amount 85000 rs, but worked only 3.5 years"
Output: {"intent": "tds_on_pf", "annual_income": null, "tax_regime": null, "rent_paid": null, "city_type": null, "has_form16": null, "section_80c_investments": null, "pf_withdrawal_amount": 85000, "service_years": 3}

Query: "form 16 nahi mila employer se, ITR filing deadline is next week"
Output: {"intent": "form16", "annual_income": null, "tax_regime": null, "rent_paid": null, "city_type": null, "has_form16": false, "section_80c_investments": null, "pf_withdrawal_amount": null, "service_years": null}

OUTPUT FORMAT:
{"intent": "...", "annual_income": null, "tax_regime": null, "rent_paid": null, "city_type": null, "has_form16": null, "section_80c_investments": null, "pf_withdrawal_amount": null, "service_years": null}"""


PROMPT_BY_DOMAIN = {
    "pf": SYSTEM_PROMPT_PF,
    "payslip": SYSTEM_PROMPT_PAYSLIP,
    "labour": SYSTEM_PROMPT_LABOUR,
    "tax": SYSTEM_PROMPT_TAX,
}


# ══════════════════════════════════════════════════════════════════════════════
# LLM EXTRACTOR
# ══════════════════════════════════════════════════════════════════════════════


def extract_slots(user_query: str, domain: str, chat_history: list[dict] = None) -> dict:
    """
    LLM-based slot extraction.

    Args:
        user_query:   latest user message
        domain:       "pf" | "payslip" | "labour" | "tax" (from router)
        chat_history: optional prior turns [{"role": ..., "content": ...}]

    Returns:
        dict with ALL keys from the domain's schema. Unfilled = None.
    """
    prompt = PROMPT_BY_DOMAIN.get(domain, SYSTEM_PROMPT_PF)
    schema = SCHEMA_BY_DOMAIN.get(domain, SLOT_SCHEMA_PF)

    # Build context from prior turns
    history_text = ""
    if chat_history:
        recent = chat_history[-4:]
        history_text = "\n".join(f"{t['role'].upper()}: {t['content']}" for t in recent)
        history_text = f"\n\nPRIOR CONVERSATION:\n{history_text}\n"

    user_content = f"{history_text}\nCURRENT QUERY: {user_query}"

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
        max_tokens=300,
    )

    raw = response.choices[0].message.content.strip()
    return _parse_and_validate(raw, domain)


def _parse_and_validate(raw: str, domain: str) -> dict:
    """Parse LLM JSON output and validate against domain schema."""
    schema = SCHEMA_BY_DOMAIN.get(domain, SLOT_SCHEMA_PF)
    raw = re.sub(r"```json|```", "", raw).strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        print(f"[SlotExtractor] JSON parse failed for {domain}. Raw: {raw[:150]}")
        return dict(schema)

    slots = dict(schema)

    for key in slots:
        if key not in parsed:
            continue
        value = parsed[key]
        if value is None:
            continue

        # Validate based on field type
        if key == "intent":
            intent_key = f"{domain}_intent"
            valid = VALID_VALUES.get(intent_key, [])
            if valid and value not in valid:
                print(f"[SlotExtractor] Invalid intent '{value}' for {domain}")
                slots[key] = "general"
            else:
                slots[key] = value

        elif key in VALID_VALUES:
            if value not in VALID_VALUES[key]:
                print(f"[SlotExtractor] Invalid value for '{key}': {value}")
                continue
            slots[key] = value

        elif key in ("months_unemployed", "employment_years", "service_years",
                      "basic_salary", "gross_salary", "epf_deducted", "esi_deducted",
                      "employee_count", "last_drawn_salary", "notice_period_days",
                      "annual_income", "rent_paid", "section_80c_investments",
                      "pf_withdrawal_amount", "age"):
            try:
                slots[key] = int(float(str(value)))
            except (ValueError, TypeError):
                print(f"[SlotExtractor] Cannot cast '{key}' to int: {value}")

        elif key in ("is_pregnant", "has_form16"):
            if isinstance(value, bool):
                slots[key] = value
            elif str(value).lower() in ("true", "yes", "1"):
                slots[key] = True
            elif str(value).lower() in ("false", "no", "0"):
                slots[key] = False

        elif key in ("employer_name", "state"):
            slots[key] = str(value).strip()

        else:
            slots[key] = value

    return slots


# ══════════════════════════════════════════════════════════════════════════════
# KEYWORD / REGEX BASELINE — no LLM
# ══════════════════════════════════════════════════════════════════════════════


def baseline_extract(user_query: str, domain: str) -> dict:
    """
    Baseline slot extractor using regex and keyword matching only.
    No LLM calls. Returns same schema as LLM extractor.
    """
    if domain == "pf":
        return _baseline_pf(user_query)
    elif domain == "payslip":
        return _baseline_payslip(user_query)
    elif domain == "labour":
        return _baseline_labour(user_query)
    elif domain == "tax":
        return _baseline_tax(user_query)
    return {"intent": "general"}


def _extract_amount(text, keywords=None):
    """
    Extract rupee amount near optional keywords.
    Handles: Rs 50000, ₹50,000, 50000 rupees, 14.5 lakhs, 11 lpa
    """
    # Lakh conversion: "14.5 lakhs", "6.5 lakh", "11 lpa", "8 lakh"
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:lakhs?|lacs?|lpa|lac)\b', text, re.I)
    if m:
        return int(float(m.group(1)) * 100000)

    # Direct amount: Rs 50000, ₹50,000, 50000 rupees
    patterns = [
        r'(?:Rs\.?|₹|INR)\s*([\d,]+)',
        r'([\d,]+)\s*(?:rupees?|rs\.?|₹)',
        r'(?:amount|salary|basic|gross|rent|withdraw|income)\s*(?:is|of|was|=|:)?\s*(?:Rs\.?|₹)?\s*([\d,]+)',
    ]
    if keywords:
        kw_pattern = '|'.join(re.escape(k) for k in keywords)
        patterns.insert(0, rf'(?:{kw_pattern})\s*(?:is|of|was|=|:)?\s*(?:Rs\.?|₹)?\s*([\d,]+)')

    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            val = int(m.group(1).replace(",", ""))
            if val > 100:  # avoid matching small numbers like years
                return val
    return None


def _extract_state(text):
    """Extract Indian state from city/state names in text."""
    t = text.lower()
    for alias, state in STATE_ALIASES.items():
        if alias in t:
            return state
    return None


def _extract_years(text, keywords=None):
    """Extract years (integer, rounded down) from text."""
    patterns = [
        r'(\d+)\s*(?:years?|yrs?)\s*(?:\d+\s*months?)?',
        r'(\d+(?:\.\d+)?)\s*(?:years?|yrs?)',
    ]
    if keywords:
        kw_pattern = '|'.join(re.escape(k) for k in keywords)
        patterns.insert(0, rf'(?:{kw_pattern})\s*(?:of|is|was)?\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)?')

    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return int(float(m.group(1)))
    return None


# ── PF baseline ───────────────────────────────────────────────────────────────


def _baseline_pf(query: str) -> dict:
    slots = dict(SLOT_SCHEMA_PF)
    q = query.lower()

    # Intent
    if any(w in q for w in ["employer", "non deposit", "not deposit", "not showing in portal",
                            "nahi deposit", "non-deposit", "not credited"]):
        slots["intent"] = "employer_complaint"
    elif any(w in q for w in ["kyc", "aadhaar", "aadhar", "uan seed", "name mismatch"]):
        slots["intent"] = "kyc_issue"
    elif any(w in q for w in ["tds", "tax deduct"]):
        slots["intent"] = "tds_query"
    elif any(w in q for w in ["transfer", "shift pf"]):
        slots["intent"] = "transfer"
    elif any(w in q for w in ["partial", "advance", "form 31"]):
        slots["intent"] = "partial_withdrawal"
    elif any(w in q for w in ["withdraw", "withdrawal", "settlement", "nikalna",
                               "nikal", "form 19", "claim"]):
        slots["intent"] = "full_withdrawal"
    elif any(w in q for w in ["pension", "eps"]):
        slots["intent"] = "pension"
    elif any(w in q for w in ["nomination", "nominee"]):
        slots["intent"] = "nomination_update"
    else:
        slots["intent"] = "general"

    # Employment status
    if any(w in q for w in ["unemployed", "left job", "quit", "resigned", "left my job",
                            "job chhod", "company left"]):
        slots["employment_status"] = "unemployed"
    elif any(w in q for w in ["retired", "retirement"]):
        slots["employment_status"] = "retired"
    elif any(w in q for w in ["employed", "working", "currently", "new joiner"]):
        slots["employment_status"] = "employed"

    # Months unemployed
    m = re.search(r'(\d+)\s*months?\s*(?:ago|back|since|unemployed|ho gaye)', q)
    if m:
        slots["months_unemployed"] = int(m.group(1))
    m = re.search(r'(\d+)\s*weeks?\s*(?:ago|back|since)', q)
    if m:
        slots["months_unemployed"] = max(1, int(m.group(1)) // 4)

    # Service years
    slots["service_years"] = _extract_years(q, ["service", "worked", "kaam"])

    # UAN status
    if "uan" in q:
        if "active" in q:
            slots["uan_status"] = "active"
        elif "inactive" in q:
            slots["uan_status"] = "inactive"
        elif any(w in q for w in ["not generated", "not seeded"]):
            slots["uan_status"] = "not_generated"

    # KYC status
    if "kyc" in q or "aadhaar" in q or "aadhar" in q:
        if any(w in q for w in ["done", "complete", "approved"]):
            slots["kyc_status"] = "complete"
        elif any(w in q for w in ["reject", "rejected"]):
            slots["kyc_status"] = "rejected"
        elif any(w in q for w in ["incomplete", "not done", "partial"]):
            slots["kyc_status"] = "incomplete"

    # Employer name — very basic: look for "company <name>" or "employer <name>"
    m = re.search(r'(?:company|employer)\s+([a-zA-Z][\w\s]{2,30}?)(?:\s*,|\s+(?:deducted|not|hasn|is|hai|me|ne|ka))', q)
    if m:
        slots["employer_name"] = m.group(1).strip().lower()

    # Incident type
    if slots["intent"] == "employer_complaint":
        if any(w in q for w in ["non deposit", "not deposit", "not showing",
                                "nahi deposit", "zero credit", "hasn't deposited"]):
            slots["incident_type"] = "non_deposit"
        elif any(w in q for w in ["wrong amount", "less amount", "kam deposit"]):
            slots["incident_type"] = "wrong_amount"

    return slots


# ── Payslip baseline ──────────────────────────────────────────────────────────


def _baseline_payslip(query: str) -> dict:
    slots = dict(SLOT_SCHEMA_PAYSLIP)
    q = query.lower()

    # Intent
    if any(w in q for w in ["full audit", "complete audit", "complete salary"]):
        slots["intent"] = "full_audit"
    elif any(w in q for w in ["minimum wage", "min wage", "milna chahiye"]):
        slots["intent"] = "check_minimum_wage"
    elif any(w in q for w in ["epf", "pf deduct", "pf kata", "pf contribution", "provident fund"]):
        slots["intent"] = "verify_epf"
    elif any(w in q for w in ["esi", "esic"]):
        slots["intent"] = "verify_esi"
    elif any(w in q for w in ["bonus", "statutory bonus"]):
        slots["intent"] = "check_bonus"
    elif any(w in q for w in ["professional tax", "pt ", "deduction", "deducted", "kata"]):
        slots["intent"] = "check_deductions"
    else:
        slots["intent"] = "general"

    # Basic salary
    m = re.search(r'basic\s*(?:salary|pay|is|of|=|:)?\s*(?:Rs\.?|₹)?\s*([\d,]+)', q)
    if m:
        slots["basic_salary"] = int(m.group(1).replace(",", ""))

    # Gross salary
    m = re.search(r'gross\s*(?:salary|pay|is|of|=|:)?\s*(?:Rs\.?|₹)?\s*([\d,]+)', q)
    if m:
        slots["gross_salary"] = int(m.group(1).replace(",", ""))

    # EPF deducted
    m = re.search(r'(?:epf|pf)\s*(?:deduct\w*|cut|kata|is)?\s*(?:Rs\.?|₹)?\s*([\d,]+)', q)
    if m:
        val = int(m.group(1).replace(",", ""))
        if val < 50000:  # sanity check — PF deduction won't be huge
            slots["epf_deducted"] = val

    # ESI deducted
    if "no esi" in q or "esi band" in q or "esi nahi" in q:
        slots["esi_deducted"] = 0
    else:
        m = re.search(r'esi\s*(?:deduct\w*|cut|kata|is|they cut)?\s*(?:Rs\.?|₹|around|is)?\s*([\d,]+)', q)
        if m:
            val = int(m.group(1).replace(",", ""))
            if val < 10000:
                slots["esi_deducted"] = val

    # State
    slots["state"] = _extract_state(q)

    # Employee count
    m = re.search(r'(\d+)\s*(?:employees?|workers?|staff)', q)
    if m:
        slots["employee_count"] = int(m.group(1))

    return slots


# ── Labour baseline ───────────────────────────────────────────────────────────


def _baseline_labour(query: str) -> dict:
    slots = dict(SLOT_SCHEMA_LABOUR)
    q = query.lower()

    # Intent
    if any(w in q for w in ["gratuity"]):
        slots["intent"] = "gratuity"
    elif any(w in q for w in ["maternity", "pregnant", "pregnancy"]):
        slots["intent"] = "maternity_benefit"
    elif any(w in q for w in ["overtime", "ot pay", "extra hours", "12 hours"]):
        slots["intent"] = "overtime_pay"
    elif any(w in q for w in ["notice period", "notice"]):
        slots["intent"] = "notice_period"
    elif any(w in q for w in ["fired", "terminated", "termination", "nikala",
                               "wrongful", "retrenchment", "retrenched"]):
        slots["intent"] = "wrongful_termination"
    else:
        slots["intent"] = "general"

    # Employment years
    slots["employment_years"] = _extract_years(q, ["worked", "service", "kaam"])

    # Termination reason
    if any(w in q for w in ["resigned", "resignation", "resign", "quit", "left", "leaving"]):
        slots["termination_reason"] = "resignation"
    elif any(w in q for w in ["misconduct", "dismissed for"]):
        slots["termination_reason"] = "misconduct"
    elif any(w in q for w in ["fired", "terminated", "nikala", "removed"]):
        slots["termination_reason"] = "employer_terminated"
    elif any(w in q for w in ["retrenched", "retrenchment", "laid off", "layoff"]):
        slots["termination_reason"] = "retrenched"

    # Last drawn salary
    m = re.search(r'(?:salary|basic|gross|pay)\s*(?:was|is|of)?\s*(?:Rs\.?|₹)?\s*([\d,]+)', q)
    if m:
        val = int(m.group(1).replace(",", ""))
        if val > 1000:
            slots["last_drawn_salary"] = val

    # Is pregnant
    if any(w in q for w in ["pregnant", "expecting mother", "pregnancy", "maternity"]):
        slots["is_pregnant"] = True

    # Employer type
    if any(w in q for w in ["government", "govt", "sarkari", "public sector"]):
        slots["employer_type"] = "government"
    elif any(w in q for w in ["factory"]):
        slots["employer_type"] = "factory"
    elif any(w in q for w in ["shop", "retail", "store", "establishment"]):
        slots["employer_type"] = "shop_establishment"
    elif any(w in q for w in ["private", "pvt", "company", "it firm", "startup"]):
        slots["employer_type"] = "private"

    # State
    slots["state"] = _extract_state(q)

    # Notice period days
    m = re.search(r'(\d+)\s*days?\s*notice', q)
    if m:
        slots["notice_period_days"] = int(m.group(1))
    m = re.search(r'(\d+)\s*months?\s*notice', q)
    if m:
        slots["notice_period_days"] = int(m.group(1)) * 30

    return slots


# ── Tax baseline ──────────────────────────────────────────────────────────────


def _baseline_tax(query: str) -> dict:
    slots = dict(SLOT_SCHEMA_TAX)
    q = query.lower()

    # Intent
    if any(w in q for w in ["hra", "house rent", "rent allowance"]):
        slots["intent"] = "hra_exemption"
    elif any(w in q for w in ["80c", "80d", "deduction under", "section 80"]):
        slots["intent"] = "deductions_80c"
    elif any(w in q for w in ["form 16", "form16"]):
        slots["intent"] = "form16"
    elif any(w in q for w in ["refund"]):
        slots["intent"] = "refund_status"
    elif any(w in q for w in ["pf withdrawal", "pf nikalne", "pf withdraw"]) and "tds" in q:
        slots["intent"] = "tds_on_pf"
    elif any(w in q for w in ["pf withdrawal", "withdrew pf", "pf amount", "pf nikalne"]):
        slots["intent"] = "tds_on_pf"
    elif any(w in q for w in ["tds", "tax", "salary", "income"]):
        slots["intent"] = "tds_on_salary"
    elif any(w in q for w in ["itr", "it return", "return file"]):
        slots["intent"] = "itr_filing"
    else:
        slots["intent"] = "general"

    # Annual income (handles lakhs)
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:lakhs?|lacs?|lpa|lac)\b', q)
    if m:
        slots["annual_income"] = int(float(m.group(1)) * 100000)
    else:
        m = re.search(r'(?:income|salary)\s*(?:is|of|was)?\s*(?:Rs\.?|₹)?\s*([\d,]+)', q)
        if m:
            val = int(m.group(1).replace(",", ""))
            if val > 50000:  # likely annual
                slots["annual_income"] = val

    # Tax regime
    if any(w in q for w in ["old regime", "old scheme", "purana"]):
        slots["tax_regime"] = "old_regime"
    elif any(w in q for w in ["new regime", "new scheme", "naya", "new tax"]):
        slots["tax_regime"] = "new_regime"

    # Rent paid
    m = re.search(r'(?:rent|paying)\s*(?:is|of|=|:)?\s*(?:Rs\.?|₹)?\s*([\d,]+)', q)
    if m:
        slots["rent_paid"] = int(m.group(1).replace(",", ""))

    # City type (metro = only Delhi, Mumbai, Kolkata, Chennai)
    # Check for explicit "metro" / "non-metro" first
    if "non-metro" in q or "non metro" in q:
        slots["city_type"] = "non_metro"
    elif "metro" in q:
        # Check if they mention a specific metro city
        slots["city_type"] = "metro"
    else:
        # Infer from city names
        for city in METRO_CITIES:
            if city in q:
                slots["city_type"] = "metro"
                break
        else:
            # Check for non-metro cities
            non_metro_cities = ["bangalore", "bengaluru", "hyderabad", "pune",
                                "ahmedabad", "jaipur", "lucknow", "chandigarh"]
            for city in non_metro_cities:
                if city in q:
                    slots["city_type"] = "non_metro"
                    break

    # Has form 16
    if any(w in q for w in ["form 16 nahi", "form 16 not", "haven't received",
                            "nahi mila", "not received", "no form 16"]):
        slots["has_form16"] = False
    elif any(w in q for w in ["have form 16", "form 16 received", "got form 16"]):
        slots["has_form16"] = True

    # Section 80C investments
    m = re.search(r'80[cC]\s*(?:investment|invest|amount)?\s*(?:is|of|are)?\s*(\d+(?:\.\d+)?)\s*(?:lakhs?|lacs?|lac)?\s*', q)
    if m:
        val = float(m.group(1))
        has_lakh = re.search(r'80[cC].*' + re.escape(m.group(1)) + r'\s*(?:lakhs?|lacs?|lac)', q)
        if has_lakh or val < 10:
            slots["section_80c_investments"] = int(val * 100000)
        else:
            slots["section_80c_investments"] = int(val)

    # PF withdrawal amount
    m = re.search(r'(?:pf|provident fund)\s*(?:amount|withdrawal|withdrew|nikala)?\s*(?:of|is|was)?\s*(?:Rs\.?|₹)?\s*([\d,]+)', q)
    if m:
        val = int(m.group(1).replace(",", ""))
        if val > 1000:
            slots["pf_withdrawal_amount"] = val

    # Service years
    slots["service_years"] = _extract_years(q, ["service", "worked", "kaam"])

    return slots


# ══════════════════════════════════════════════════════════════════════════════
# MERGE — for multi-turn slot accumulation
# ══════════════════════════════════════════════════════════════════════════════

# Slots that shouldn't be overwritten once filled (preserve first answer)
STICKY_SLOTS = {"intent", "employment_status"}


def merge_slots(existing: dict, new_extraction: dict) -> dict:
    """Merge new slot extraction into existing accumulated slots."""
    merged = dict(existing)
    for key, value in new_extraction.items():
        if value is not None:
            if key in STICKY_SLOTS and merged.get(key) is not None:
                continue
            merged[key] = value
    return merged


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_cases = [
        ("pf", "I quit exactly 4 months ago. UAN is perfectly active and KYC approved. Need total settlement."),
        ("payslip", "basic is around 18500 and esi they cut is around 500, verify esi"),
        ("labour", "resigned after working for 6 years 2 months. last drawn salary gross was 40500."),
        ("tax", "income is 14.5 lakhs, opt for the old regime, paying rent 25000 in metro. checking hra."),
        ("pf", "company reliance retail deducted pf but not showing in portal"),
        ("labour", "factory work 12 hours daily, no overtime paid, Gujarat factory"),
        ("tax", "form 16 nahi mila employer se, ITR filing deadline is next week"),
    ]

    for domain, query in test_cases:
        print(f"\n{'─'*60}")
        print(f"Domain: {domain}")
        print(f"Query:  {query[:70]}")
        bl = baseline_extract(query, domain)
        print(f"Baseline: {json.dumps({k:v for k,v in bl.items() if v is not None})}")
        try:
            llm = extract_slots(query, domain)
            print(f"LLM:      {json.dumps({k:v for k,v in llm.items() if v is not None})}")
        except Exception as e:
            print(f"LLM:      ERROR — {e}")
