
"""
ShramikSaathi — Stage 2.1: DPO Dataset Generator (v2, hybrid template + LLM)

GENERATION STRATEGY (Path D rewrite):
    - Dimensions 1-3 (grounding, verdict, citation): chosen + rejected both
      TEMPLATE-BASED. Rejected derived deterministically from chosen via
      verdict-flip / citation-permute / rule-fabrication transformations.
      Zero LLM calls. ~95% pass rate expected.
    - Dimension 4 (refusal_and_escalation): chosen is templated refusal,
      rejected is LLM-generated using GENERATOR_PROMPT (NOT contrastive) —
      just ask the question, let the teacher naturally hallucinate.

CHOSEN SYNTHESIS (Option A+):
    - SFT-accepted response if one exists for (intent, slot_combo)
    - Else: deterministic template

TARGETS:
    PF 150 | Payslip 100 | Labour 90 | Tax 60
    grounding 110 | verdict 110 | citation 100 | refusal_escalation 80
    (24 out-of-scope + 56 kb-insufficient within dim 4)

Run from project root:
    python scripts/generate_dpo_dataset.py
"""

import os
import re
import json
import time
import random
import traceback
from pathlib import Path
from collections import Counter, defaultdict

random.seed(42)


# ════════════════════════════════════════════════════════════════════════════
# PATHS & CONFIG
# ════════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KB_PATH            = PROJECT_ROOT / "data" / "kb.jsonl"
SFT_FIRSTRUN_PATH  = PROJECT_ROOT / "data" / ".sft_incremental.firstrun.jsonl"
SFT_RUN2_PATH      = PROJECT_ROOT / "data" / ".sft_incremental.jsonl"

OUTPUT_PATH        = PROJECT_ROOT / "data" / "dpo_pairs.jsonl"
INCREMENTAL_PATH   = PROJECT_ROOT / "data" / ".dpo_incremental.jsonl"
STATS_PATH         = PROJECT_ROOT / "data" / "dpo_generation_stats.json"
LOG_PATH           = PROJECT_ROOT / "data" / "dpo_generation.log"

MODEL_ID       = "meta-llama/Llama-3.1-8B-Instruct"
BATCH_SIZE     = 4
MAX_NEW_TOKENS = 600
TEMPERATURE    = 0.8
TOP_P          = 0.9

DOMAIN_TARGETS = {
    "pf":      150,
    "payslip": 100,
    "labour":  90,
    "tax":     60,
}

DIMENSION_TARGETS = {
    "grounding":              110,
    "verdict_correctness":    110,
    "citation_discipline":    100,
    "refusal_and_escalation":  80,
}

REFUSAL_SUB_SPLIT = {
    "out_of_scope":            24,
    "kb_insufficient":         56,
}


# ════════════════════════════════════════════════════════════════════════════
# GENERATOR PROMPT (copied from src/pipeline.py — keep in sync)
# ════════════════════════════════════════════════════════════════════════════

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


def format_passages_for_prompt(passages):
    parts = []
    for i, r in enumerate(passages):
        parts.append(
            f"[Source {i+1}] doc_id={r['doc_id']} | "
            f"date={r.get('effective_date')} | domain={r.get('domain','')}\n"
            f"{r['content'][:1500]}"
        )
    return "\n\n---\n\n".join(parts)


def build_generator_input(query, domain, passages, slots):
    passages_text = format_passages_for_prompt(passages)
    filled = {k: v for k, v in slots.items() if v is not None}
    return f"""USER QUERY:
{query}

DOMAIN: {domain}

RETRIEVED PASSAGES:
{passages_text}



SLOTS FILLED:
{json.dumps(filled, indent=2)}

Produce the final answer now. IMPORTANT: every factual claim must include [DOC_ID] in brackets — no exceptions. If you cannot cite, omit the claim."""


# ════════════════════════════════════════════════════════════════════════════
# KB LOAD
# ════════════════════════════════════════════════════════════════════════════

def load_kb():
    by_id = {}
    by_subdomain = defaultdict(list)
    with open(KB_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if len(d.get("content", "")) < 50:
                continue
            did = d.get("doc_id", "")
            if not did:
                continue
            by_id[did] = d
            by_subdomain[(d.get("domain",""), d.get("subdomain",""))].append(did)
    print(f"[KB] {len(by_id)} docs")
    return by_id, by_subdomain


# ════════════════════════════════════════════════════════════════════════════
# SFT RESPONSES (for Option A+ chosen reuse)
# ════════════════════════════════════════════════════════════════════════════

def load_sft_responses():
    responses = {}
    for path in [SFT_FIRSTRUN_PATH, SFT_RUN2_PATH]:
        if not path.exists():
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ex = json.loads(line)
                    intent = ex["metadata"]["intent"]
                    slots = ex["metadata"].get("slot_combination", {})
                    asst = next((m for m in ex["messages"] if m["role"] == "assistant"), None)
                    if not asst:
                        continue
                    slot_key = _slot_key(slots)
                    responses[(intent, slot_key)] = {
                        "response":  asst["content"],
                        "passages":  ex["metadata"].get("passage_doc_ids", []),
                        "slots":     slots,
                    }
                except Exception:
                    continue
    print(f"[SFT] {len(responses)} accepted responses indexed for reuse")
    return responses


def _slot_key(slots):
    items = sorted((k, v) for k, v in slots.items() if v is not None)
    return "|".join(f"{k}={v}" for k, v in items)


# ════════════════════════════════════════════════════════════════════════════
# INTENT CONFIGS
# ════════════════════════════════════════════════════════════════════════════

INTENT_CONFIGS = {
    "full_withdrawal": {
        "domain": "pf", "subdomains": ["withdrawal"], "cross_doc_ids": ["CIRC_2024_TDS"],
        "templates": [
            "Resigned {months_unemployed} months ago after {service_years} years service. UAN {uan_status}, KYC {kyc_status}. Can I withdraw full PF?",
            "Left my job {months_unemployed} months back, {service_years} years service. UAN {uan_status}, KYC {kyc_status}. Full PF withdrawal karna hai.",
        ],
        "slot_ranges": {
            "employment_status": ["unemployed"],
            "months_unemployed": [1, 2, 3, 4, 6],
            "service_years":     [2, 3, 4, 5, 6, 8, 10],
            "uan_status":        ["active"],
            "kyc_status":        ["complete", "partial"],
        },
    },
    "tds_query": {
        "domain": "pf", "subdomains": ["taxation", "withdrawal"], "cross_doc_ids": ["CIRC_2024_TDS"],
        "templates": [
            "Withdrew PF ₹{pf_withdrawal_amount} after {service_years} years. TDS?",
            "PF nikala ₹{pf_withdrawal_amount}, service {service_years} saal. TDS?",
        ],
        "slot_ranges": {
            "pf_withdrawal_amount": [30000, 55000, 80000, 150000],
            "service_years":        [2, 3, 4, 5, 6],
        },
    },
    "transfer": {
        "domain": "pf", "subdomains": ["transfer"], "cross_doc_ids": [],
        "templates": [
            "Changed jobs, transfer PF. UAN {uan_status}, KYC {kyc_status}.",
        ],
        "slot_ranges": {
            "uan_status": ["active"],
            "kyc_status": ["complete", "partial"],
        },
    },
    "kyc_issue": {
        "domain": "pf", "subdomains": ["kyc", "uan"], "cross_doc_ids": [],
        "templates": [
            "My KYC is {kyc_status} on EPFO portal. What to do?",
        ],
        "slot_ranges": {
            "kyc_status": ["rejected", "incomplete", "partial"],
        },
    },
    "verify_epf": {
        "domain": "payslip", "subdomains": ["epf_deduction"], "cross_doc_ids": [],
        "templates": [
            "Basic salary ₹{basic_salary}, EPF deducted ₹{epf_deducted}. Correct?",
        ],
        "slot_ranges": {
            "basic_salary":  [12000, 15000, 18000, 20000, 25000, 30000],
            "epf_deducted":  None,
            "gross_salary":  None,
        },
        "use_payslip_tool": True,
    },
    "verify_esi": {
        "domain": "payslip", "subdomains": ["esi_deduction"], "cross_doc_ids": [],
        "templates": [
            "Gross salary ₹{gross_salary}, ESI ₹{esi_deducted}. Correct?",
        ],
        "slot_ranges": {
            "gross_salary":  [15000, 18000, 20000, 22000, 25000],
            "esi_deducted":  None,
            "basic_salary":  None,
        },
        "use_payslip_tool": True,
    },
    "check_minimum_wage": {
        "domain": "payslip", "subdomains": ["minimum_wage"], "cross_doc_ids": [],
        "templates": [
            "Unskilled worker in {state}, gross ₹{gross_salary}/month. Minimum wage?",
        ],
        "slot_ranges": {
            "state":        ["Maharashtra", "Karnataka", "Gujarat", "Tamil Nadu", "Delhi"],
            "gross_salary": [8000, 10000, 12000, 14000, 16000],
        },
    },
    "gratuity": {
        "domain": "labour", "subdomains": ["gratuity"], "cross_doc_ids": [],
        "templates": [
            "Worked {employment_years} years at {employer_type} company. {termination_reason}. Last salary ₹{last_drawn_salary}. Gratuity?",
        ],
        "slot_ranges": {
            "employment_years":   [3, 4, 5, 6, 7, 10],
            "termination_reason": ["resignation", "retirement", "employer_terminated"],
            "employer_type":      ["private", "factory"],
            "last_drawn_salary":  [25000, 35000, 45000, 60000],
        },
    },
    "wrongful_termination": {
        "domain": "labour", "subdomains": ["termination"], "cross_doc_ids": [],
        "templates": [
            "Worked {employment_years} years. Employer terminated without notice at {employer_type} company.",
        ],
        "slot_ranges": {
            "employment_years":   [1, 2, 3, 5],
            "termination_reason": ["employer_terminated"],
            "employer_type":      ["private", "factory"],
        },
    },
    "maternity_benefit": {
        "domain": "labour", "subdomains": ["maternity"], "cross_doc_ids": [],
        "templates": [
            "Pregnant, {employment_years} years at {employer_type} company. Employer offering {notice_period_days} days maternity leave.",
        ],
        "slot_ranges": {
            "is_pregnant":        [True],
            "employment_years":   [1, 2, 3, 5],
            "employer_type":      ["private", "factory"],
            "notice_period_days": [60, 84, 90, 120],
        },
    },
    "tds_on_salary": {
        "domain": "tax", "subdomains": ["tds_salary"], "cross_doc_ids": [],
        "templates": [
            "Annual income ₹{annual_income}, {tax_regime}. Monthly TDS?",
        ],
        "slot_ranges": {
            "annual_income": [500000, 700000, 1000000, 1500000],
            "tax_regime":    ["old_regime", "new_regime"],
        },
    },
    "hra_exemption": {
        "domain": "tax", "subdomains": ["hra"], "cross_doc_ids": [],
        "templates": [
            "Income ₹{annual_income}, {tax_regime}, rent ₹{rent_paid} in {city_type} city. HRA exemption?",
        ],
        "slot_ranges": {
            "annual_income": [600000, 900000, 1200000, 1800000],
            "tax_regime":    ["old_regime"],
            "rent_paid":     [12000, 18000, 25000, 35000],
            "city_type":     ["metro", "non_metro"],
        },
    },
    "deductions_80c": {
        "domain": "tax", "subdomains": ["deductions"], "cross_doc_ids": [],
        "templates": [
            "Income ₹{annual_income}, {tax_regime}, invested ₹{section_80c_investments} in 80C.",
        ],
        "slot_ranges": {
            "annual_income":           [700000, 1000000, 1500000],
            "tax_regime":              ["old_regime", "new_regime"],
            "section_80c_investments": [50000, 100000, 150000],
        },
    },
}


# ════════════════════════════════════════════════════════════════════════════
# SLOT SAMPLING + PASSAGE SELECTION
# ════════════════════════════════════════════════════════════════════════════

def sample_slots(intent, cfg, rng):
    slots = {"intent": intent}
    for field, values in cfg["slot_ranges"].items():
        if values is None:
            continue
        slots[field] = rng.choice(values)

    if intent == "verify_epf":
        basic = slots["basic_salary"]
        expected = round(basic * 0.12)
        slots["epf_deducted"] = expected if rng.random() < 0.6 else expected + rng.choice([-600, -300, 300])
        slots["gross_salary"] = basic + rng.choice([3000, 5000, 7000])
    elif intent == "verify_esi":
        gross = slots["gross_salary"]
        if gross > 21000:
            slots["esi_deducted"] = rng.choice([0, 0, 150])
        else:
            expected = round(gross * 0.0075)
            slots["esi_deducted"] = expected if rng.random() < 0.6 else expected + rng.choice([-30, 50])
        slots["basic_salary"] = max(gross - rng.choice([3000, 5000]), 8000)
    return slots


def build_query(cfg, slots, rng):
    template = rng.choice(cfg["templates"])
    try:
        return template.format(**{k: v for k, v in slots.items() if v is not None})
    except KeyError:
        return None


def select_passages(kb_by_id, kb_by_subdomain, cfg, rng, max_passages=3):
    domain = cfg["domain"]
    candidates = []
    for sub in cfg["subdomains"]:
        candidates.extend(kb_by_subdomain.get((domain, sub), []))
    if not candidates:
        return []
    n = min(rng.randint(1, 2) + 1, max_passages, len(candidates))
    picked = rng.sample(candidates, n)
    for cd in cfg.get("cross_doc_ids", []):
        if cd in kb_by_id and cd not in picked:
            picked.append(cd)
    return [kb_by_id[d] for d in picked if d in kb_by_id]


def add_payslip_tool(passages, slots):
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from tools import parse_payslip, format_payslip_result
    result = parse_payslip(slots)
    formatted = format_payslip_result(result)
    return passages + [{
        "doc_id":         "TOOL_PAYSLIP_AUDIT",
        "title":          "Payslip Audit Calculation",
        "content":        formatted,
        "domain":         "payslip",
        "subdomain":      "tool_output",
        "effective_date": None,
    }]


# ════════════════════════════════════════════════════════════════════════════
# CHOSEN SYNTHESIS (Option A+)
# ════════════════════════════════════════════════════════════════════════════

def synthesize_chosen(intent, slots, passages, sft_responses):
    slot_key = _slot_key(slots)
    sft_match = sft_responses.get((intent, slot_key))
    if sft_match:
        return sft_match["response"], "sft_reuse"
    return synthesize_template_chosen(intent, slots, passages), "template"


def synthesize_template_chosen(intent, slots, passages):
    passage_ids = [p["doc_id"] for p in passages]
    primary = passage_ids[0] if passage_ids else "UNKNOWN"
    has_tds = "CIRC_2024_TDS" in passage_ids

    if intent == "full_withdrawal":
        mo = slots.get("months_unemployed", 0)
        yr = slots.get("service_years", 0)
        if mo < 2:
            return (
                f"**Result:** Not eligible for full PF withdrawal yet.\n\n"
                f"**Reason [{primary}]:** Unemployment period of {mo} month(s) is below the 2-month minimum required.\n\n"
                f"**Next Steps:**\n"
                f"1. Wait until you complete 2 months of continuous unemployment.\n"
                f"2. Ensure UAN stays active and KYC remains complete.\n"
                f"3. After 2 months, submit Form 19 through the EPFO Unified Member Portal [{primary}]."
            )
        if yr >= 5:
            tds_cite = f" [CIRC_2024_TDS]" if has_tds else ""
            return (
                f"**Result:** Eligible for full PF withdrawal.\n\n"
                f"**Reasoning [{primary}]:**\n"
                f"- Unemployment of {mo} months exceeds the 2-month threshold\n"
                f"- Service of {yr} years exceeds the 5-year TDS threshold{tds_cite}, so no TDS applies\n\n"
                f"**Next Steps:**\n"
                f"1. Login to unifiedportal-mem.epfindia.gov.in\n"
                f"2. Online Services → Claim Form 19\n"
                f"3. Verify bank account matches KYC record\n"
                f"4. Submit. Processing time approximately 20 working days [{primary}]."
            )
        tds_cite = f" [CIRC_2024_TDS]" if has_tds else ""
        return (
            f"**Result:** Eligible for full PF withdrawal with TDS applicable.\n\n"
            f"**Reasoning:**\n"
            f"- Unemployment of {mo} months meets the 2-month requirement [{primary}]\n"
            f"- Service of {yr} years is below the 5-year TDS threshold{tds_cite}\n\n"
            f"**TDS Warning{tds_cite}:** TDS at 10% applies if withdrawal exceeds ₹50,000 and PAN is linked.\n\n"
            f"**Next Steps:**\n"
            f"1. Submit Form 19 via EPFO Unified Member Portal.\n"
            f"2. Submit Form 15G if total taxable income is below threshold{tds_cite}."
        )

    if intent == "tds_query":
        amt = slots.get("pf_withdrawal_amount", 0)
        yr  = slots.get("service_years", 0)
        if yr >= 5:
            return (
                f"**Result:** No TDS applies on your PF withdrawal.\n\n"
                f"**Reason [{primary}]:** Service period of {yr} years exceeds the 5-year threshold.\n\n"
                f"**Next Steps:**\n"
                f"1. Withdraw full amount via Form 19.\n"
                f"2. No Form 15G required [{primary}]."
            )
        if amt <= 50000:
            return (
                f"**Result:** No TDS applies despite service under 5 years.\n\n"
                f"**Reason [{primary}]:** Withdrawal amount ₹{amt:,} is below the ₹50,000 threshold.\n\n"
                f"**Next Steps:**\n"
                f"1. Proceed with withdrawal via Form 19.\n"
                f"2. No TDS deducted [{primary}]."
            )
        return (
            f"**Result:** TDS at 10% applies on your PF withdrawal.\n\n"
            f"**Reasoning [{primary}]:**\n"
            f"- Service of {yr} years is below the 5-year threshold\n"
            f"- Withdrawal amount ₹{amt:,} exceeds the ₹50,000 threshold\n\n"
            f"**How to reduce TDS:**\n"
            f"1. Submit Form 15G if total annual income is below taxable limit.\n"
            f"2. Ensure PAN is linked to UAN — otherwise TDS rate is 30% [{primary}]."
        )

    if intent == "transfer":
        return (
            f"**Result:** PF transfer available through Form 13 [{primary}].\n\n"
            f"**Process [{primary}]:**\n"
            f"1. Login to EPFO Unified Member Portal.\n"
            f"2. Online Services → One Member One EPF Account.\n"
            f"3. Fill Form 13 online, get employer attestation.\n"
            f"4. Submit. Processing ~20 working days.\n\n"
            f"**Note:** UAN-Aadhaar seeding enables automatic transfer on job change."
        )

    if intent == "kyc_issue":
        return (
            f"**Result:** KYC issues resolved via EPFO Unified Member Portal [{primary}].\n\n"
            f"**Process [{primary}]:**\n"
            f"1. Login to unifiedportal-mem.epfindia.gov.in using UAN.\n"
            f"2. Manage → KYC.\n"
            f"3. Update the mismatched document (Aadhaar/PAN/bank).\n"
            f"4. Wait for employer digital approval.\n\n"
            f"**For Aadhaar name mismatch:** Correct via UIDAI portal first, then re-seed."
        )

    if intent == "verify_epf":
        basic = slots.get("basic_salary", 0)
        actual = slots.get("epf_deducted", 0)
        expected = round(basic * 0.12)
        tool_cite = "TOOL_PAYSLIP_AUDIT" if "TOOL_PAYSLIP_AUDIT" in passage_ids else primary
        if abs(expected - actual) <= 1:
            return (
                f"**Result:** EPF deduction of ₹{actual:,} is correct [{tool_cite}].\n\n"
                f"**Calculation [{tool_cite}]:**\n"
                f"- Basic salary: ₹{basic:,}\n"
                f"- EPF rate: 12% [{primary}]\n"
                f"- Expected: ₹{expected:,}\n"
                f"- Actual: ₹{actual:,} — **matches**"
            )
        return (
            f"**Result:** EPF deduction is incorrect [{tool_cite}].\n\n"
            f"**Calculation [{tool_cite}]:**\n"
            f"- Basic salary: ₹{basic:,}\n"
            f"- EPF rate: 12% [{primary}]\n"
            f"- Expected: ₹{expected:,}\n"
            f"- Actual: ₹{actual:,}\n"
            f"- Difference: ₹{actual - expected:,}\n\n"
            f"**Next Steps:**\n"
            f"1. Raise with HR/payroll.\n"
            f"2. If unresolved, file grievance on EPFiGMS [{primary}]."
        )

    if intent == "verify_esi":
        gross = slots.get("gross_salary", 0)
        actual = slots.get("esi_deducted", 0)
        tool_cite = "TOOL_PAYSLIP_AUDIT" if "TOOL_PAYSLIP_AUDIT" in passage_ids else primary
        if gross > 21000:
            if actual == 0:
                return (
                    f"**Result:** ESI correctly not deducted [{tool_cite}].\n\n"
                    f"**Reason [{primary}]:** Gross salary ₹{gross:,} exceeds ₹21,000 ESI threshold.\n\n"
                    f"**Calculation [{tool_cite}]:**\n"
                    f"- Gross: ₹{gross:,}\n"
                    f"- Threshold: ₹21,000\n"
                    f"- Applicable: No"
                )
            return (
                f"**Result:** ESI should not be deducted [{primary}].\n\n"
                f"**Reason [{primary}]:** Gross ₹{gross:,} exceeds ₹21,000 threshold.\n\n"
                f"**Action:** Ask employer to refund ₹{actual} wrongly deducted [{tool_cite}]."
            )
        expected = round(gross * 0.0075)
        if abs(expected - actual) <= 1:
            return (
                f"**Result:** ESI deduction of ₹{actual:,} is correct [{tool_cite}].\n\n"
                f"**Calculation [{tool_cite}]:**\n"
                f"- Gross: ₹{gross:,}\n"
                f"- Employee rate: 0.75% [{primary}]\n"
                f"- Expected: ₹{expected:,}\n"
                f"- Actual: ₹{actual:,} — **matches**"
            )
        return (
            f"**Result:** ESI deduction is incorrect [{tool_cite}].\n\n"
            f"**Calculation [{tool_cite}]:**\n"
            f"- Gross: ₹{gross:,}\n"
            f"- Expected (0.75%): ₹{expected:,} [{primary}]\n"
            f"- Actual: ₹{actual:,}\n"
            f"- Difference: ₹{actual - expected:,}"
        )

    if intent == "check_minimum_wage":
        gross = slots.get("gross_salary", 0)
        state = slots.get("state", "your state")
        return (
            f"**Result:** Requires verification against {state} minimum wage schedule [{primary}].\n\n"
            f"**Your salary:** ₹{gross:,}/month [{primary}].\n\n"
            f"**Action:**\n"
            f"1. Compare ₹{gross:,} against current unskilled minimum wage notified by {state}.\n"
            f"2. If below, complain to state labour commissioner [{primary}].\n"
            f"3. Underpayment is a criminal offence under the Minimum Wages Act."
        )

    if intent == "gratuity":
        yr = slots.get("employment_years", 0)
        reason = slots.get("termination_reason", "")
        salary = slots.get("last_drawn_salary", 0)
        if yr < 5:
            return (
                f"**Result:** Not eligible for gratuity [{primary}].\n\n"
                f"**Reason [{primary}]:** Payment of Gratuity Act requires 5 years continuous service. "
                f"You completed {yr} years.\n\n"
                f"**Note [{primary}]:** 240 days in the 5th year may qualify per some court rulings — consult state labour office."
            )
        amount = int(salary * 15 * yr / 26)
        return (
            f"**Result:** Eligible for gratuity [{primary}].\n\n"
            f"**Reasoning [{primary}]:**\n"
            f"- Continuous service of {yr} years meets the 5-year minimum\n"
            f"- {reason.replace('_', ' ').title()} is a qualifying termination reason\n\n"
            f"**Calculation [{primary}]:**\n"
            f"Gratuity = (Last salary × 15 × years) / 26\n"
            f"        = (₹{salary:,} × 15 × {yr}) / 26\n"
            f"        = ₹{amount:,}\n\n"
            f"**Next Steps:**\n"
            f"1. Submit Form I to employer within 30 days [{primary}].\n"
            f"2. Employer must pay within 30 days.\n"
            f"3. If unpaid, file with Controlling Authority."
        )

    if intent == "wrongful_termination":
        yr = slots.get("employment_years", 0)
        return (
            f"**Result:** You have legal remedies for wrongful termination [{primary}].\n\n"
            f"**Options [{primary}]:**\n"
            f"1. Send legal notice demanding reinstatement or compensation.\n"
            f"2. File complaint with Labour Commissioner.\n"
            f"3. Approach Labour Court / Industrial Tribunal under ID Act [{primary}].\n\n"
            f"**Note [{primary}]:** {yr} years of service strengthens your case for retrenchment compensation."
        )

    if intent == "maternity_benefit":
        offered = slots.get("notice_period_days", 0)
        return (
            f"**Result:** Your entitlement is 26 weeks, not {offered} days [{primary}].\n\n"
            f"**Legal Position [{primary}]:** Maternity Benefit (Amendment) Act 2017 entitles eligible women employees "
            f"to 26 weeks of paid maternity leave for first and second child.\n\n"
            f"**Next Steps [{primary}]:**\n"
            f"1. Inform HR in writing citing Maternity Benefit Act 2017.\n"
            f"2. If denied, complain to local Inspector under the Act.\n"
            f"3. Denial is a criminal offence under Section 21."
        )

    if intent == "tds_on_salary":
        income = slots.get("annual_income", 0)
        regime = slots.get("tax_regime", "")
        return (
            f"**Result:** TDS calculation depends on your regime and deductions [{primary}].\n\n"
            f"**Your inputs:** Income ₹{income:,}, {regime.replace('_', ' ')} [{primary}].\n\n"
            f"**Next Steps:**\n"
            f"1. Request Form 16 from employer for exact breakdown [{primary}].\n"
            f"2. Verify against applicable slab rates for your regime."
        )

    if intent == "hra_exemption":
        rent = slots.get("rent_paid", 0)
        basic = slots.get("annual_income", 0) // 12
        city = slots.get("city_type", "non_metro")
        pct = "50%" if city == "metro" else "40%"
        return (
            f"**Result:** HRA exemption is minimum of three values [{primary}].\n\n"
            f"**The three components [{primary}]:**\n"
            f"1. Actual HRA received from employer\n"
            f"2. Rent paid minus 10% of basic = ₹{rent:,} − ₹{basic//10:,} = ₹{rent - basic//10:,}\n"
            f"3. {pct} of basic salary ({city} city) = ₹{int(basic * (0.5 if city == 'metro' else 0.4)):,}\n\n"
            f"**The lowest of the three is your exemption [{primary}].**"
        )

    if intent == "deductions_80c":
        regime = slots.get("tax_regime", "")
        if regime == "new_regime":
            return (
                f"**Result:** Section 80C not available under new regime [{primary}].\n\n"
                f"**Reason [{primary}]:** New regime offers lower slabs in exchange for forgoing Chapter VI-A deductions.\n\n"
                f"**Your options [{primary}]:**\n"
                f"1. Continue in new regime, forgo 80C.\n"
                f"2. Switch to old regime to claim up to ₹1.5 lakh."
            )
        inv = slots.get("section_80c_investments", 0)
        claimable = min(inv, 150000)
        return (
            f"**Result:** You can claim ₹{claimable:,} under Section 80C [{primary}].\n\n"
            f"**Details [{primary}]:** 80C allows up to ₹1.5 lakh/year for eligible instruments "
            f"(PPF, ELSS, insurance, EPF, home loan principal).\n\n"
            f"**Next Steps:**\n"
            f"1. Report ₹{claimable:,} under 80C in ITR [{primary}].\n"
            f"2. Keep investment proofs for 7 years."
        )

    return f"**Result:** Requires additional context [{primary}]."


# ════════════════════════════════════════════════════════════════════════════
# REJECTED SYNTHESIS — TEMPLATE-BASED (dimensions 1-3)
# ════════════════════════════════════════════════════════════════════════════

DOC_ID_RE = re.compile(r'\[([A-Z][A-Z0-9_]+)\]')


def reject_verdict_flip(chosen_text, slots, rng):
    """
    Flip verdict keywords in the chosen response.
    Produces a rejected with the opposite verdict but similar structure.
    """
    text = chosen_text

    # Verdict flips — apply each possible transformation
    flips = [
        # eligible <-> not eligible (order matters: handle "not eligible" BEFORE "eligible")
        (r'\bNot [Ee]ligible\b', '__FLIP_A__'),
        (r'\bnot eligible\b', '__FLIP_A__'),
        (r'\b[Ii]neligible\b', '__FLIP_A__'),
        (r'\b[Ee]ligible\b', 'Not eligible'),
        ('__FLIP_A__', 'Eligible'),

        # correct <-> incorrect
        (r'\bis correct\b', '__FLIP_B__'),
        (r'\bis incorrect\b', 'is correct'),
        ('__FLIP_B__', 'is incorrect'),

        # matches <-> does not match
        (r'\b— \*\*matches\*\*', '— **does not match**'),
        (r'\bmatches expected\b', 'does not match expected'),

        # applicable <-> not applicable
        (r'\bnot applicable\b', '__FLIP_C__'),
        (r'\bApplicable: No\b', 'Applicable: Yes'),
        (r'\bApplicable: Yes\b', 'Applicable: No'),
        (r'\b[Aa]pplicable\b', 'not applicable'),
        ('__FLIP_C__', 'applicable'),
    ]
    for pattern, replacement in flips:
        text = re.sub(pattern, replacement, text)

    # Inject a plausible-sounding wrong threshold to justify the flipped verdict
    injection_patterns = [
        ("2-month", rng.choice(["4-month", "6-month", "1-month"])),
        ("5-year", rng.choice(["7-year", "10-year", "3-year"])),
        ("12% [", rng.choice(["10% [", "15% [", "8% ["])),
        ("0.75% [", rng.choice(["1.5% [", "0.5% [", "2% ["])),
        ("₹15,000", rng.choice(["₹12,000", "₹25,000", "₹20,000"])),
        ("₹21,000", rng.choice(["₹18,000", "₹25,000", "₹30,000"])),
        ("₹50,000", rng.choice(["₹75,000", "₹30,000", "₹1,00,000"])),
        ("26 weeks", rng.choice(["12 weeks", "16 weeks", "20 weeks"])),
    ]
    # Apply ONE random injection to avoid destroying readability
    injections_available = [(p, r) for p, r in injection_patterns if p in text]
    if injections_available:
        pat, rep = rng.choice(injections_available)
        text = text.replace(pat, rep, 1)

    return text


def reject_citation_permute(chosen_text, passage_ids, rng):
    """
    Permute the [DOC_ID] citations in the chosen response.
    Real doc_ids, wrong attributions.
    """
    text = chosen_text
    cites_in_text = DOC_ID_RE.findall(text)
    if len(cites_in_text) < 2 or len(passage_ids) < 2:
        return None  # can't permute; caller will skip

    # Build a permutation that is not the identity
    available_cites = [c for c in passage_ids if c != "TOOL_PAYSLIP_AUDIT"]
    if len(available_cites) < 2:
        available_cites = passage_ids
    permuted = available_cites.copy()
    for _ in range(5):
        rng.shuffle(permuted)
        if permuted != available_cites:
            break

    # Walk through text, replacing each [DOC_ID] with a different doc_id from passage_ids
    def replacer(match):
        original = match.group(1)
        # pick any doc_id from available_cites that is NOT the original
        candidates = [c for c in available_cites if c != original]
        if not candidates:
            return match.group(0)
        return f"[{rng.choice(candidates)}]"

    new_text = DOC_ID_RE.sub(replacer, text)
    return new_text if new_text != text else None


GROUNDING_PATTERNS = [
    # Pattern A: insert a fake prerequisite sentence
    lambda rng, cite: (
        f"\n\n**Important clarification [{cite}]:** This only applies if you have completed "
        f"{rng.choice(['180', '240', '365'])} continuous working days in the "
        f"{rng.choice(['last 6 months', 'past 12 months', 'last 2 years'])} at the same establishment."
    ),
    # Pattern B: fake geographic restriction
    lambda rng, cite: (
        f"\n\n**Regional note [{cite}]:** This provision applies only to workers employed in "
        f"{rng.choice(['metro cities', 'Tier-1 cities', 'state-capitals only', 'notified industrial zones'])}."
    ),
    # Pattern C: fake age threshold
    lambda rng, cite: (
        f"\n\n**Age requirement [{cite}]:** This benefit is available only to employees "
        f"{rng.choice(['above 21 years', 'between 25 and 58 years', 'under 45 years'])} of age."
    ),
    # Pattern D: fake timeline / filing window
    lambda rng, cite: (
        f"\n\n**Deadline [{cite}]:** The claim must be filed within "
        f"{rng.choice(['60 days', '90 days', '180 days'])} of the triggering event — delayed claims forfeit eligibility."
    ),
    # Pattern E: fake income threshold
    lambda rng, cite: (
        f"\n\n**Income cap [{cite}]:** This rule applies only if annual income is below "
        f"₹{rng.choice(['5 lakh', '8 lakh', '12 lakh'])} for the financial year."
    ),
    # Pattern F: fake registration requirement
    lambda rng, cite: (
        f"\n\n**Prerequisite [{cite}]:** You must be registered on the "
        f"{rng.choice(['Shram Suvidha Portal', 'e-Shram portal', 'state labour department registry'])} "
        f"for at least {rng.choice(['6 months', '1 year', '2 years'])} before this applies."
    ),
]


def reject_grounding_inject(chosen_text, passage_ids, rng):
    """
    Inject a plausible-sounding fabricated rule into the chosen response.
    """
    if not passage_ids:
        return None
    cite = rng.choice([c for c in passage_ids if c != "TOOL_PAYSLIP_AUDIT"] or passage_ids)
    pattern_fn = rng.choice(GROUNDING_PATTERNS)
    injection = pattern_fn(rng, cite)

    # Insert before the last section (usually "Next Steps" or at end)
    lines = chosen_text.split("\n")
    if len(lines) > 4:
        insert_at = max(3, len(lines) - 4)
        return "\n".join(lines[:insert_at]) + injection + "\n" + "\n".join(lines[insert_at:])
    return chosen_text + injection


# ════════════════════════════════════════════════════════════════════════════
# OUT-OF-SCOPE + KB-INSUFFICIENT PROMPTS
# ════════════════════════════════════════════════════════════════════════════

OUT_OF_SCOPE_PROMPTS = [
    "Should I sue my employer for wrongful termination? Draft the legal notice.",
    "My boss is harassing me — what criminal charges can I file under IPC?",
    "Is my employer's health insurance good? Should I buy supplementary coverage?",
    "I want to invest PF withdrawal in stocks. Which stocks should I buy?",
    "Help me plan retirement at 45 — should I quit and start a business?",
    "My colleague is doing something illegal — report to police or HR?",
    "I need visa advice — can I move to Canada on my current employment?",
    "Write a resignation email that makes my boss feel guilty.",
    "What's the best cryptocurrency to invest my bonus in?",
    "I think I have depression from work. Should I take medication?",
    "Draft a court case against the company for me.",
    "Can I legally record my boss without consent?",
    "Should I take a 14% loan to invest in mutual funds?",
    "How do I set up an LLC to route my salary and save tax?",
    "Give me medical advice on whether I qualify for ESI based on my symptoms.",
    "Write a fake sick leave application that HR will approve.",
    "My father needs pension help — what govt schemes can he use?",
    "Negotiate my salary hike — give me exact scripts.",
    "Explain GST implications for my freelance clients.",
    "What's the startup ecosystem like in my city?",
    "Should I marry my colleague? Career impact?",
    "Detailed business plan for a PF consultancy firm.",
    "How do I find the best labour law lawyer near me?",
    "Explain Hindu Succession Act for my property dispute.",
]

KB_INSUFFICIENT_PROMPTS = [
    ("My grandfather was an EPFO member who died in 1978. How do I claim his old PF?", "pf", ["FAQ_CLAIM_128", "GRIEVANCE_EPFIGMS_PROCESS"]),
    ("I was deputed abroad 12 years, returned last month. PF with dual SSAs?", "pf", ["FAQ_CLAIM_128"]),
    ("Employer went bankrupt 8 years ago, never paid final PF. Company no longer exists.", "pf", ["EMPLOYER_DEFAULT_REMEDIES"]),
    ("Worked on ship flagged in Singapore but based at Kolkata port. EPF covered?", "pf", ["FAQ_CLAIM_128"]),
    ("Company acquired 3 times in 10 years. How is my service period calculated for gratuity?", "labour", ["GRATUITY_ACT_S4_ELIG"]),
    ("I'm a priest in a registered temple trust. Do labour laws apply?", "labour", ["GRATUITY_ACT_S4_ELIG"]),
    ("I'm an Apprentices Act 1961 trainee, terminated. What are my rights?", "labour", ["WRONGFUL_TERMINATION_REMEDIES"]),
    ("Journalist — how does Working Journalists Act affect my gratuity?", "labour", ["GRATUITY_ACT_S4_ELIG"]),
    ("Shifts at metro train operator — government-private mix. Which labour law?", "labour", ["STANDING_ORDERS_ACT_NOTICE_PERIOD"]),
    ("Seafarer on Indian-flag merchant vessel. Maternity Act for wife's port stay?", "labour", ["MATERNITY_BENEFIT_ACT_2017"]),
    ("Company runs charitable trust school. EPF or trust exempt?", "pf", ["FAQ_CONTRIB_001"]),
    ("My salary is paid in cryptocurrency. How does TDS apply?", "tax", ["ITA_OLD_REGIME_SLABS"]),
    ("Returned from Dubai after 15 years. Global vs Indian income TDS this year?", "tax", ["ITA_OLD_REGIME_SLABS"]),
    ("NRI withdrawing old PF from 2005 — updated tax treatment?", "tax", ["CIRC_2024_TDS"]),
    ("Payslip has 'Welfare Fund' deduction specific to Kerala. Legal? Which act?", "payslip", ["PROF_TAX_KERALA"]),
    ("ESI shows 0.75% plus 'state ESI top-up'. Which states? Lawful?", "payslip", ["ESI_WAGE_LIMIT"]),
    ("I work at a SEZ — special PF/ESI under SEZ Act?", "payslip", ["EPF_ACT_S6_CONTRIB"]),
    ("BPO deducts 'training cost recovery' from salary. Lawful?", "payslip", ["CODE_ON_WAGES_2019_BASICS"]),
    ("Bonus linked to Balanced Scorecard scores. Legal under Bonus Act?", "payslip", ["BONUS_ACT_1965"]),
    ("PT ₹200 in work state, former employer (different state) deducted ₹150. Refund who?", "payslip", ["PROF_TAX_KARNATAKA"]),
    ("Overlapping UANs from different companies can't merge due to Aadhaar mismatch. Escalation?", "pf", ["GUIDE_UAN_MERGE"]),
    ("EPFO rejected PF transfer because previous employer 'untraceable' — but company still operates. Next?", "pf", ["EMPLOYER_DEFAULT_REMEDIES"]),
    ("Got Section 7A order from EPFO as director. Response? Personal liability?", "pf", ["EPF_ACT_S14B"]),
    ("Employer contesting gratuity at Controlling Authority. Timeline? Interim relief?", "labour", ["GRATUITY_ACT_S4_ELIG"]),
    ("Court ruled for me on wrongful termination 3 years ago. Employer still unpaid back-wages. Enforce?", "labour", ["WRONGFUL_TERMINATION_REMEDIES"]),
    ("Employer's ITR shows no TDS deposit despite deducting from my salary. Remedy?", "tax", ["ITR_REFUND_DELAY_GRIEVANCE"]),
    ("Apprentice stipend — is 12% EPF mandatory?", "pf", ["FAQ_CONTRIB_001"]),
    ("Working for Indian subsidiary of foreign company paid in foreign currency. TDS?", "tax", ["ITA_OLD_REGIME_SLABS"]),
    ("Gratuity for contract employee moved through 3 different contractors but same work site?", "labour", ["GRATUITY_ACT_S4_ELIG"]),
    ("Temporary worker on fixed-term contract renewed 5 times over 8 years. Permanent?", "labour", ["STANDING_ORDERS_ACT_NOTICE_PERIOD"]),
]

REFUSAL_TEMPLATE_OUT_OF_SCOPE = """**Result:** This is outside ShramikSaathi's scope.

ShramikSaathi helps with four specific areas:
- PF / EPFO account matters
- Payslip audit and salary deductions
- Labour rights (gratuity, termination, maternity, overtime, notice period)
- Income tax on salaried income

**For your question:**
{redirect}

**What I can help with:** Any question about your PF, payslip, labour rights, or income tax — ask and I'll give you a grounded answer with citations."""

REDIRECTS = {
    "legal":      "Please consult a qualified lawyer or legal aid service. I can't provide legal representation or draft formal legal notices.",
    "medical":    "Please consult a medical professional. I can't provide medical advice.",
    "investment": "Please consult a SEBI-registered investment advisor. I can't recommend stocks, funds, or investment strategies.",
    "visa":       "Please consult a certified immigration consultant or the relevant embassy. Visa matters are outside my scope.",
    "other":      "Please consult a qualified professional in that area. This topic is outside my scope.",
}

REFUSAL_TEMPLATE_ESCALATION = """**Result:** Your specific situation isn't fully covered by the available sources.

**General information [{cite}]:** {general_info}

**Why this needs escalation:** The specifics — {specifics} — fall outside what standard EPFO/labour/tax references cover directly. A regional office or domain authority needs to examine your documents.

**Recommended next step:** {escalation_path}

**What to include:** full documentation, any prior correspondence, account numbers, and a clear chronology."""


# ════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ════════════════════════════════════════════════════════════════════════════

VERDICT_KEYWORDS = [
    "eligible", "not eligible", "ineligible", "correct", "incorrect",
    "matches", "does not match", "mismatch", "applicable", "not applicable",
    "entitled", "conditional", "escalate", "under-deducted", "over-deducted",
    "exemption", "outside", "scope", "outside shramiksaathi",
]

REFUSAL_PHRASES = [
    "i cannot help", "i don't know", "i'm not able",
    "i am not able", "unable to help",
]


def validate_chosen(text, passage_ids, dimension):
    words = text.split()
    if len(words) < 40:
        return False, "chosen too short"
    if len(words) > 550:
        return False, "chosen too long"

    if dimension == "refusal_and_escalation":
        rl = text.lower()
        signals = ["outside", "scope", "consult", "escalate", "grievance",
                   "regional office", "specific situation", "professional"]
        if not any(s in rl for s in signals):
            return False, "chosen missing refusal/escalation signal"
        return True, "ok"

    rl = text.lower()
    for phrase in REFUSAL_PHRASES:
        if phrase in rl:
            return False, f"chosen accidental refusal: {phrase}"

    cited = set(DOC_ID_RE.findall(text))
    if not cited:
        return False, "chosen no citations"

    fabricated = cited - set(passage_ids)
    if fabricated:
        return False, f"chosen fabricated cites: {sorted(fabricated)[:2]}"

    if not any(k in rl for k in VERDICT_KEYWORDS):
        return False, "chosen no verdict keyword"
    return True, "ok"


def validate_rejected(text, chosen_text, passage_ids, dimension):
    words = text.split()
    if len(words) < 40:
        return False, "rejected too short"
    if len(words) > 600:
        return False, "rejected too long"

    if text.strip() == chosen_text.strip():
        return False, "rejected identical to chosen"

    # Rejected must have citations (otherwise trivial)
    cited = set(DOC_ID_RE.findall(text))
    if not cited:
        return False, "rejected no citations"

    # Dimension-specific sanity checks
    if dimension == "verdict_correctness":
        cl = chosen_text.lower()
        rl = text.lower()
        chosen_has_eligible = ("eligible" in cl) and ("not eligible" not in cl) and ("ineligible" not in cl)
        rejected_has_eligible = ("eligible" in rl) and ("not eligible" not in rl) and ("ineligible" not in rl)
        chosen_has_correct = ("is correct" in cl) or ("matches" in cl and "does not match" not in cl)
        rejected_has_correct = ("is correct" in rl) or ("matches" in rl and "does not match" not in rl)
        # At least one verdict axis must differ
        if chosen_has_eligible == rejected_has_eligible and chosen_has_correct == rejected_has_correct:
            return False, "rejected verdict matches chosen"

    return True, "ok"


# ════════════════════════════════════════════════════════════════════════════
# LLM TEACHER (only for refusal dimension)
# ════════════════════════════════════════════════════════════════════════════

def load_teacher():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    print(f"Loading {MODEL_ID}")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, torch_dtype=torch.bfloat16,
        device_map="auto", attn_implementation="sdpa",
    )
    model.eval()
    device = next(model.parameters()).device
    print(f"Loaded in {time.time()-t0:.1f}s on {device}")
    return model, tokenizer, device


def generate_batch(model, tokenizer, device, chat_texts):
    import torch
    inputs = tokenizer(chat_texts, return_tensors="pt", padding=True,
                       truncation=True, max_length=3072).to(device)
    with torch.no_grad():
        out = model.generate(
            **inputs, max_new_tokens=MAX_NEW_TOKENS,
            do_sample=True, temperature=TEMPERATURE, top_p=TOP_P,
            pad_token_id=tokenizer.eos_token_id,
        )
    responses = []
    for i in range(len(chat_texts)):
        input_len = inputs['input_ids'][i].shape[0]
        gen = out[i][input_len:]
        responses.append(tokenizer.decode(gen, skip_special_tokens=True).strip())
    return responses


# ════════════════════════════════════════════════════════════════════════════
# INCREMENTAL
# ════════════════════════════════════════════════════════════════════════════

def load_incremental():
    if not INCREMENTAL_PATH.exists():
        return []
    rows = []
    with open(INCREMENTAL_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def append_incremental(record):
    INCREMENTAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INCREMENTAL_PATH, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ════════════════════════════════════════════════════════════════════════════
# GENERATION LOOPS
# ════════════════════════════════════════════════════════════════════════════

def generate_contrastive_template(
    domain, target, intents, kb_by_id, kb_by_subdomain,
    sft_responses, log_f, existing_dim_counts,
):
    """Dimensions 1-3: fully template-based, no LLM."""
    rng = random.Random(hash(domain) & 0xffffffff)
    dim_rotation = ["grounding", "verdict_correctness", "citation_discipline"]

    count = 0
    attempts = 0
    t0 = time.time()
    max_attempts = target * 4

    while count < target and attempts < max_attempts:
        attempts += 1

        available = [i for i in intents if i in INTENT_CONFIGS]
        if not available:
            break
        intent = rng.choice(available)
        cfg = INTENT_CONFIGS[intent]

        passages = select_passages(kb_by_id, kb_by_subdomain, cfg, rng)
        if not passages:
            continue
        slots = sample_slots(intent, cfg, rng)
        if cfg.get("use_payslip_tool"):
            passages = add_payslip_tool(passages, slots)
        query = build_query(cfg, slots, rng)
        if query is None:
            continue

        passage_ids = [p["doc_id"] for p in passages]

        # Dimension balancing
        dim_order = sorted(dim_rotation, key=lambda d: existing_dim_counts.get(d, 0))
        dimension = dim_order[0]
        if existing_dim_counts.get(dimension, 0) >= DIMENSION_TARGETS[dimension]:
            # This dim is full — pick another
            remaining = [d for d in dim_rotation if existing_dim_counts.get(d, 0) < DIMENSION_TARGETS[d]]
            if not remaining:
                break
            dimension = rng.choice(remaining)

        # Chosen
        chosen, chosen_source = synthesize_chosen(intent, slots, passages, sft_responses)
        ok_c, why_c = validate_chosen(chosen, passage_ids, dimension)
        if not ok_c:
            log_f.write(f"[reject-chosen] {domain}/{dimension}/{intent}: {why_c}\n")
            log_f.flush()
            continue

        # Rejected — deterministic per dimension
        if dimension == "verdict_correctness":
            rejected = reject_verdict_flip(chosen, slots, rng)
        elif dimension == "citation_discipline":
            rejected = reject_citation_permute(chosen, passage_ids, rng)
            if rejected is None:
                continue
        elif dimension == "grounding":
            rejected = reject_grounding_inject(chosen, passage_ids, rng)
            if rejected is None:
                continue
        else:
            continue

        ok_r, why_r = validate_rejected(rejected, chosen, passage_ids, dimension)
        if not ok_r:
            log_f.write(f"[reject-rejected] {domain}/{dimension}/{intent}: {why_r}\n")
            log_f.flush()
            continue

        user_prompt = build_generator_input(query, cfg["domain"], passages, slots)
        record = {
            "prompt":       user_prompt[:1500],
            "full_prompt":  user_prompt,
            "chosen":       chosen,
            "rejected":     rejected,
            "metadata": {
                "domain":        cfg["domain"],
                "intent":        intent,
                "dimension":     dimension,
                "chosen_source": chosen_source,
                "passage_ids":   passage_ids,
                "slots":         {k: v for k, v in slots.items() if v is not None},
            },
        }
        append_incremental(record)
        count += 1
        existing_dim_counts[dimension] = existing_dim_counts.get(dimension, 0) + 1

        if count % 10 == 0:
            elapsed = time.time() - t0
            print(f"  [{domain}] {count}/{target} | attempts={attempts} pass={count/max(attempts,1)*100:.0f}% [{elapsed:.1f}s]")

    elapsed = (time.time() - t0)
    print(f"[{domain}] Done: {count} pairs ({attempts} attempts, {count/max(attempts,1)*100:.0f}% pass, {elapsed:.1f}s)")
    return count


def generate_refusal_pairs(model, tokenizer, device, kb_by_id, log_f, existing_dim_counts):
    """Dimension 4: chosen=template refusal/escalation, rejected=teacher natural hallucination."""
    rng = random.Random(999)
    target = DIMENSION_TARGETS["refusal_and_escalation"]
    already = existing_dim_counts.get("refusal_and_escalation", 0)
    if already >= target:
        return already

    oos_target = REFUSAL_SUB_SPLIT["out_of_scope"]
    kbi_target = REFUSAL_SUB_SPLIT["kb_insufficient"]

    count = already
    attempts = 0
    oos_done = 0
    kbi_done = 0
    t0 = time.time()

    shuffled_oos = OUT_OF_SCOPE_PROMPTS.copy()
    rng.shuffle(shuffled_oos)
    shuffled_kbi = KB_INSUFFICIENT_PROMPTS.copy()
    rng.shuffle(shuffled_kbi)
    oos_idx = 0
    kbi_idx = 0

    while count < (already + target) and attempts < target * 5:
        batch_prompts = []
        batch_meta = []

        for _ in range(BATCH_SIZE):
            if count + len(batch_prompts) >= already + target:
                break

            need_oos = oos_done < oos_target
            need_kbi = kbi_done < kbi_target
            if need_oos and need_kbi:
                sub_type = "out_of_scope" if rng.random() < (oos_target / (oos_target + kbi_target)) else "kb_insufficient"
            elif need_oos:
                sub_type = "out_of_scope"
            elif need_kbi:
                sub_type = "kb_insufficient"
            else:
                break

            if sub_type == "out_of_scope":
                query = shuffled_oos[oos_idx % len(shuffled_oos)]
                oos_idx += 1
                ql = query.lower()
                if any(w in ql for w in ["lawyer", "sue", "legal", "court", "criminal", "ipc"]):
                    cat = "legal"
                elif any(w in ql for w in ["medical", "depression", "medication", "symptoms"]):
                    cat = "medical"
                elif any(w in ql for w in ["invest", "crypto", "stock", "mutual fund", "loan"]):
                    cat = "investment"
                elif any(w in ql for w in ["visa", "move to", "immigration"]):
                    cat = "visa"
                else:
                    cat = "other"
                chosen = REFUSAL_TEMPLATE_OUT_OF_SCOPE.format(redirect=REDIRECTS[cat])
                passages = []
                passage_ids = []
                user_msg = (
                    f"USER QUERY:\n{query}\n\n"
                    f"DOMAIN: unknown\n\n"
                    f"RETRIEVED PASSAGES:\n(no relevant passages found)\n\n"
                    f"SLOTS FILLED: {{}}\n\n"
                    f"Produce the final answer now."
                )
            else:
                query, domain, wanted = shuffled_kbi[kbi_idx % len(shuffled_kbi)]
                kbi_idx += 1
                passages = [kb_by_id[pid] for pid in wanted if pid in kb_by_id]
                if not passages:
                    attempts += 1
                    continue
                passage_ids = [p["doc_id"] for p in passages]
                primary = passage_ids[0]
                specifics = query[:100] + "..."
                if domain in ("pf", "labour"):
                    escalation = (
                        "1. File detailed grievance on EPFiGMS (epfigms.gov.in) with documents.\n"
                        "2. If unresolved, escalate to jurisdictional Regional PF Commissioner.\n"
                        "3. For labour disputes, approach state Labour Commissioner."
                    )
                else:
                    escalation = (
                        "1. Raise grievance on Income Tax e-filing portal (e-Nivaran).\n"
                        "2. If unresolved, escalate to jurisdictional Assessing Officer."
                    )
                chosen = REFUSAL_TEMPLATE_ESCALATION.format(
                    cite=primary,
                    general_info="Some general provisions may apply, but the specifics require individual assessment.",
                    specifics=specifics,
                    escalation_path=escalation,
                )
                user_msg = build_generator_input(query, domain, passages, {})

            # Rejected: ask the teacher the question NORMALLY (no contrastive framing)
            # It will naturally hallucinate a confident answer
            messages = [
                {"role": "system", "content": GENERATOR_PROMPT},
                {"role": "user", "content": user_msg},
            ]
            chat = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            batch_prompts.append(chat)
            batch_meta.append({
                "dimension":   "refusal_and_escalation",
                "sub_type":    sub_type,
                "domain":      domain if sub_type == "kb_insufficient" else "unknown",
                "query":       query,
                "user_prompt": user_msg,
                "chosen":      chosen,
                "passage_ids": passage_ids,
            })
            if sub_type == "out_of_scope":
                oos_done += 1
            else:
                kbi_done += 1

        if not batch_prompts:
            break
        attempts += len(batch_prompts)

        try:
            rejected_texts = generate_batch(model, tokenizer, device, batch_prompts)
        except Exception as e:
            log_f.write(f"[batch-error] refusal: {str(e)[:200]}\n")
            log_f.flush()
            continue

        for meta, rejected in zip(batch_meta, rejected_texts):
            ok_c, why_c = validate_chosen(meta["chosen"], meta["passage_ids"],
                                          meta["dimension"])
            if not ok_c:
                log_f.write(f"[reject-chosen] refusal/{meta['sub_type']}: {why_c}\n")
                log_f.flush()
                continue
            ok_r, why_r = validate_rejected(rejected, meta["chosen"],
                                            meta["passage_ids"], meta["dimension"])
            if not ok_r:
                log_f.write(f"[reject-rejected] refusal/{meta['sub_type']}: {why_r}\n")
                log_f.flush()
                continue

            record = {
                "prompt":       meta["user_prompt"][:1500],
                "full_prompt":  meta["user_prompt"],
                "chosen":       meta["chosen"],
                "rejected":     rejected,
                "metadata": {
                    "domain":        meta["domain"],
                    "intent":        meta["sub_type"],
                    "dimension":     meta["dimension"],
                    "chosen_source": "template",
                    "passage_ids":   meta["passage_ids"],
                    "sub_type":      meta["sub_type"],
                },
            }
            append_incremental(record)
            count += 1
            existing_dim_counts["refusal_and_escalation"] = existing_dim_counts.get("refusal_and_escalation", 0) + 1
            if count % 5 == 0:
                elapsed = (time.time() - t0) / 60
                print(f"  [refusal] {count - already}/{target} | oos={oos_done} kbi={kbi_done} pass={(count-already)/max(attempts,1)*100:.0f}% [{elapsed:.1f}min]")

    elapsed = (time.time() - t0) / 60
    print(f"[refusal] Done: {count - already} pairs ({elapsed:.1f}min)")
    return count


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("ShramikSaathi — Stage 2.1: DPO Dataset Generator (hybrid)")
    print("=" * 70)

    kb_by_id, kb_by_subdomain = load_kb()
    sft_responses = load_sft_responses()

    existing = load_incremental()
    existing_dim_counts = Counter(r["metadata"]["dimension"] for r in existing)
    print(f"\n[Resume] {len(existing)} existing pairs | dims: {dict(existing_dim_counts)}")

    intents_by_domain = defaultdict(list)
    for intent, cfg in INTENT_CONFIGS.items():
        intents_by_domain[cfg["domain"]].append(intent)

    log_f = open(LOG_PATH, "a")
    log_f.write(f"\n--- Run {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")

    try:
        # Dimensions 1-3 per domain (template only — no LLM)
        print(f"\n{'=' * 70}")
        print("PHASE 1: Template-based contrastive pairs (dims 1-3)")
        print(f"{'=' * 70}")
        for domain, target in DOMAIN_TARGETS.items():
            print(f"\n[{domain}] target {target}")
            generate_contrastive_template(
                domain, target, intents_by_domain[domain],
                kb_by_id, kb_by_subdomain, sft_responses,
                log_f, existing_dim_counts,
            )

        # Dimension 4 (LLM)
        print(f"\n{'=' * 70}")
        print(f"PHASE 2: LLM refusal pairs (dim 4, target {DIMENSION_TARGETS['refusal_and_escalation']})")
        print(f"{'=' * 70}")
        model, tokenizer, device = load_teacher()
        generate_refusal_pairs(model, tokenizer, device, kb_by_id, log_f, existing_dim_counts)
    finally:
        log_f.close()

    # Final consolidation
    all_pairs = load_incremental()
    print(f"\n{'=' * 70}")
    print(f"FINAL: {len(all_pairs)} pairs")
    print(f"{'=' * 70}")

    with open(OUTPUT_PATH, "w") as f:
        for p in all_pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    stats = {
        "total":     len(all_pairs),
        "by_domain": dict(Counter(r["metadata"]["domain"] for r in all_pairs)),
        "by_dim":    dict(Counter(r["metadata"]["dimension"] for r in all_pairs)),
        "by_intent": dict(Counter(r["metadata"]["intent"] for r in all_pairs)),
        "by_chosen_source": dict(Counter(r["metadata"]["chosen_source"] for r in all_pairs)),
    }
    with open(STATS_PATH, "w") as f:
        json.dump(stats, f, indent=2)

    print(f"\n[Save] {OUTPUT_PATH}")
    print(f"[Save] {STATS_PATH}")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Incremental saves preserved. Re-run to resume.")
    except Exception as e:
        print(f"\n[FATAL] {type(e).__name__}: {e}")
        traceback.print_exc()