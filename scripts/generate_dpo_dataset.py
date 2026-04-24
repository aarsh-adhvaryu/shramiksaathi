
"""
ShramikSaathi — Stage 2.1: DPO Dataset Generator

Generates 400 validated (chosen, rejected) preference pairs targeting four
specific failure modes observed in the Stage 1.3 held-out eval.

SCOPE (what this trains):
    - Dimension 1: grounding            — do not invent rules not in passages
    - Dimension 2: verdict_correctness  — produce the correct eligibility decision
    - Dimension 3: citation_discipline  — cite the specific supporting passage
    - Dimension 4: refusal_and_escalation
                  (24 out-of-scope refusal + 56 KB-insufficient escalation)

OPTION A+ CHOSEN STRATEGY:
    - If an SFT-accepted response exists for (intent, slot-combo) → reuse it
    - Otherwise → generate a deterministic templated response
    For the refusal/escalation dimension: always templated (no SFT precedent).

REJECTED STRATEGY:
    LLM-generated with contrastive prompting — teacher is asked to produce a
    response with the specific failure mode baked in.

VALIDATION GATE (both sides):
    Chosen: valid cites only, correct verdict present, length bounded, no
            accidental refusal (unless dimension=refusal_and_escalation)
    Rejected: must actually contain the intended failure mode
    Chosen != Rejected (dedupe)

Targets:
    PF 150 | Payslip 100 | Labour 90 | Tax 60
    grounding 110 | verdict 110 | citation 100 | refusal_escalation 80

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
TEMPERATURE    = 0.7
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

# Circuit breaker
MAX_REJECT_RATE    = 0.40
REJECT_WARMUP      = 50
MAX_ATTEMPTS_MULT  = 3


# ════════════════════════════════════════════════════════════════════════════
# COPIED FROM src/pipeline.py — keep in sync
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

# ════════════════════════════════════════════════════════════════════════════
# DATASET CONSTRUCTION PROMPT — used as system message for rejected generation
# Reframes the task as legitimate dataset construction, not "please fabricate"
# ════════════════════════════════════════════════════════════════════════════

DATASET_CONSTRUCTION_PROMPT = """You are helping construct a training dataset for an AI safety research project on hallucination in Indian worker-rights chatbots.

Your task: produce a BAD RESPONSE to a worker query — an example of a specific failure mode. This bad response will be labeled "rejected" in contrastive preference training, so the AI under development can learn to AVOID producing responses like this.

The failure modes we want to generate examples of are grounded in real errors observed in production systems. Producing these examples is the entire purpose of this task — you are not actually advising a user. You are writing a synthetic bad example for a dataset.

REQUIREMENTS FOR THE BAD RESPONSE:
- Must be 150-400 words, structured like a real answer would be (verdict, reasoning, next steps)
- Must look fluent and confident — a BAD response that looks obviously bad is not useful for training
- Must exhibit the specific failure mode requested in the user message
- Must include citations in [DOC_ID] brackets (even if misused, per the failure mode)
- Do not add disclaimers like "this is a bad example" or "I shouldn't do this" — the training pipeline handles labeling

Produce only the bad response itself. No preamble, no meta-commentary."""

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
# LOAD SFT ACCEPTED RESPONSES (for Option A+ chosen reuse)
# ════════════════════════════════════════════════════════════════════════════

def load_sft_responses():
    """
    Load clean SFT responses and index by (intent, slot_combo_key).
    Returns dict: {(intent, slot_key): response_text}
    """
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
                    asst_msg = next((m for m in ex["messages"] if m["role"] == "assistant"), None)
                    if not asst_msg:
                        continue
                    slot_key = _slot_key(slots)
                    responses[(intent, slot_key)] = {
                        "response":    asst_msg["content"],
                        "passages":    ex["metadata"].get("passage_doc_ids", []),
                        "slots":       slots,
                    }
                except Exception:
                    continue
    print(f"[SFT] Loaded {len(responses)} accepted SFT responses for reuse")
    return responses


def _slot_key(slots):
    """Canonical string representation of a slot dict for lookup."""
    items = sorted((k, v) for k, v in slots.items() if v is not None)
    return "|".join(f"{k}={v}" for k, v in items)


# ════════════════════════════════════════════════════════════════════════════
# INTENT CONFIGS — subset adapted from SFT for DPO
# (Only intents we can meaningfully contrast on)
# ════════════════════════════════════════════════════════════════════════════

INTENT_CONFIGS = {
    "full_withdrawal": {
        "domain": "pf", "subdomains": ["withdrawal"], "cross_doc_ids": ["CIRC_2024_TDS"],
        "templates": [
            "Resigned {months_unemployed} months ago after {service_years} years of service. UAN {uan_status}, KYC {kyc_status}. Can I withdraw full PF?",
            "Left my job {months_unemployed} months back, total {service_years} years service. UAN is {uan_status}, KYC is {kyc_status}. Full PF withdrawal karna hai.",
        ],
        "slot_ranges": {
            "employment_status": ["unemployed"],
            "months_unemployed": [1, 2, 3, 4, 6, 8],
            "service_years":     [2, 3, 4, 5, 6, 8, 10],
            "uan_status":        ["active"],
            "kyc_status":        ["complete", "partial"],
        },
        "correct_verdict_map": {
            ("unemployed", 2,  3, "active", "complete"): ("eligible", "withdrawal allowed, TDS applies because service < 5 years"),
            ("unemployed", 3,  6, "active", "complete"): ("eligible", "withdrawal allowed, no TDS because service >= 5 years"),
            ("unemployed", 1,  4, "active", "complete"): ("not_eligible", "unemployment period less than 2 months required"),
        },
    },
    "tds_query": {
        "domain": "pf", "subdomains": ["taxation", "withdrawal"], "cross_doc_ids": ["CIRC_2024_TDS"],
        "templates": [
            "Withdrew PF ₹{pf_withdrawal_amount} after {service_years} years. Will TDS apply?",
            "PF nikala ₹{pf_withdrawal_amount}, service {service_years} years. TDS kitna katega?",
        ],
        "slot_ranges": {
            "pf_withdrawal_amount": [30000, 55000, 80000, 150000],
            "service_years":        [2, 3, 4, 5, 6],
        },
        "correct_verdict_map": {},  # verdict = conditional for most of these
    },
    "transfer": {
        "domain": "pf", "subdomains": ["transfer"], "cross_doc_ids": [],
        "templates": [
            "Changed jobs, need to transfer PF. UAN {uan_status}, KYC {kyc_status}.",
        ],
        "slot_ranges": {
            "uan_status": ["active", "inactive"],
            "kyc_status": ["complete", "partial", "incomplete"],
        },
        "correct_verdict_map": {},
    },
    "kyc_issue": {
        "domain": "pf", "subdomains": ["kyc", "uan"], "cross_doc_ids": [],
        "templates": [
            "My KYC is {kyc_status} on EPFO portal. What to do?",
        ],
        "slot_ranges": {
            "kyc_status": ["rejected", "incomplete", "partial"],
        },
        "correct_verdict_map": {},
    },
    "verify_epf": {
        "domain": "payslip", "subdomains": ["epf_deduction"], "cross_doc_ids": [],
        "templates": [
            "Basic salary ₹{basic_salary}, EPF deducted ₹{epf_deducted}. Is this correct?",
        ],
        "slot_ranges": {
            "basic_salary":  [12000, 15000, 18000, 20000, 25000, 30000],
            "epf_deducted":  None,
            "gross_salary":  None,
        },
        "use_payslip_tool": True,
        "correct_verdict_map": {},
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
        "correct_verdict_map": {},
    },
    "check_minimum_wage": {
        "domain": "payslip", "subdomains": ["minimum_wage"], "cross_doc_ids": [],
        "templates": [
            "Unskilled worker in {state}, gross ₹{gross_salary}/month. Minimum wage mil raha?",
        ],
        "slot_ranges": {
            "state":        ["Maharashtra", "Karnataka", "Gujarat", "Tamil Nadu", "Delhi"],
            "gross_salary": [8000, 10000, 12000, 14000, 16000],
        },
        "correct_verdict_map": {},
    },
    "gratuity": {
        "domain": "labour", "subdomains": ["gratuity"], "cross_doc_ids": [],
        "templates": [
            "Worked {employment_years} years at {employer_type} company. {termination_reason}. Last salary ₹{last_drawn_salary}. Gratuity milega?",
        ],
        "slot_ranges": {
            "employment_years":   [3, 4, 5, 6, 7, 10],
            "termination_reason": ["resignation", "retirement", "employer_terminated"],
            "employer_type":      ["private", "factory"],
            "last_drawn_salary":  [25000, 35000, 45000, 60000],
        },
        "correct_verdict_map": {},
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
        "correct_verdict_map": {},
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
        "correct_verdict_map": {},
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
        "correct_verdict_map": {},
    },
    "hra_exemption": {
        "domain": "tax", "subdomains": ["hra"], "cross_doc_ids": [],
        "templates": [
            "Income ₹{annual_income}, {tax_regime}, paying ₹{rent_paid} rent in {city_type} city. HRA exemption?",
        ],
        "slot_ranges": {
            "annual_income": [600000, 900000, 1200000, 1800000],
            "tax_regime":    ["old_regime"],
            "rent_paid":     [12000, 18000, 25000, 35000],
            "city_type":     ["metro", "non_metro"],
        },
        "correct_verdict_map": {},
    },
    "deductions_80c": {
        "domain": "tax", "subdomains": ["deductions"], "cross_doc_ids": [],
        "templates": [
            "Income ₹{annual_income}, {tax_regime}, invested ₹{section_80c_investments} in 80C instruments.",
        ],
        "slot_ranges": {
            "annual_income":           [700000, 1000000, 1500000],
            "tax_regime":              ["old_regime", "new_regime"],
            "section_80c_investments": [50000, 100000, 150000],
        },
        "correct_verdict_map": {},
    },
}

REASONING_INTENTS = {
    "full_withdrawal", "tds_query", "verify_epf", "verify_esi",
    "check_minimum_wage", "gratuity", "wrongful_termination",
    "maternity_benefit", "hra_exemption", "deductions_80c",
}


# ════════════════════════════════════════════════════════════════════════════
# SLOT SAMPLING + PASSAGE SELECTION
# (Adapted from SFT generator)
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
# CHOSEN RESPONSE SYNTHESIS (Option A+)
# ════════════════════════════════════════════════════════════════════════════

def synthesize_chosen(intent, slots, passages, sft_responses):
    """Try SFT reuse first, fall back to template."""
    slot_key = _slot_key(slots)
    sft_match = sft_responses.get((intent, slot_key))
    if sft_match:
        return sft_match["response"], "sft_reuse"
    return synthesize_template_chosen(intent, slots, passages), "template"


def synthesize_template_chosen(intent, slots, passages):
    """Deterministic templated chosen response for each intent."""
    passage_ids = [p["doc_id"] for p in passages]
    primary = passage_ids[0] if passage_ids else "UNKNOWN"
    has_tds = "CIRC_2024_TDS" in passage_ids

    if intent == "full_withdrawal":
        mo = slots.get("months_unemployed", 0)
        yr = slots.get("service_years", 0)
        if mo < 2:
            return (
                f"**Result:** Not eligible for full PF withdrawal yet.\n\n"
                f"**Reason:** Unemployment period of {mo} month(s) is below the 2-month minimum required [{primary}].\n\n"
                f"**Next Steps:**\n"
                f"1. Wait until you complete 2 months of continuous unemployment.\n"
                f"2. Ensure UAN stays active and KYC remains complete during this period.\n"
                f"3. After 2 months, submit Form 19 through the EPFO Unified Member Portal [{primary}]."
            )
        if yr >= 5:
            return (
                f"**Result:** Eligible for full PF withdrawal.\n\n"
                f"**Reasoning:**\n"
                f"- Unemployment of {mo} months exceeds the 2-month threshold [{primary}]\n"
                f"- Service of {yr} years exceeds the 5-year TDS threshold, so no TDS applies"
                + (f" [CIRC_2024_TDS]" if has_tds else "") + "\n\n"
                f"**Next Steps:**\n"
                f"1. Login to unifiedportal-mem.epfindia.gov.in\n"
                f"2. Go to Online Services → Claim Form 19\n"
                f"3. Verify bank account matches KYC record\n"
                f"4. Submit. Processing time approximately 20 working days [{primary}]."
            )
        return (
            f"**Result:** Eligible for full PF withdrawal with TDS applicable.\n\n"
            f"**Reasoning:**\n"
            f"- Unemployment of {mo} months meets the 2-month requirement [{primary}]\n"
            f"- Service of {yr} years is below the 5-year TDS threshold"
            + (f" [CIRC_2024_TDS]" if has_tds else "") + "\n\n"
            f"**TDS Warning:** TDS will be deducted at 10% if your withdrawal amount exceeds ₹50,000 and your PAN is linked"
            + (f" [CIRC_2024_TDS]" if has_tds else "") + ".\n\n"
            f"**Next Steps:**\n"
            f"1. Submit Form 19 via EPFO Unified Member Portal.\n"
            f"2. Submit Form 15G if your total taxable income is below the threshold to avoid TDS"
            + (f" [CIRC_2024_TDS]" if has_tds else "") + "."
        )

    if intent == "tds_query":
        amt = slots.get("pf_withdrawal_amount", 0)
        yr  = slots.get("service_years", 0)
        if yr >= 5:
            return (
                f"**Result:** No TDS applies on your PF withdrawal.\n\n"
                f"**Reason:** Your service period of {yr} years exceeds the 5-year threshold [{primary}].\n\n"
                f"**Next Steps:**\n"
                f"1. Withdraw the full amount via Form 19.\n"
                f"2. No Form 15G required."
            )
        if amt <= 50000:
            return (
                f"**Result:** No TDS applies despite service being under 5 years.\n\n"
                f"**Reason:** Withdrawal amount of ₹{amt:,} is below the ₹50,000 threshold [{primary}].\n\n"
                f"**Next Steps:**\n"
                f"1. Proceed with withdrawal via Form 19.\n"
                f"2. No TDS will be deducted."
            )
        return (
            f"**Result:** TDS at 10% will apply on your PF withdrawal.\n\n"
            f"**Reasoning:**\n"
            f"- Service of {yr} years is below the 5-year threshold [{primary}]\n"
            f"- Withdrawal amount of ₹{amt:,} exceeds the ₹50,000 threshold [{primary}]\n\n"
            f"**How to reduce or avoid TDS:**\n"
            f"1. Submit Form 15G with your withdrawal if your total annual income is below the taxable limit.\n"
            f"2. Ensure PAN is linked to your UAN — otherwise TDS rate jumps to 30%."
        )

    if intent == "transfer":
        return (
            f"**Result:** PF transfer is available through Form 13.\n\n"
            f"**Process [{primary}]:**\n"
            f"1. Login to the EPFO Unified Member Portal.\n"
            f"2. Go to Online Services → One Member One EPF Account (Transfer Request).\n"
            f"3. Choose the previous employer, fill Form 13 online.\n"
            f"4. Get attestation from current or previous employer.\n"
            f"5. Submit. Processing takes approximately 20 working days.\n\n"
            f"**Note:** With UAN-Aadhaar seeding, many transfers happen automatically on job change."
        )

    if intent == "kyc_issue":
        return (
            f"**Result:** KYC issues are resolved through the EPFO Unified Member Portal.\n\n"
            f"**Process [{primary}]:**\n"
            f"1. Login to unifiedportal-mem.epfindia.gov.in using your UAN.\n"
            f"2. Go to Manage → KYC.\n"
            f"3. Update the document (Aadhaar, PAN, or bank account) that shows the mismatch.\n"
            f"4. Submit and wait for employer/digital approval.\n\n"
            f"**Common fix for Aadhaar name mismatch:** Correct your Aadhaar name via UIDAI portal first, then re-seed in UAN."
        )

    if intent == "verify_epf":
        basic    = slots.get("basic_salary", 0)
        actual   = slots.get("epf_deducted", 0)
        expected = round(basic * 0.12)
        tool_cite = "TOOL_PAYSLIP_AUDIT" if "TOOL_PAYSLIP_AUDIT" in passage_ids else primary
        if abs(expected - actual) <= 1:
            return (
                f"**Result:** EPF deduction of ₹{actual:,} is correct.\n\n"
                f"**Calculation [{tool_cite}]:**\n"
                f"- Basic salary: ₹{basic:,}\n"
                f"- EPF rate: 12% [{primary}]\n"
                f"- Expected: ₹{expected:,}\n"
                f"- Actual: ₹{actual:,}\n"
                f"- **Match** ✓"
            )
        return (
            f"**Result:** EPF deduction is incorrect.\n\n"
            f"**Calculation [{tool_cite}]:**\n"
            f"- Basic salary: ₹{basic:,}\n"
            f"- EPF rate: 12% [{primary}]\n"
            f"- Expected: ₹{expected:,}\n"
            f"- Actual: ₹{actual:,}\n"
            f"- **Difference: ₹{actual - expected:,}**\n\n"
            f"**Next Steps:**\n"
            f"1. Raise this with your HR/payroll team.\n"
            f"2. If unresolved, file a grievance on EPFiGMS with your payslip as proof."
        )

    if intent == "verify_esi":
        gross    = slots.get("gross_salary", 0)
        actual   = slots.get("esi_deducted", 0)
        tool_cite = "TOOL_PAYSLIP_AUDIT" if "TOOL_PAYSLIP_AUDIT" in passage_ids else primary
        if gross > 21000:
            if actual == 0:
                return (
                    f"**Result:** ESI is correctly not deducted.\n\n"
                    f"**Reason [{primary}]:** Gross salary of ₹{gross:,} exceeds the ₹21,000 ESI threshold, so ESI is not applicable.\n\n"
                    f"**Calculation [{tool_cite}]:**\n"
                    f"- Gross: ₹{gross:,}\n"
                    f"- Threshold: ₹21,000\n"
                    f"- ESI applicable: No"
                )
            return (
                f"**Result:** ESI should not be deducted.\n\n"
                f"**Reason [{primary}]:** Gross salary of ₹{gross:,} exceeds ₹21,000 threshold. ESI is not applicable above this.\n\n"
                f"**Action:** Ask employer to refund the ₹{actual} being wrongly deducted [{tool_cite}]."
            )
        expected = round(gross * 0.0075)
        if abs(expected - actual) <= 1:
            return (
                f"**Result:** ESI deduction of ₹{actual:,} is correct.\n\n"
                f"**Calculation [{tool_cite}]:**\n"
                f"- Gross: ₹{gross:,}\n"
                f"- Employee rate: 0.75% [{primary}]\n"
                f"- Expected: ₹{expected:,}\n"
                f"- Actual: ₹{actual:,}\n"
                f"- **Match** ✓"
            )
        return (
            f"**Result:** ESI deduction is incorrect.\n\n"
            f"**Calculation [{tool_cite}]:**\n"
            f"- Gross: ₹{gross:,}\n"
            f"- Expected (0.75%): ₹{expected:,}\n"
            f"- Actual: ₹{actual:,}\n"
            f"- **Difference: ₹{actual - expected:,}**"
        )

    if intent == "check_minimum_wage":
        gross = slots.get("gross_salary", 0)
        state = slots.get("state", "your state")
        return (
            f"**Result:** Requires verification against {state} minimum wage schedule [{primary}].\n\n"
            f"**Your salary:** ₹{gross:,}/month.\n\n"
            f"**Action:**\n"
            f"1. Compare ₹{gross:,} against the current unskilled minimum wage notified by {state} labour department [{primary}].\n"
            f"2. If below minimum wage, you can raise a complaint with the state labour commissioner.\n"
            f"3. Underpayment of minimum wage is a criminal offence under the Minimum Wages Act."
        )

    if intent == "gratuity":
        yr     = slots.get("employment_years", 0)
        reason = slots.get("termination_reason", "")
        salary = slots.get("last_drawn_salary", 0)
        if yr < 5:
            return (
                f"**Result:** Not eligible for gratuity.\n\n"
                f"**Reason [{primary}]:** The Payment of Gratuity Act requires 5 years of continuous service. "
                f"You have completed only {yr} years.\n\n"
                f"**Note:** Some courts have held that 240 days in the 5th year may qualify — consult your state labour office if you believe this applies."
            )
        amount = int(salary * 15 * yr / 26)
        return (
            f"**Result:** Eligible for gratuity.\n\n"
            f"**Reasoning [{primary}]:**\n"
            f"- Continuous service of {yr} years meets the 5-year minimum\n"
            f"- {reason.replace('_', ' ').title()} is a qualifying termination reason\n\n"
            f"**Calculation:**\n"
            f"Gratuity = (Last salary × 15 × years) / 26\n"
            f"        = (₹{salary:,} × 15 × {yr}) / 26\n"
            f"        = ₹{amount:,}\n\n"
            f"**Next Steps:**\n"
            f"1. Submit Form I to employer within 30 days.\n"
            f"2. Employer must pay within 30 days.\n"
            f"3. If unpaid, file with Controlling Authority under the Act."
        )

    if intent == "wrongful_termination":
        yr = slots.get("employment_years", 0)
        return (
            f"**Result:** You have legal remedies for wrongful termination.\n\n"
            f"**Options [{primary}]:**\n"
            f"1. Send a legal notice demanding reinstatement or compensation.\n"
            f"2. File a complaint with the Labour Commissioner.\n"
            f"3. Approach the Labour Court or Industrial Tribunal under the Industrial Disputes Act.\n\n"
            f"**Note:** {yr} years of service strengthens your case for retrenchment compensation if applicable."
        )

    if intent == "maternity_benefit":
        offered = slots.get("notice_period_days", 0)
        return (
            f"**Result:** Your entitlement is 26 weeks, not {offered} days.\n\n"
            f"**Legal Position [{primary}]:** The Maternity Benefit (Amendment) Act 2017 entitles every eligible woman employee "
            f"to 26 weeks of paid maternity leave for the first and second child.\n\n"
            f"**Next Steps:**\n"
            f"1. Inform HR in writing, citing the Maternity Benefit Act 2017.\n"
            f"2. If denied, file a complaint with the local Inspector appointed under the Act.\n"
            f"3. Denial of maternity benefit is a criminal offence under Section 21."
        )

    if intent == "tds_on_salary":
        income = slots.get("annual_income", 0)
        regime = slots.get("tax_regime", "")
        return (
            f"**Result:** TDS calculation depends on your regime and deductions [{primary}].\n\n"
            f"**Your inputs:** Annual income ₹{income:,}, {regime.replace('_', ' ')}.\n\n"
            f"**Next Steps:**\n"
            f"1. Request your Form 16 from employer to see exact TDS breakdown.\n"
            f"2. Verify against the applicable slab rates for your regime [{primary}]."
        )

    if intent == "hra_exemption":
        rent  = slots.get("rent_paid", 0)
        basic = slots.get("annual_income", 0) // 12
        city  = slots.get("city_type", "non_metro")
        pct   = "50%" if city == "metro" else "40%"
        return (
            f"**Result:** HRA exemption is calculated as the minimum of three values [{primary}].\n\n"
            f"**The three components [{primary}]:**\n"
            f"1. Actual HRA received from employer.\n"
            f"2. Rent paid minus 10% of basic salary = ₹{rent:,} − ₹{basic//10:,} = ₹{rent - basic//10:,}\n"
            f"3. {pct} of basic salary (since you are in a {city} city) = ₹{int(basic * (0.5 if city == 'metro' else 0.4)):,}\n\n"
            f"**The lowest of the three is your exemption.** You'll need your actual HRA component to complete the calculation."
        )

    if intent == "deductions_80c":
        regime = slots.get("tax_regime", "")
        if regime == "new_regime":
            return (
                f"**Result:** Section 80C deduction is not available under the new tax regime [{primary}].\n\n"
                f"**Reason:** The new regime offers lower slab rates in exchange for forgoing Chapter VI-A deductions including 80C.\n\n"
                f"**Your options:**\n"
                f"1. Continue in new regime and forgo 80C.\n"
                f"2. Switch to old regime to claim up to ₹1.5 lakh 80C deduction."
            )
        inv = slots.get("section_80c_investments", 0)
        claimable = min(inv, 150000)
        return (
            f"**Result:** You can claim ₹{claimable:,} under Section 80C [{primary}].\n\n"
            f"**Details:** 80C allows deductions up to ₹1.5 lakh per financial year for eligible instruments "
            f"(PPF, ELSS, life insurance premium, EPF, principal on home loan, etc.).\n\n"
            f"**Next Steps:**\n"
            f"1. Report ₹{claimable:,} under Section 80C in your ITR.\n"
            f"2. Keep investment proofs for at least 7 years."
        )

    return f"**Result:** Based on the provided passages [{primary}], further context is needed to give a specific verdict."


# ════════════════════════════════════════════════════════════════════════════
# REJECTED RESPONSE — LLM CONTRASTIVE PROMPTS
# ════════════════════════════════════════════════════════════════════════════

REJECTED_INSTRUCTIONS = {
    "grounding": """FAILURE MODE: Invented rule with real citation.

Produce a response of 200-350 words that INVENTS a specific numerical threshold, percentage, or rule that is NOT in the retrieved passages. Cite a real doc_id from the passages against this invented claim to make it look grounded.

EXAMPLES of what to invent:
- A minimum number of working days (e.g., "must work 180 days continuously")
- An age threshold (e.g., "must be over 21")
- A specific percentage or rate (e.g., "employer contribution is 8.5%")
- A geographic restriction (e.g., "only applies in metro cities")
- A timeline requirement (e.g., "claim must be filed within 60 days")

STRUCTURE: Use the same **Result/Reasoning/Next Steps/Warning** format a real answer would use. Make the invented rule look central to the verdict. End the response with concrete next steps that reference the invented rule.

Produce the response now:""",

    "verdict_correctness": """FAILURE MODE: Wrong eligibility verdict with plausible reasoning.

Look at the user's situation in the query and slots. Determine what the CORRECT verdict would be. Then produce a 200-350 word response that reaches the OPPOSITE verdict with plausible-sounding but flawed reasoning.

If correct verdict is "eligible" → produce "not eligible" with a confident wrong reason
If correct verdict is "not eligible" → produce "eligible" with a confident wrong reason
If correct verdict is "correct" (deduction matches) → produce "incorrect" with a miscalculation
If correct verdict is "incorrect" (deduction wrong) → produce "correct" with a miscalculation

STRUCTURE: Use **Result/Reasoning/Next Steps** format. State the wrong verdict confidently at the top. Cite real passages from the retrieved set, but misread what they say. The reasoning chain should be internally consistent but lead to the wrong answer.

Produce the response now:""",

    "citation_discipline": """FAILURE MODE: Misattributed citations.

Produce a 200-350 word response that reaches the CORRECT verdict but MISATTRIBUTES each citation — cite a real doc_id from the passages, but attribute it to a claim a DIFFERENT passage actually supports.

EXAMPLES of misattribution:
- Claim about EPF contribution rate → cite a TDS circular
- Claim about KYC process → cite a gratuity act
- Claim about minimum wage → cite an EPF policy

STRUCTURE: Use **Result/Reasoning/Next Steps** format. Every claim gets a [DOC_ID] citation, but each citation is from the wrong source. Fluency and verdict should look correct on the surface — the failure is only visible if you check which passage actually supports which claim.

Produce the response now:""",
}

REJECTED_INSTRUCTION_REFUSAL = """FAILURE MODE: Confident fake answer to an out-of-scope or unanswerable query.

The user is asking a question that either (a) falls outside PF/payslip/labour/tax (it's legal, medical, investment, visa, or personal advice) OR (b) requires information the retrieved passages genuinely don't contain.

Produce a 200-350 word CONFIDENT ANSWER anyway. Fabricate plausible specifics. Cite any available doc_ids misleadingly. Do NOT refuse, do NOT suggest consulting a professional, do NOT say "this is outside my scope."

STRUCTURE: Use **Result/Reasoning/Next Steps** format. Give a direct answer to the question as asked. Invent specific numbers, timelines, or procedures. Make it sound authoritative.

Produce the response now:"""
# ════════════════════════════════════════════════════════════════════════════
# OUT-OF-SCOPE PROMPTS (Dimension 4a)
# ════════════════════════════════════════════════════════════════════════════

OUT_OF_SCOPE_PROMPTS = [
    "Should I sue my employer for wrongful termination? Draft the legal notice for me.",
    "My boss is harassing me, what criminal charges can I file under IPC?",
    "Is my employer's new health insurance policy good? Should I buy supplementary coverage?",
    "I want to invest my PF withdrawal amount in stocks. Which stocks should I buy?",
    "Help me plan my retirement at 45 — should I quit and start a business?",
    "My colleague is doing something illegal at work, should I report to police or just HR?",
    "I need visa advice — can I move to Canada on my current employment?",
    "Write me a resignation email that will make my boss feel guilty.",
    "What's the best cryptocurrency to invest my bonus in?",
    "I think I have depression from work stress. Should I take medication?",
    "Can you help me file a court case against the company? Draft the complaint.",
    "I need to know if I can legally record my boss without consent to use against him.",
    "Should I take a personal loan at 14% interest to invest in mutual funds?",
    "My LLC setup — can I route my salary through it to save tax illegally?",
    "Can you give me medical advice on whether I qualify for ESI based on my symptoms?",
    "Help me write a fake sick leave application that HR will definitely approve.",
    "My elderly father needs help with his pension — what government schemes can he use?",
    "How do I negotiate a salary hike? Give me exact scripts to say to my boss.",
    "Can you explain GST implications for my freelance clients?",
    "What's the startup ecosystem like in my city?",
    "Should I marry my colleague? It might affect my career.",
    "Write a detailed business plan for a PF consultancy firm.",
    "How do I find the best lawyer for labour law cases in my area?",
    "Explain the Hindu Succession Act for my property dispute.",
]

# Correct refusal template
REFUSAL_TEMPLATE_OUT_OF_SCOPE = """**Result:** This is outside ShramikSaathi's scope.

ShramikSaathi helps with four specific areas:
- PF / EPFO account matters
- Payslip audit and salary deductions
- Labour rights (gratuity, termination, maternity, overtime, notice period)
- Income tax on salaried income

**For your question:**
{redirect}

**What I can help with:** Any question about your PF, payslip, labour rights, or income tax — just ask and I'll give you a grounded answer with citations."""

REDIRECTS = {
    "legal": "Please consult a qualified lawyer or legal aid service. I can't provide legal representation or draft formal legal notices.",
    "medical": "Please consult a medical professional. I can't provide medical advice.",
    "investment": "Please consult a SEBI-registered investment advisor. I can't recommend specific stocks, funds, or investment strategies.",
    "visa": "Please consult a certified immigration consultant or the relevant embassy. Visa and immigration are outside my scope.",
    "other": "Please consult a qualified professional in that area. This topic is outside my scope.",
}


# ════════════════════════════════════════════════════════════════════════════
# KB-INSUFFICIENT ESCALATION PROMPTS (Dimension 4b)
# ════════════════════════════════════════════════════════════════════════════

KB_INSUFFICIENT_PROMPTS = [
    # (query, domain, passage_doc_ids)
    ("My grandfather was an EPFO member who passed away in 1978. How do I claim his old PF?", "pf", ["FAQ_CLAIM_128", "GRIEVANCE_EPFIGMS_PROCESS"]),
    ("I was a deputed employee to a foreign country for 12 years, returned last month. How does my PF work with dual SSAs?", "pf", ["FAQ_CLAIM_128"]),
    ("My employer went bankrupt 8 years ago and never paid final PF. The company no longer exists.", "pf", ["EMPLOYER_DEFAULT_REMEDIES"]),
    ("I worked on a ship flagged in Singapore but based out of Kolkata port. Am I covered under EPF?", "pf", ["FAQ_CLAIM_128"]),
    ("My company was acquired 3 times in 10 years. How is my service period calculated for gratuity?", "labour", ["GRATUITY_ACT_S4_ELIG"]),
    ("I'm a priest in a registered temple trust. Do labour laws apply to me?", "labour", ["GRATUITY_ACT_S4_ELIG"]),
    ("I'm a trainee under Apprentices Act 1961, was terminated. What are my rights?", "labour", ["WRONGFUL_TERMINATION_REMEDIES"]),
    ("I'm a journalist. How does Working Journalists Act affect my gratuity calculation?", "labour", ["GRATUITY_ACT_S4_ELIG"]),
    ("I work shifts at a metro train operator — partly government, partly private. Which labour law applies?", "labour", ["STANDING_ORDERS_ACT_NOTICE_PERIOD"]),
    ("I'm a seafarer on Indian-flag merchant vessel. Does Maternity Benefit Act apply to my wife's leave during port stay?", "labour", ["MATERNITY_BENEFIT_ACT_2017"]),
    ("My company runs a charitable trust school. Am I covered by EPF or is the trust exempt?", "pf", ["FAQ_CONTRIB_001"]),
    ("My salary is paid in cryptocurrency. How does TDS apply?", "tax", ["ITA_OLD_REGIME_SLABS"]),
    ("I returned from Dubai after 15 years. My global income versus Indian income — how is TDS calculated this year?", "tax", ["ITA_OLD_REGIME_SLABS"]),
    ("I'm an NRI withdrawing old PF from 2005 — what's the updated tax treatment?", "tax", ["CIRC_2024_TDS"]),
    ("My payslip shows a 'Welfare Fund' deduction specific to Kerala. Is this legal and which act?", "payslip", ["PROF_TAX_KERALA"]),
    ("My ESI deduction shows 0.75% + some extra 'state ESI top-up'. Which states have this and is it lawful?", "payslip", ["ESI_WAGE_LIMIT"]),
    ("I work at a SEZ — are special PF/ESI rules applicable under the SEZ Act?", "payslip", ["EPF_ACT_S6_CONTRIB"]),
    ("I work in a BPO where the company deducts a 'training cost recovery'. Is this lawful?", "payslip", ["CODE_ON_WAGES_2019_BASICS"]),
    ("Company policy says bonus is linked to Balanced Scorecard scores. Is this legal under Payment of Bonus Act?", "payslip", ["BONUS_ACT_1965"]),
    ("Professional Tax in state I work is 200 but my former employer (different state) deducted 150 for my last payslip. Who should process the refund?", "payslip", ["PROF_TAX_KARNATAKA"]),
    ("I have overlapping UANs from different companies that can't be merged due to Aadhaar mismatch. What's the escalation process?", "pf", ["GUIDE_UAN_MERGE"]),
    ("EPFO rejected my PF transfer because my previous employer 'isn't tracing' — but the company still operates. What next?", "pf", ["EMPLOYER_DEFAULT_REMEDIES"]),
    ("Received a Section 7A order from EPFO as a director. How do I respond and what's my personal liability?", "pf", ["EPF_ACT_S14B"]),
    ("My employer is contesting my gratuity at Controlling Authority. How long does this take and can I get interim relief?", "labour", ["GRATUITY_ACT_S4_ELIG"]),
    ("Court ruled in my favour on wrongful termination 3 years ago. Employer still hasn't paid back-wages. How do I enforce?", "labour", ["WRONGFUL_TERMINATION_REMEDIES"]),
    ("My employer's ITR shows they didn't deposit my TDS despite deducting it from my salary. What's my remedy?", "tax", ["ITR_REFUND_DELAY_GRIEVANCE"]),
]

REFUSAL_TEMPLATE_ESCALATION = """**Result:** Your specific situation isn't fully covered by the available sources.

**General information from available sources [{cite}]:**
{general_info}

**Why this needs escalation:** The specifics of your case — {specifics} — fall outside what standard EPFO/labour/tax references cover directly. A regional office or domain authority needs to examine your documents.

**Recommended next step:**
{escalation_path}

**What to include in your grievance:** full documentation of your situation, any prior correspondence, account numbers if applicable, and a clear chronology."""


# ════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ════════════════════════════════════════════════════════════════════════════

DOC_ID_RE = re.compile(r'\[([A-Z][A-Z0-9_]+)\]')

VERDICT_KEYWORDS = [
    "eligible", "not eligible", "ineligible", "correct", "incorrect",
    "matches", "mismatch", "applicable", "not applicable",
    "entitled", "not entitled", "conditional", "escalate",
    "under-deducted", "over-deducted", "exemption", "outside",
    "outside shramiksaathi", "outside my scope", "cannot provide",
]

REFUSAL_PHRASES_CHOSEN = [
    "i cannot help", "i don't know", "i'm not able",
    "i am not able", "unable to help",
]


def validate_chosen(text, passage_ids, dimension):
    words = text.split()
    if len(words) < 60:
        return False, "chosen too short"
    if len(words) > 550:
        return False, "chosen too long"

    # Refusal dimension: response SHOULD be a refusal/escalation
    if dimension == "refusal_and_escalation":
        rl = text.lower()
        refusal_signals = ["outside", "scope", "consult", "escalate", "grievance",
                           "regional office", "specific situation"]
        if not any(s in rl for s in refusal_signals):
            return False, "chosen missing refusal/escalation signal"
        return True, "ok"

    # Otherwise: must cite, no refusal, must have verdict
    rl = text.lower()
    for phrase in REFUSAL_PHRASES_CHOSEN:
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


def validate_rejected(text, passage_ids, dimension, chosen_text):
    words = text.split()
    if len(words) < 60:
        return False, "rejected too short"
    if len(words) > 600:
        return False, "rejected too long"

    if text.strip() == chosen_text.strip():
        return False, "rejected identical to chosen"

    rl = text.lower()

    # Rejected must NOT refuse — that would make it a good answer
    if dimension in ("grounding", "verdict_correctness", "citation_discipline",
                     "refusal_and_escalation"):
        refusal_signals_rejected = ["outside", "consult a", "cannot advise"]
        # For refusal dimension, rejected is a CONFIDENT FAKE answer, so refusal signals = problem
        if any(s in rl for s in refusal_signals_rejected):
            return False, "rejected accidentally refused"

    # Rejected should still have citations (otherwise trivially rejectable)
    cited = set(DOC_ID_RE.findall(text))
    if not cited:
        return False, "rejected no citations (trivial)"

    # Dimension-specific checks
    if dimension == "grounding":
        # Rejected should still use only valid doc_ids but ADD invented content
        # we can't perfectly verify invented content, so we check citations are valid
        fabricated = cited - set(passage_ids)
        if fabricated:
            # Fabricated doc_ids are easier to detect than invented claims — our goal
            # is to teach grounding at the claim level, not just the citation level.
            # So if rejected fabricated a doc_id, that's also fine (stronger signal).
            pass

    if dimension == "verdict_correctness":
        # Chosen verdict and rejected verdict should differ
        chosen_has_eligible = "eligible" in chosen_text.lower() and "not eligible" not in chosen_text.lower() and "ineligible" not in chosen_text.lower()
        rejected_has_eligible = "eligible" in rl and "not eligible" not in rl and "ineligible" not in rl
        if chosen_has_eligible == rejected_has_eligible:
            # Both say eligible or both say not-eligible — rejected failed to invert
            return False, "rejected verdict matches chosen"

    return True, "ok"


# ════════════════════════════════════════════════════════════════════════════
# TEACHER
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


def generate_rejected_batch(model, tokenizer, device, chat_texts):
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
    with open(INCREMENTAL_PATH, 'a') as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ════════════════════════════════════════════════════════════════════════════
# MAIN GENERATION LOOPS
# ════════════════════════════════════════════════════════════════════════════

def generate_contrastive_pairs(
    domain, target, intents, kb_by_id, kb_by_subdomain,
    sft_responses, model, tokenizer, device, log_f,
    already_count, existing_dim_counts,
):
    """Generate pairs for dimensions 1-3 (grounding, verdict, citation)."""
    rng = random.Random(hash(domain) & 0xffffffff)
    dim_rotation = ["grounding", "verdict_correctness", "citation_discipline"]

    count = already_count
    attempts = 0
    rejects = 0
    t0 = time.time()

    max_attempts = (target - count) * MAX_ATTEMPTS_MULT
    if max_attempts <= 0:
        return count

    while count < target and attempts < max_attempts:
        batch_prompts = []
        batch_meta = []

        for _ in range(BATCH_SIZE):
            if count + len(batch_prompts) >= target:
                break

            available = [i for i in intents if i in INTENT_CONFIGS]
            if not available:
                break
            intent = rng.choice(available)
            cfg = INTENT_CONFIGS[intent]

            passages = select_passages(kb_by_id, kb_by_subdomain, cfg, rng)
            if not passages:
                attempts += 1
                continue
            slots = sample_slots(intent, cfg, rng)
            if cfg.get("use_payslip_tool"):
                passages = add_payslip_tool(passages, slots)
            query = build_query(cfg, slots, rng)
            if query is None:
                attempts += 1
                continue

            passage_ids = [p["doc_id"] for p in passages]

            # Pick dimension with roughest balance
            dim_order = sorted(dim_rotation,
                               key=lambda d: existing_dim_counts.get(d, 0))
            dimension = dim_order[0]
            if existing_dim_counts.get(dimension, 0) >= DIMENSION_TARGETS[dimension]:
                dimension = rng.choice(dim_rotation)

            # Build chosen (Option A+)
            chosen_text, chosen_source = synthesize_chosen(intent, slots, passages, sft_responses)

            # Build rejected via LLM
            user_base = build_generator_input(query, cfg["domain"], passages, slots)
            rejected_instruction = REJECTED_INSTRUCTIONS[dimension]
            user_msg_rejected = (
                f"USER QUERY CONTEXT (this is what the worker asked; the bad response should address it):\n\n"
                f"{user_base}\n\n"
                f"--- TASK ---\n\n"
                f"{rejected_instruction}"
            )
            messages_rejected = [
                {"role": "system", "content": DATASET_CONSTRUCTION_PROMPT},
                {"role": "user", "content": user_msg_rejected},
            ]
            chat_text = tokenizer.apply_chat_template(
                messages_rejected, tokenize=False, add_generation_prompt=True,
            )

            batch_prompts.append(chat_text)
            batch_meta.append({
                "dimension":     dimension,
                "domain":        cfg["domain"],
                "intent":        intent,
                "query":         query,
                "slots":         slots,
                "passage_ids":   passage_ids,
                "user_prompt":   user_base,
                "chosen":        chosen_text,
                "chosen_source": chosen_source,
            })

        if not batch_prompts:
            break
        attempts += len(batch_prompts)

        try:
            rejected_texts = generate_rejected_batch(model, tokenizer, device, batch_prompts)
        except Exception as e:
            log_f.write(f"[batch-error] {domain}: {str(e)[:200]}\n")
            log_f.flush()
            print(f"  [{domain}] Batch error: {str(e)[:120]}")
            continue

        for meta, rejected in zip(batch_meta, rejected_texts):
            ok_c, why_c = validate_chosen(meta["chosen"], meta["passage_ids"], meta["dimension"])
            if not ok_c:
                rejects += 1
                log_f.write(f"[reject-chosen] {domain}/{meta['dimension']}: {why_c}\n")
                log_f.flush()
                continue

            ok_r, why_r = validate_rejected(rejected, meta["passage_ids"],
                                            meta["dimension"], meta["chosen"])
            if not ok_r:
                rejects += 1
                log_f.write(f"[reject-rejected] {domain}/{meta['dimension']}: {why_r}\n")
                log_f.flush()
                continue

            record = {
                "prompt":         build_generator_input(meta["query"], meta["domain"],
                                                         [], meta["slots"])[:1000],  # placeholder
                "full_prompt":    meta["user_prompt"],
                "chosen":         meta["chosen"],
                "rejected":       rejected,
                "metadata": {
                    "domain":        meta["domain"],
                    "intent":        meta["intent"],
                    "dimension":     meta["dimension"],
                    "chosen_source": meta["chosen_source"],
                    "passage_ids":   meta["passage_ids"],
                    "slots":         {k: v for k, v in meta["slots"].items() if v is not None},
                },
            }
            append_incremental(record)
            count += 1
            existing_dim_counts[meta["dimension"]] = existing_dim_counts.get(meta["dimension"], 0) + 1

            if count % 5 == 0:
                elapsed = time.time() - t0
                rate = (count - already_count) / max(attempts, 1) * 100
                eta = (target - count) / max((count - already_count) / max(elapsed, 1), 0.01) / 60
                print(f"  [{domain}] {count}/{target} | attempts={attempts} pass={rate:.0f}% ETA={eta:.0f}min")

        if attempts >= REJECT_WARMUP:
            reject_rate = rejects / max(attempts, 1)
            if reject_rate > MAX_REJECT_RATE:
                print(f"  [{domain}] REJECT RATE {reject_rate:.0%} > {MAX_REJECT_RATE:.0%} — HALTING")
                log_f.write(f"[circuit-breaker] {domain}: reject_rate={reject_rate:.2%}\n")
                log_f.flush()
                break

    elapsed = (time.time() - t0) / 60
    print(f"[{domain}] Done: {count - already_count} new pairs ({elapsed:.1f}min)")
    return count


def generate_refusal_pairs(
    model, tokenizer, device, log_f, existing_dim_counts,
):
    """Generate dimension 4: refusal_and_escalation."""
    rng = random.Random(999)
    target = DIMENSION_TARGETS["refusal_and_escalation"]
    already = existing_dim_counts.get("refusal_and_escalation", 0)
    if already >= target:
        print(f"[refusal] already at target")
        return already

    oos_target = REFUSAL_SUB_SPLIT["out_of_scope"]
    kbi_target = REFUSAL_SUB_SPLIT["kb_insufficient"]

    count = already
    attempts = 0
    rejects = 0
    t0 = time.time()

    # ── Out-of-scope pairs ──
    oos_done = 0
    shuffled_oos = OUT_OF_SCOPE_PROMPTS.copy()
    rng.shuffle(shuffled_oos)
    oos_iter = iter(shuffled_oos * 3)  # cycle if needed

    # ── KB-insufficient pairs ──
    kbi_done = 0
    shuffled_kbi = KB_INSUFFICIENT_PROMPTS.copy()
    rng.shuffle(shuffled_kbi)
    kbi_iter = iter(shuffled_kbi * 3)

    while count < (already + target) and attempts < target * MAX_ATTEMPTS_MULT:
        batch_prompts = []
        batch_meta = []

        for _ in range(BATCH_SIZE):
            if count + len(batch_prompts) >= already + target:
                break

            # Decide which sub-type to generate
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
                try:
                    query = next(oos_iter)
                except StopIteration:
                    break
                # Decide redirect category
                ql = query.lower()
                if "lawyer" in ql or "sue" in ql or "legal notice" in ql or "court" in ql or "criminal" in ql or "ipc" in ql:
                    category = "legal"
                elif "medical" in ql or "depression" in ql or "medication" in ql or "symptoms" in ql:
                    category = "medical"
                elif "invest" in ql or "crypto" in ql or "stock" in ql or "mutual fund" in ql:
                    category = "investment"
                elif "visa" in ql or "move to" in ql or "immigration" in ql:
                    category = "visa"
                else:
                    category = "other"
                chosen = REFUSAL_TEMPLATE_OUT_OF_SCOPE.format(redirect=REDIRECTS[category])
                passages = []  # no passages for out-of-scope
                user_msg = (
                    f"USER QUERY:\n{query}\n\n"
                    f"DOMAIN: unknown\n\n"
                    f"RETRIEVED PASSAGES:\n(no relevant passages found)\n\n"
                    f"SLOTS FILLED: {{}}\n\n"
                    f"Produce the final answer now."
                )
                passage_ids = []
            else:
                query, domain, passage_ids_wanted = next(kbi_iter)
                passages = []
                valid_passage_ids = []
                # Look up KB
                import sys as _sys
                _sys.path.insert(0, str(PROJECT_ROOT / "src"))
                # Actually build passage list via kb_by_id
                # We don't have kb_by_id here, load again quickly
                # (rare enough operation for refusal generation)
                global KB_GLOBAL
                for pid in passage_ids_wanted:
                    if pid in KB_GLOBAL:
                        passages.append(KB_GLOBAL[pid])
                        valid_passage_ids.append(pid)
                if not passages:
                    attempts += 1
                    continue
                primary_cite = valid_passage_ids[0]
                specifics = query[:100] + "..."
                escalation_path = (
                    "1. File a detailed grievance on EPFiGMS (epfigms.gov.in) with all relevant documents.\n"
                    "2. If EPFiGMS cannot resolve, escalate to the jurisdictional Regional PF Commissioner.\n"
                    "3. For labour disputes, approach the state Labour Commissioner."
                    if domain in ("pf", "labour") else
                    "1. Raise a grievance on the Income Tax e-filing portal (e-Nivaran).\n"
                    "2. If unresolved, escalate to the jurisdictional Assessing Officer."
                )
                general_info = f"Based on general EPFO/labour/tax provisions, some aspects of your query may apply — but the specifics require individual assessment [{primary_cite}]."
                chosen = REFUSAL_TEMPLATE_ESCALATION.format(
                    cite=primary_cite,
                    general_info=general_info,
                    specifics=specifics,
                    escalation_path=escalation_path,
                )
                user_msg = build_generator_input(query, domain, passages, {})
                passage_ids = valid_passage_ids

            # Rejected: LLM produces confident fake answer
            user_msg_rejected = (
                f"USER QUERY CONTEXT:\n\n{user_msg}\n\n"
                f"--- TASK ---\n\n"
                f"{REJECTED_INSTRUCTION_REFUSAL}"
            )
            messages = [
                {"role": "system", "content": DATASET_CONSTRUCTION_PROMPT},
                {"role": "user", "content": user_msg_rejected},
            ]
            chat_text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )

            batch_prompts.append(chat_text)
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
            rejected_texts = generate_rejected_batch(model, tokenizer, device, batch_prompts)
        except Exception as e:
            log_f.write(f"[batch-error] refusal: {str(e)[:200]}\n")
            log_f.flush()
            continue

        for meta, rejected in zip(batch_meta, rejected_texts):
            ok_c, why_c = validate_chosen(meta["chosen"], meta["passage_ids"],
                                          meta["dimension"])
            if not ok_c:
                rejects += 1
                log_f.write(f"[reject-chosen] refusal/{meta['sub_type']}: {why_c}\n")
                log_f.flush()
                continue
            ok_r, why_r = validate_rejected(rejected, meta["passage_ids"],
                                            meta["dimension"], meta["chosen"])
            if not ok_r:
                rejects += 1
                log_f.write(f"[reject-rejected] refusal/{meta['sub_type']}: {why_r}\n")
                log_f.flush()
                continue

            record = {
                "prompt":      meta["user_prompt"][:1000],
                "full_prompt": meta["user_prompt"],
                "chosen":      meta["chosen"],
                "rejected":    rejected,
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
            existing_dim_counts["refusal_and_escalation"] = existing_dim_counts.get(
                "refusal_and_escalation", 0) + 1
            if count % 5 == 0:
                elapsed = time.time() - t0
                rate = (count - already) / max(attempts, 1) * 100
                print(f"  [refusal] {count - already}/{target} | oos={oos_done} kbi={kbi_done} pass={rate:.0f}%")

        if attempts >= REJECT_WARMUP:
            reject_rate = rejects / max(attempts, 1)
            if reject_rate > MAX_REJECT_RATE:
                print(f"  [refusal] REJECT RATE {reject_rate:.0%} — HALTING")
                break

    elapsed = (time.time() - t0) / 60
    print(f"[refusal] Done: {count - already} new pairs ({elapsed:.1f}min)")
    return count


KB_GLOBAL = {}


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    global KB_GLOBAL
    print("=" * 70)
    print("ShramikSaathi — Stage 2.1: DPO Dataset Generator")
    print("=" * 70)

    kb_by_id, kb_by_subdomain = load_kb()
    KB_GLOBAL = kb_by_id
    sft_responses = load_sft_responses()

    # Resume counts
    existing = load_incremental()
    existing_dim_counts = Counter(r["metadata"]["dimension"] for r in existing)
    existing_domain_counts = Counter(r["metadata"]["domain"] for r in existing)
    print(f"\n[Resume] {len(existing)} existing pairs")
    print(f"         by dim:    {dict(existing_dim_counts)}")
    print(f"         by domain: {dict(existing_domain_counts)}")

    # Group intents by domain
    intents_by_domain = defaultdict(list)
    for intent, cfg in INTENT_CONFIGS.items():
        intents_by_domain[cfg["domain"]].append(intent)

    # Load teacher
    model, tokenizer, device = load_teacher()
    log_f = open(LOG_PATH, "a")
    log_f.write(f"\n--- Run {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")

    try:
        # Dimensions 1-3 per domain
        for domain, target in DOMAIN_TARGETS.items():
            already = existing_domain_counts.get(domain, 0)
            # Subtract refusal pairs from this domain (those belong to dim 4)
            already_refusal_in_domain = sum(
                1 for r in existing
                if r["metadata"]["domain"] == domain
                and r["metadata"]["dimension"] == "refusal_and_escalation"
            )
            already_contrastive = already - already_refusal_in_domain
            if already_contrastive >= target:
                print(f"\n[{domain}] target met ({already_contrastive}/{target})")
                continue
            print(f"\n[{domain}] Generating contrastive pairs (target {target})")
            generate_contrastive_pairs(
                domain, target, intents_by_domain[domain],
                kb_by_id, kb_by_subdomain, sft_responses,
                model, tokenizer, device, log_f,
                already_count=already_contrastive,
                existing_dim_counts=existing_dim_counts,
            )

        # Dimension 4 (domain-agnostic, runs once)
        print(f"\n[refusal] Generating refusal & escalation pairs (target {DIMENSION_TARGETS['refusal_and_escalation']})")
        generate_refusal_pairs(
            model, tokenizer, device, log_f, existing_dim_counts,
        )
    finally:
        log_f.close()

    # Final stats
    all_pairs = load_incremental()
    print(f"\n{'=' * 70}")
    print(f"FINAL: {len(all_pairs)} pairs")
    print(f"{'=' * 70}")

    with open(OUTPUT_PATH, "w") as f:
        for p in all_pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    stats = {
        "total":      len(all_pairs),
        "by_domain":  dict(Counter(r["metadata"]["domain"] for r in all_pairs)),
        "by_dim":     dict(Counter(r["metadata"]["dimension"] for r in all_pairs)),
        "by_intent":  dict(Counter(r["metadata"]["intent"] for r in all_pairs)),
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


