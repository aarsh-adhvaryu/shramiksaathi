"""
ShramikSaathi — SFT Dataset Generator (Stage 1.1)

Generates ~400 validated (prompt, response) pairs for LoRA SFT.
Teacher: LLaMA 3.1 8B Instruct, local inference on Lightning A100.
Goal: teach the Generator OUTPUT FORMAT (verdict + trace + citations + steps).

SFT SCOPE (what this trains):
    - Output structure: verdict → trace → citations → steps → caveats
    - Citation syntax: [DOC_ID] inline
    - Mirroring the eligibility trace from reasoning into the answer
    - Using slot values correctly in the answer
    - Non-technical tone baseline
    - Format for TOOL_PAYSLIP_AUDIT output (Option A, payslip verification)

NOT IN SFT SCOPE (deferred to Stage 2 DPO + runtime validator):
    - Hallucinated doc_id suppression
    - Over-hedging on met conditions
    - Trace-skipping penalty
    - Escalate-vs-guess preference
    - Borderline verdict choice

Run from project root on Lightning:
    python src/generate_sft_dataset.py

Resumable: re-run to continue from .sft_incremental.jsonl
Outputs:
    data/sft_train.jsonl         (90% split)
    data/sft_val.jsonl           (10% split)
    data/sft_generation_stats.json
    data/sft_generation.log
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
KB_PATH = PROJECT_ROOT / "data" / "kb.jsonl"
TRAIN_OUT = PROJECT_ROOT / "data" / "sft_train.jsonl"
VAL_OUT = PROJECT_ROOT / "data" / "sft_val.jsonl"
INCREMENTAL_PATH = PROJECT_ROOT / "data" / ".sft_incremental.jsonl"
STATS_PATH = PROJECT_ROOT / "data" / "sft_generation_stats.json"
LOG_PATH = PROJECT_ROOT / "data" / "sft_generation.log"

MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"
BATCH_SIZE = 4
MAX_NEW_TOKENS = 600
TEMPERATURE = 0.6
TOP_P = 0.9

DOMAIN_TARGETS = {
    "payslip": 40,
    "tax": 35,
}

# Per-subdomain cap = min(abs_cap, n_docs_in_subdomain * multiplier)
SUBDOMAIN_CAPS = {
    "payslip": {"abs_cap": 20, "per_doc": 10},
    "tax": {"abs_cap": 20, "per_doc": 10},
}

# Circuit breaker: halt domain if reject rate exceeds this after warmup
MAX_REJECT_RATE = 0.40
REJECT_WARMUP = 50
MAX_ATTEMPTS_MULT = 3  # stop trying after target * multiplier attempts

VAL_FRACTION = 0.10


# ════════════════════════════════════════════════════════════════════════════
# COPIED VERBATIM FROM src/pipeline.py — KEEP IN SYNC IF PIPELINE CHANGES
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


REASONING_INTENTS = {
    "full_withdrawal",
    "partial_withdrawal",
    "transfer",
    "tds_query",
    "kyc_issue",
    "verify_epf",
    "verify_esi",
    "check_deductions",
    "check_minimum_wage",
    "full_audit",
    "gratuity",
    "wrongful_termination",
    "maternity_benefit",
    "overtime_pay",
    "tds_on_salary",
    "tds_on_pf",
    "hra_exemption",
    "deductions_80c",
}


def format_passages_for_prompt(passages):
    """Matches SearchKB.format_for_prompt() byte-for-byte."""
    parts = []
    for i, r in enumerate(passages):
        parts.append(
            f"[Source {i+1}] doc_id={r['doc_id']} | "
            f"date={r.get('effective_date')} | domain={r.get('domain','')}\n"
            f"{r['content'][:1500]}"
        )
    return "\n\n---\n\n".join(parts)


def build_generator_input(query, domain, passages, reasoning, slots):
    """Matches pipeline._build_generator_input() byte-for-byte."""
    passages_text = format_passages_for_prompt(passages)
    reasoning_text = ""

    if reasoning:
        decision = reasoning.get("decision", "")
        eligible = reasoning.get("eligible")
        coverage = reasoning.get("coverage", 0)
        met = reasoning.get("met", [])
        failed = reasoning.get("failed", [])
        warnings = reasoning.get("warnings", [])
        unresolved = reasoning.get("unresolved", [])

        lines = ["ELIGIBILITY REASONING TRACE:", f"  Decision : {decision}"]
        if eligible is not None:
            lines.append(f"  Eligible : {eligible}")
        lines.append(f"  Coverage : {coverage}")

        if met:
            lines.append("  Met conditions:")
            for c in met:
                lines.append(
                    f"    ✓ {c.get('field','?')} {c.get('operator','?')} {c.get('value','?')} [{c.get('doc_id','?')}]"
                )
        if failed:
            lines.append("  Failed conditions:")
            for c in failed:
                lines.append(
                    f"    ✗ {c.get('field','?')} {c.get('operator','?')} {c.get('value','?')} [{c.get('doc_id','?')}] (user value: {c.get('slot_value')})"
                )
        if warnings:
            lines.append("  Warnings (non-blocking):")
            for c in warnings:
                lines.append(
                    f"    ⚠ {c.get('field','?')} {c.get('operator','?')} {c.get('value','?')} [{c.get('doc_id','?')}]"
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

Produce the final answer now. IMPORTANT: every factual claim must include [DOC_ID] in brackets — no exceptions. If you cannot cite, omit the claim."""


# ════════════════════════════════════════════════════════════════════════════
# KB LOADING
# ════════════════════════════════════════════════════════════════════════════


def load_kb():
    by_id = {}
    by_subdomain = defaultdict(list)
    subdomain_counts = Counter()
    with open(KB_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            if len(doc.get("content", "")) < 50:
                continue
            doc_id = doc.get("doc_id", "")
            if not doc_id:
                continue
            by_id[doc_id] = doc
            key = (doc.get("domain", ""), doc.get("subdomain", ""))
            by_subdomain[key].append(doc_id)
            subdomain_counts[key] += 1

    print(f"[KB] Loaded {len(by_id)} docs")
    for (dom, sub), n in sorted(subdomain_counts.items()):
        print(f"       {dom}/{sub}: {n}")
    return by_id, by_subdomain, subdomain_counts


# ════════════════════════════════════════════════════════════════════════════
# INTENT CONFIGS — templates, slot samplers, trace conditions
#
# Each config declares the intent's domain, which subdomains its passages
# come from, any cross-cutting doc_ids to include, query templates, slot
# value ranges, and (for reasoning intents) the conditions to check in
# the synthesized trace.
# ════════════════════════════════════════════════════════════════════════════

INTENT_CONFIGS = {
    # ──── PF ────────────────────────────────────────────────────────────────
    "full_withdrawal": {
        "domain": "pf",
        "subdomains": ["withdrawal"],
        "cross_doc_ids": ["CIRC_2024_TDS"],
        "templates": [
            "I left my job {months_unemployed} months ago. Worked {service_years} years total. My UAN is {uan_status} and KYC is {kyc_status}. Want to withdraw full PF balance.",
            "Unemployed for {months_unemployed} months now. Total service was {service_years} years. UAN {uan_status}, KYC {kyc_status}. Job chhoda, full PF withdrawal kaise karu?",
        ],
        "slot_ranges": {
            "employment_status": ["unemployed"],
            "months_unemployed": [1, 2, 3, 4, 6, 8, 12],
            "service_years": [2, 3, 4, 5, 6, 8, 10, 15],
            "uan_status": ["active"],
            "kyc_status": ["complete", "partial", "complete", "complete"],
        },
        "trace_conditions": [
            {
                "field": "employment_status",
                "operator": "eq",
                "value": "unemployed",
                "mandatory": True,
            },
            {
                "field": "months_unemployed",
                "operator": "gte",
                "value": 2,
                "mandatory": True,
            },
            {
                "field": "uan_status",
                "operator": "eq",
                "value": "active",
                "mandatory": True,
            },
            {
                "field": "kyc_status",
                "operator": "eq",
                "value": "complete",
                "mandatory": True,
            },
            {
                "field": "service_years",
                "operator": "gte",
                "value": 5,
                "mandatory": False,
                "cross_doc": "CIRC_2024_TDS",
            },
        ],
    },
    "partial_withdrawal": {
        "domain": "pf",
        "subdomains": ["withdrawal"],
        "cross_doc_ids": [],
        "templates": [
            "Still employed. Need partial PF withdrawal for {reason}. Service is {service_years} years. UAN {uan_status}, KYC {kyc_status}.",
            "Currently working. {reason} ke liye PF advance chahiye. {service_years} saal kaam kiya. UAN {uan_status}, KYC {kyc_status}.",
        ],
        "slot_ranges": {
            "employment_status": ["employed"],
            "service_years": [3, 5, 6, 7, 10],
            "uan_status": ["active"],
            "kyc_status": ["complete", "partial"],
            "reason": [
                "medical emergency",
                "house purchase",
                "marriage",
                "education",
                "home loan repayment",
            ],
        },
        "trace_conditions": [
            {
                "field": "service_years",
                "operator": "gte",
                "value": 5,
                "mandatory": True,
            },
            {
                "field": "uan_status",
                "operator": "eq",
                "value": "active",
                "mandatory": True,
            },
            {
                "field": "kyc_status",
                "operator": "eq",
                "value": "complete",
                "mandatory": True,
            },
        ],
    },
    "transfer": {
        "domain": "pf",
        "subdomains": ["transfer"],
        "cross_doc_ids": [],
        "templates": [
            "Changed jobs. Need to transfer PF from old employer to new employer. UAN is {uan_status}, KYC {kyc_status}.",
            "Job switch kiya. Old PF account ka transfer karna hai. UAN {uan_status}, KYC {kyc_status}.",
        ],
        "slot_ranges": {
            "employment_status": ["employed"],
            "uan_status": ["active", "inactive"],
            "kyc_status": ["complete", "partial", "incomplete"],
        },
        "trace_conditions": [
            {
                "field": "uan_status",
                "operator": "eq",
                "value": "active",
                "mandatory": True,
            },
            {
                "field": "kyc_status",
                "operator": "eq",
                "value": "complete",
                "mandatory": True,
            },
        ],
    },
    "kyc_issue": {
        "domain": "pf",
        "subdomains": ["kyc", "uan"],
        "cross_doc_ids": [],
        "templates": [
            "My KYC is {kyc_status} on EPFO portal. Aadhaar mismatch with PAN. UAN is {uan_status}.",
            "EPFO portal me KYC {kyc_status} dikha raha. Aadhaar aur PAN me name mismatch hai. UAN {uan_status}.",
        ],
        "slot_ranges": {
            "kyc_status": ["rejected", "incomplete", "partial"],
            "uan_status": ["active", "inactive"],
        },
        "trace_conditions": [],
    },
    "tds_query": {
        "domain": "pf",
        "subdomains": ["taxation", "withdrawal"],
        "cross_doc_ids": ["CIRC_2024_TDS"],
        "templates": [
            "Withdrew my PF of ₹{pf_withdrawal_amount}. Service was {service_years} years. Will TDS apply?",
            "PF nikala ₹{pf_withdrawal_amount}. Total service {service_years} saal. TDS katega kya?",
        ],
        "slot_ranges": {
            "pf_withdrawal_amount": [30000, 45000, 55000, 75000, 120000, 250000],
            "service_years": [2, 3, 4, 5, 6, 8],
        },
        "trace_conditions": [
            {
                "field": "service_years",
                "operator": "gte",
                "value": 5,
                "mandatory": False,
            },
            {
                "field": "pf_withdrawal_amount",
                "operator": "lte",
                "value": 50000,
                "mandatory": False,
            },
        ],
    },
    "employer_complaint": {
        "domain": "pf",
        "subdomains": ["employer", "grievance"],
        "cross_doc_ids": [],
        "templates": [
            "Employer is deducting PF from my salary but {incident_type}. PF amount shown in payslip but not in EPFO passbook for {months_unemployed} months.",
            "Salary se PF kat raha hai par {incident_type} — {months_unemployed} mahine se EPFO passbook me nahi aa raha.",
        ],
        "slot_ranges": {
            "employment_status": ["employed"],
            "incident_type": ["non_deposit", "wrong_amount", "delayed_deposit"],
            "months_unemployed": [2, 3, 6, 12],  # months of non-deposit, reusing field
        },
        "trace_conditions": [],
    },
    # ──── PAYSLIP ────────────────────────────────────────────────────────────
    "verify_epf": {
        "domain": "payslip",
        "subdomains": ["epf_deduction"],
        "cross_doc_ids": [],
        "templates": [
            "Basic salary ₹{basic_salary}. Employer deducting ₹{epf_deducted} as EPF every month. Is this correct?",
            "Basic ₹{basic_salary} hai aur PF kat raha ₹{epf_deducted}. Sahi hai ya kam/zyada?",
        ],
        "slot_ranges": {
            "basic_salary": [12000, 15000, 18000, 20000, 25000, 30000, 40000],
            "epf_deducted": None,  # computed from basic_salary
            "gross_salary": None,  # computed
        },
        "trace_conditions": [],
        "use_payslip_tool": True,
    },
    "verify_esi": {
        "domain": "payslip",
        "subdomains": ["esi_deduction"],
        "cross_doc_ids": [],
        "templates": [
            "Gross salary ₹{gross_salary}. ESI being deducted is ₹{esi_deducted}. Verify?",
            "Gross ₹{gross_salary}, ESI kat raha ₹{esi_deducted}. Sahi hai?",
        ],
        "slot_ranges": {
            "gross_salary": [15000, 18000, 20000, 22000, 25000],
            "esi_deducted": None,
            "basic_salary": None,
        },
        "trace_conditions": [],
        "use_payslip_tool": True,
    },
    "check_minimum_wage": {
        "domain": "payslip",
        "subdomains": ["minimum_wage"],
        "cross_doc_ids": [],
        "templates": [
            "Working in {state} as unskilled worker. Monthly gross is ₹{gross_salary}. Is this meeting minimum wage?",
            "{state} me kaam karta hu, monthly ₹{gross_salary} milta hai. Minimum wage mil raha ya nahi?",
        ],
        "slot_ranges": {
            "state": [
                "Maharashtra",
                "Karnataka",
                "Gujarat",
                "Tamil Nadu",
                "Delhi",
                "Kerala",
            ],
            "gross_salary": [8000, 10000, 12000, 14000, 16000, 18000],
        },
        "trace_conditions": [],
    },
    "full_audit": {
        "domain": "payslip",
        "subdomains": ["epf_deduction", "esi_deduction", "professional_tax"],
        "cross_doc_ids": [],
        "templates": [
            "Basic ₹{basic_salary}, Gross ₹{gross_salary}, state {state}. EPF deducted ₹{epf_deducted}, ESI ₹{esi_deducted}. Audit my payslip.",
            "Basic {basic_salary}, Gross {gross_salary}, {state} me hu. PF kata {epf_deducted}, ESI {esi_deducted}. Pura audit karo.",
        ],
        "slot_ranges": {
            "basic_salary": [15000, 18000, 20000, 25000],
            "gross_salary": None,  # computed
            "state": ["Maharashtra", "Karnataka", "Gujarat", "Tamil Nadu"],
            "epf_deducted": None,
            "esi_deducted": None,
        },
        "trace_conditions": [],
        "use_payslip_tool": True,
    },
    # ──── LABOUR ─────────────────────────────────────────────────────────────
    "gratuity": {
        "domain": "labour",
        "subdomains": ["gratuity"],
        "cross_doc_ids": [],
        "templates": [
            "Worked {employment_years} years at a {employer_type} company. {termination_reason}. Last drawn salary was ₹{last_drawn_salary}. Am I eligible for gratuity?",
            "{employment_years} saal {employer_type} me kaam kiya, {termination_reason}. Last salary ₹{last_drawn_salary}. Gratuity milega?",
        ],
        "slot_ranges": {
            "employment_years": [3, 4, 5, 6, 7, 10, 15],
            "termination_reason": ["resignation", "retirement", "employer_terminated"],
            "employer_type": ["private", "factory", "shop_establishment"],
            "last_drawn_salary": [25000, 35000, 45000, 60000, 80000],
        },
        "trace_conditions": [
            {
                "field": "employment_years",
                "operator": "gte",
                "value": 5,
                "mandatory": True,
            },
            {
                "field": "termination_reason",
                "operator": "in",
                "value": [
                    "resignation",
                    "retirement",
                    "employer_terminated",
                    "retrenched",
                ],
                "mandatory": True,
            },
        ],
    },
    "wrongful_termination": {
        "domain": "labour",
        "subdomains": ["termination"],
        "cross_doc_ids": [],
        "templates": [
            "Worked {employment_years} years. Employer terminated me without notice or any written communication. {employer_type} company.",
            "{employment_years} saal kaam kiya, bina notice ke nikal diya. {employer_type} company hai.",
        ],
        "slot_ranges": {
            "employment_years": [1, 2, 3, 5, 8],
            "termination_reason": ["employer_terminated"],
            "employer_type": ["private", "factory", "shop_establishment"],
            "notice_period_days": [0, 15, 30],
        },
        "trace_conditions": [
            {
                "field": "termination_reason",
                "operator": "eq",
                "value": "employer_terminated",
                "mandatory": True,
            },
        ],
    },
    "maternity_benefit": {
        "domain": "labour",
        "subdomains": ["maternity"],
        "cross_doc_ids": [],
        "templates": [
            "I am pregnant ({employment_years} years at current {employer_type} company). Manager says only {notice_period_days} days maternity leave. Is that correct?",
            "Pregnant hu, {employment_years} saal ho gaye {employer_type} company me. Manager {notice_period_days} din hi maternity leave de raha. Sahi hai?",
        ],
        "slot_ranges": {
            "is_pregnant": [True],
            "employment_years": [1, 2, 3, 5],
            "employer_type": ["private", "factory", "shop_establishment", "government"],
            "notice_period_days": [45, 60, 84, 90, 120, 180],
        },
        "trace_conditions": [
            {
                "field": "is_pregnant",
                "operator": "eq",
                "value": True,
                "mandatory": True,
            },
        ],
    },
    "notice_period": {
        "domain": "labour",
        "subdomains": ["termination"],
        "cross_doc_ids": [],
        "templates": [
            "Resigned from {employer_type} job. Offer letter says {notice_period_days} days notice. Worked {employment_years} years. Can employer force full notice?",
            "{employer_type} job chhod raha, offer letter me {notice_period_days} din notice likha. {employment_years} saal ho gaye.",
        ],
        "slot_ranges": {
            "employer_type": ["private", "shop_establishment", "factory"],
            "notice_period_days": [15, 30, 60, 90],
            "employment_years": [1, 2, 3, 5, 8],
            "termination_reason": ["resignation"],
        },
        "trace_conditions": [],
    },
    # ──── TAX ────────────────────────────────────────────────────────────────
    "tds_on_salary": {
        "domain": "tax",
        "subdomains": ["tds_salary"],
        "cross_doc_ids": [],
        "templates": [
            "Annual income ₹{annual_income}, on {tax_regime}. How much TDS will be deducted from salary monthly?",
            "Annual income {annual_income}, {tax_regime} select kiya. Monthly TDS kitna katega salary se?",
        ],
        "slot_ranges": {
            "annual_income": [500000, 700000, 900000, 1200000, 1500000, 2000000],
            "tax_regime": ["old_regime", "new_regime"],
        },
        "trace_conditions": [],
    },
    "tds_on_pf": {
        "domain": "tax",
        "subdomains": ["tds_pf", "taxation"],
        "cross_doc_ids": ["CIRC_2024_TDS"],
        "templates": [
            "Withdrew PF ₹{pf_withdrawal_amount}, service was {service_years} years. TDS implications?",
            "PF nikala ₹{pf_withdrawal_amount}, service {service_years} saal. TDS par kya asar hoga?",
        ],
        "slot_ranges": {
            "pf_withdrawal_amount": [40000, 55000, 80000, 150000, 300000],
            "service_years": [2, 3, 4, 5, 7],
        },
        "trace_conditions": [
            {
                "field": "service_years",
                "operator": "gte",
                "value": 5,
                "mandatory": False,
            },
            {
                "field": "pf_withdrawal_amount",
                "operator": "lte",
                "value": 50000,
                "mandatory": False,
            },
        ],
    },
    "hra_exemption": {
        "domain": "tax",
        "subdomains": ["hra"],
        "cross_doc_ids": [],
        "templates": [
            "Annual income ₹{annual_income}, {tax_regime}. Paying ₹{rent_paid}/month rent in {city_type} city. HRA exemption?",
            "Income ₹{annual_income}, {tax_regime}, {city_type} city me ₹{rent_paid} rent de raha. HRA exemption calculate karo.",
        ],
        "slot_ranges": {
            "annual_income": [600000, 900000, 1200000, 1800000, 2500000],
            "tax_regime": ["old_regime"],
            "rent_paid": [12000, 18000, 25000, 35000, 50000],
            "city_type": ["metro", "non_metro"],
        },
        "trace_conditions": [
            {
                "field": "tax_regime",
                "operator": "eq",
                "value": "old_regime",
                "mandatory": True,
            },
        ],
    },
    "deductions_80c": {
        "domain": "tax",
        "subdomains": ["deductions"],
        "cross_doc_ids": [],
        "templates": [
            "Income ₹{annual_income}, {tax_regime}. Invested ₹{section_80c_investments} in PPF/ELSS. How much 80C deduction?",
            "Annual income {annual_income}, {tax_regime} me hu, 80C me {section_80c_investments} invest kiya. Deduction kitna milega?",
        ],
        "slot_ranges": {
            "annual_income": [600000, 1000000, 1500000, 2000000],
            "tax_regime": ["old_regime", "new_regime"],
            "section_80c_investments": [50000, 100000, 150000, 200000],
        },
        "trace_conditions": [
            {
                "field": "tax_regime",
                "operator": "eq",
                "value": "old_regime",
                "mandatory": True,
            },
        ],
    },
    "refund_status": {
        "domain": "tax",
        "subdomains": ["refund"],
        "cross_doc_ids": [],
        "templates": [
            "Filed ITR {months_unemployed} months ago. Refund still not credited. How to check status?",
            "ITR file kiye {months_unemployed} mahine ho gaye, refund abhi tak nahi aaya. Status kaise check karu?",
        ],
        "slot_ranges": {
            "months_unemployed": [1, 2, 3, 6],  # reused as months since ITR
        },
        "trace_conditions": [],
    },
}


# ════════════════════════════════════════════════════════════════════════════
# SLOT + QUERY SYNTHESIS
# ════════════════════════════════════════════════════════════════════════════


def sample_slots(intent, intent_cfg, rng):
    """Sample one slot dict from intent's slot ranges."""
    slots = {"intent": intent}
    for field, values in intent_cfg["slot_ranges"].items():
        if values is None:
            continue  # computed below
        slots[field] = rng.choice(values)

    # Computed slots — payslip calculator needs these consistent
    if intent == "verify_epf":
        basic = slots["basic_salary"]
        expected_epf = round(basic * 0.12)
        # 60% correct, 40% wrong
        if rng.random() < 0.60:
            slots["epf_deducted"] = expected_epf
        else:
            slots["epf_deducted"] = expected_epf + rng.choice([-600, -300, 300, 600])
        slots["gross_salary"] = basic + rng.choice([3000, 5000, 7000, 10000])

    elif intent == "verify_esi":
        gross = slots["gross_salary"]
        if gross > 21000:
            # ESI shouldn't apply; sometimes employer wrongly deducts
            slots["esi_deducted"] = rng.choice([0, 0, 0, 150])
        else:
            expected_esi = round(gross * 0.0075)
            if rng.random() < 0.60:
                slots["esi_deducted"] = expected_esi
            else:
                slots["esi_deducted"] = expected_esi + rng.choice([-50, 50, 100])
        slots["basic_salary"] = max(gross - rng.choice([3000, 5000, 7000]), 8000)

    elif intent == "full_audit":
        basic = slots["basic_salary"]
        gross = basic + rng.choice([3000, 5000, 7000, 10000])
        slots["gross_salary"] = gross
        expected_epf = round(basic * 0.12)
        slots["epf_deducted"] = (
            expected_epf
            if rng.random() < 0.6
            else expected_epf + rng.choice([-500, 500])
        )
        if gross <= 21000:
            expected_esi = round(gross * 0.0075)
            slots["esi_deducted"] = (
                expected_esi
                if rng.random() < 0.6
                else expected_esi + rng.choice([-30, 50])
            )
        else:
            slots["esi_deducted"] = 0

    return slots


def build_query(intent_cfg, slots, rng):
    template_id = rng.randrange(len(intent_cfg["templates"]))
    template = intent_cfg["templates"][template_id]
    try:
        query = template.format(**{k: v for k, v in slots.items() if v is not None})
    except KeyError:
        return None, None
    return query, template_id


# ════════════════════════════════════════════════════════════════════════════
# TRACE SYNTHESIS
# ════════════════════════════════════════════════════════════════════════════


def _eval_op(op, slot_val, target_val):
    if slot_val is None:
        return None
    try:
        if op == "eq":
            return str(slot_val).lower() == str(target_val).lower()
        if op == "gte":
            return float(slot_val) >= float(target_val)
        if op == "lte":
            return float(slot_val) <= float(target_val)
        if op == "gt":
            return float(slot_val) > float(target_val)
        if op == "lt":
            return float(slot_val) < float(target_val)
        if op == "in":
            return slot_val in target_val
        if op == "not_null":
            return slot_val is not None
    except (ValueError, TypeError):
        return None
    return False


def synthesize_trace(intent_cfg, slots, passage_doc_ids):
    """Build a reasoner-shaped trace dict. Returns None if not a reasoning intent."""
    trace_conds = intent_cfg.get("trace_conditions", [])
    if not trace_conds or not passage_doc_ids:
        return None

    met, failed, warnings, unresolved = [], [], [], []
    primary_doc = passage_doc_ids[0]

    for cond in trace_conds:
        field = cond["field"]
        op = cond["operator"]
        value = cond["value"]
        mandatory = cond.get("mandatory", True)

        cross_doc = cond.get("cross_doc")
        if cross_doc and cross_doc in passage_doc_ids:
            doc_id = cross_doc
        else:
            doc_id = primary_doc

        slot_val = slots.get(field)
        result = _eval_op(op, slot_val, value)

        if result is None:
            unresolved.append(
                {"field": field, "operator": op, "value": value, "doc_id": doc_id}
            )
            continue

        record = {
            "field": field,
            "operator": op,
            "value": value,
            "doc_id": doc_id,
            "slot_value": slot_val,
        }

        if result:
            met.append(record)
        else:
            if mandatory:
                failed.append(record)
            else:
                warnings.append(record)

    if unresolved and not (met or failed):
        return {"decision": "ASK"}

    if failed:
        decision, eligible = "ANSWER", False
    else:
        decision, eligible = "ANSWER", True

    total = len(met) + len(failed) + len(unresolved)
    coverage = round(len(met) / total, 2) if total else 1.0

    return {
        "decision": decision,
        "eligible": eligible,
        "coverage": coverage,
        "met": met,
        "failed": failed,
        "warnings": warnings,
        "unresolved": unresolved,
    }


# ════════════════════════════════════════════════════════════════════════════
# PASSAGE SELECTION + PAYSLIP TOOL
# ════════════════════════════════════════════════════════════════════════════


def select_passages(kb_by_id, kb_by_subdomain, intent_cfg, rng, max_passages=3):
    domain = intent_cfg["domain"]
    candidates = []
    for sub in intent_cfg["subdomains"]:
        candidates.extend(kb_by_subdomain.get((domain, sub), []))

    if not candidates:
        return []

    n = min(rng.randint(1, 2) + 1, max_passages, len(candidates))
    picked = rng.sample(candidates, n)

    for cd in intent_cfg.get("cross_doc_ids", []):
        if cd in kb_by_id and cd not in picked:
            picked.append(cd)

    return [kb_by_id[d] for d in picked if d in kb_by_id]


def add_payslip_tool_passage(passages, slots):
    """Run parse_payslip, wrap result as TOOL_PAYSLIP_AUDIT passage."""
    import sys

    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from tools import parse_payslip, format_payslip_result

    result = parse_payslip(slots)
    formatted = format_payslip_result(result)

    tool_passage = {
        "doc_id": "TOOL_PAYSLIP_AUDIT",
        "title": "Payslip Audit Calculation",
        "content": formatted,
        "domain": "payslip",
        "subdomain": "tool_output",
        "effective_date": None,
    }
    return passages + [tool_passage]


# ════════════════════════════════════════════════════════════════════════════
# VALIDATION GATE
# ════════════════════════════════════════════════════════════════════════════

DOC_ID_REGEX = re.compile(r"\[([A-Z][A-Z0-9_]+)\]")

VERDICT_KEYWORDS = [
    "eligible",
    "not eligible",
    "ineligible",
    "correct",
    "incorrect",
    "matches",
    "mismatch",
    "applicable",
    "not applicable",
    "entitled",
    "not entitled",
    "conditional",
    "pending",
    "escalate",
    "under-deducted",
    "over-deducted",
    "exemption",
    "refund",
]

REFUSAL_PHRASES = [
    "i cannot help",
    "i cannot provide",
    "i don't know",
    "i do not know",
    "i'm not able",
    "i am not able",
    "insufficient information",
    "cannot answer",
    "unable to help",
    "no information available",
]


def validate_response(response, passage_doc_ids):
    r = response.strip()
    rl = r.lower()

    # Length (rough token proxy: 1 token ≈ 0.75 words)
    words = r.split()
    if len(words) < 60:
        return False, "too short"
    if len(words) > 450:
        return False, "too long"

    # Refusal
    for phrase in REFUSAL_PHRASES:
        if phrase in rl:
            return False, f"refusal: '{phrase}'"

    # Citations — at least one
    cited = set(DOC_ID_REGEX.findall(r))
    if not cited:
        return False, "no citations"

    # Fabrication — ALL cited must be in passages
    allowed = set(passage_doc_ids)
    fabricated = cited - allowed
    if fabricated:
        return False, f"fabricated cites: {sorted(fabricated)[:3]}"

    # Tool passage must be cited if present
    if "TOOL_PAYSLIP_AUDIT" in allowed and "TOOL_PAYSLIP_AUDIT" not in cited:
        return False, "tool passage not cited"

    # Verdict keyword
    if not any(kw in rl for kw in VERDICT_KEYWORDS):
        return False, "no verdict keyword"

    return True, "ok"


# ════════════════════════════════════════════════════════════════════════════
# TEACHER MODEL
# ════════════════════════════════════════════════════════════════════════════


def load_teacher():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"Loading {MODEL_ID} ...")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        attn_implementation="sdpa",
    )
    model.eval()
    device = next(model.parameters()).device
    print(f"Model loaded in {time.time()-t0:.1f}s on {device}")
    if torch.cuda.is_available():
        print(f"VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")
    return model, tokenizer, device


def batched_generate(model, tokenizer, device, chat_texts):
    import torch

    inputs = tokenizer(
        chat_texts,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=3072,
    ).to(device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=True,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            pad_token_id=tokenizer.eos_token_id,
        )

    responses = []
    for i in range(len(chat_texts)):
        input_len = inputs["input_ids"][i].shape[0]
        generated = outputs[i][input_len:]
        text = tokenizer.decode(generated, skip_special_tokens=True)
        responses.append(text.strip())
    return responses


# ════════════════════════════════════════════════════════════════════════════
# INCREMENTAL SAVE
# ════════════════════════════════════════════════════════════════════════════


def load_incremental():
    if not INCREMENTAL_PATH.exists():
        return []
    pairs = []
    with open(INCREMENTAL_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    pairs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return pairs


def append_incremental(example):
    INCREMENTAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INCREMENTAL_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(example, ensure_ascii=False) + "\n")


# ════════════════════════════════════════════════════════════════════════════
# MAIN GENERATION LOOP
# ════════════════════════════════════════════════════════════════════════════


def generate_for_domain(
    domain,
    target,
    intents_for_domain,
    kb_by_id,
    kb_by_subdomain,
    subdomain_counts,
    already_done_by_subdomain,
    model,
    tokenizer,
    device,
    log_f,
):
    rng = random.Random(hash(domain) & 0xFFFFFFFF)

    cap_cfg = SUBDOMAIN_CAPS[domain]

    # Per-subdomain caps based on available docs
    sub_caps = {}
    for intent in intents_for_domain:
        for sub in INTENT_CONFIGS[intent]["subdomains"]:
            n_docs = subdomain_counts.get((domain, sub), 0)
            sub_caps[sub] = min(cap_cfg["abs_cap"], n_docs * cap_cfg["per_doc"])

    print(f"\n[{domain}] Subdomain caps: {sub_caps}")

    count = sum(v for k, v in already_done_by_subdomain.items() if k[0] == domain)
    print(f"[{domain}] Already have {count} examples")
    if count >= target:
        print(f"[{domain}] Target already met, skipping")
        return

    sub_counts = {
        k[1]: v for k, v in already_done_by_subdomain.items() if k[0] == domain
    }
    max_attempts = (target - count) * MAX_ATTEMPTS_MULT
    attempts = 0
    rejects = 0

    t0 = time.time()

    while count < target and attempts < max_attempts:
        batch_examples = []
        batch_chats = []

        for _ in range(BATCH_SIZE):
            if count + len(batch_examples) >= target:
                break

            # Pick an intent with remaining subdomain budget
            available_intents = []
            for intent in intents_for_domain:
                cfg = INTENT_CONFIGS[intent]
                for sub in cfg["subdomains"]:
                    if sub_counts.get(sub, 0) < sub_caps.get(sub, 0):
                        available_intents.append(intent)
                        break
            if not available_intents:
                break
            intent = rng.choice(available_intents)
            cfg = INTENT_CONFIGS[intent]

            passages = select_passages(kb_by_id, kb_by_subdomain, cfg, rng)
            if not passages:
                attempts += 1
                continue

            slots = sample_slots(intent, cfg, rng)

            if cfg.get("use_payslip_tool"):
                passages = add_payslip_tool_passage(passages, slots)

            query, template_id = build_query(cfg, slots, rng)
            if query is None:
                attempts += 1
                continue

            passage_doc_ids = [p["doc_id"] for p in passages]
            reasoning = None
            if intent in REASONING_INTENTS:
                reasoning = synthesize_trace(cfg, slots, passage_doc_ids)
                if reasoning and reasoning.get("decision") == "ASK":
                    attempts += 1
                    continue

            user_msg = build_generator_input(
                query, cfg["domain"], passages, reasoning, slots
            )

            messages = [
                {"role": "system", "content": GENERATOR_PROMPT},
                {"role": "user", "content": user_msg},
            ]
            chat_text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )

            batch_examples.append(
                {
                    "intent": intent,
                    "cfg": cfg,
                    "slots": slots,
                    "query": query,
                    "template_id": template_id,
                    "passages": passages,
                    "passage_doc_ids": passage_doc_ids,
                    "reasoning": reasoning,
                    "messages": messages,
                }
            )
            batch_chats.append(chat_text)

        if not batch_chats:
            break

        attempts += len(batch_chats)

        try:
            responses = batched_generate(model, tokenizer, device, batch_chats)
        except Exception as e:
            err = str(e)[:200]
            log_f.write(f"[batch-error] {err}\n")
            log_f.flush()
            print(f"  [{domain}] Batch error: {err}")
            continue

        for ex, response in zip(batch_examples, responses):
            ok, reason = validate_response(response, ex["passage_doc_ids"])
            if not ok:
                rejects += 1
                log_f.write(f"[reject] {domain}/{ex['intent']}: {reason}\n")
                log_f.flush()
                continue

            ex["messages"].append({"role": "assistant", "content": response})

            primary_sub = INTENT_CONFIGS[ex["intent"]]["subdomains"][0]

            record = {
                "messages": ex["messages"],
                "metadata": {
                    "domain": ex["cfg"]["domain"],
                    "subdomain": primary_sub,
                    "intent": ex["intent"],
                    "template_id": ex["template_id"],
                    "cited_doc_ids": sorted(DOC_ID_REGEX.findall(response)),
                    "passage_doc_ids": ex["passage_doc_ids"],
                    "slot_combination": {
                        k: v for k, v in ex["slots"].items() if v is not None
                    },
                    "has_reasoning": ex["reasoning"] is not None,
                    "reasoning_decision": (
                        ex["reasoning"]["decision"] if ex["reasoning"] else None
                    ),
                    "reasoning_eligible": (
                        ex["reasoning"]["eligible"] if ex["reasoning"] else None
                    ),
                    "reasoning_coverage": (
                        ex["reasoning"]["coverage"] if ex["reasoning"] else None
                    ),
                },
            }
            append_incremental(record)
            count += 1
            sub_counts[primary_sub] = sub_counts.get(primary_sub, 0) + 1

            if count % 5 == 0:
                elapsed = time.time() - t0
                rate = count / max(attempts, 1) * 100
                eta = (
                    (target - count) / max(count / elapsed, 0.01) / 60
                    if count > 0
                    else 0
                )
                print(
                    f"  [{domain}] {count}/{target} | attempts={attempts} pass={rate:.0f}% ETA={eta:.0f}min"
                )

        # Circuit breaker
        if attempts >= REJECT_WARMUP:
            reject_rate = rejects / max(attempts, 1)
            if reject_rate > MAX_REJECT_RATE:
                print(
                    f"  [{domain}] REJECT RATE {reject_rate:.0%} > {MAX_REJECT_RATE:.0%} after {attempts} attempts — HALTING"
                )
                log_f.write(
                    f"[circuit-breaker] {domain}: reject_rate={reject_rate:.2%}\n"
                )
                log_f.flush()
                break

    elapsed = (time.time() - t0) / 60
    pass_rate = count / max(attempts, 1) * 100
    print(
        f"[{domain}] Done: {count} saved | {attempts} attempts | {pass_rate:.0f}% pass | {elapsed:.1f}min"
    )


# ════════════════════════════════════════════════════════════════════════════
# TRAIN / VAL SPLIT + STATS
# ════════════════════════════════════════════════════════════════════════════


def split_and_stats(examples):
    by_intent = defaultdict(list)
    for e in examples:
        by_intent[e["metadata"]["intent"]].append(e)

    train, val = [], []
    for intent, exs in by_intent.items():
        random.Random(42).shuffle(exs)
        n_val = max(1, int(len(exs) * VAL_FRACTION)) if len(exs) >= 10 else 0
        val.extend(exs[:n_val])
        train.extend(exs[n_val:])

    random.Random(42).shuffle(train)
    random.Random(42).shuffle(val)

    def write(path, data):
        with open(path, "w", encoding="utf-8") as f:
            for e in data:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    write(TRAIN_OUT, train)
    write(VAL_OUT, val)

    stats = {
        "total": len(examples),
        "train": len(train),
        "val": len(val),
        "by_domain": dict(Counter(e["metadata"]["domain"] for e in examples)),
        "by_intent": dict(Counter(e["metadata"]["intent"] for e in examples)),
        "by_subdomain": dict(Counter(e["metadata"]["subdomain"] for e in examples)),
        "reasoning_yes": sum(1 for e in examples if e["metadata"]["has_reasoning"]),
        "reasoning_eligible_true": sum(
            1 for e in examples if e["metadata"].get("reasoning_eligible") is True
        ),
        "reasoning_eligible_false": sum(
            1 for e in examples if e["metadata"].get("reasoning_eligible") is False
        ),
    }
    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    print(f"\n✓ Train: {len(train)} → {TRAIN_OUT}")
    print(f"✓ Val:   {len(val)}   → {VAL_OUT}")
    print(f"✓ Stats: {STATS_PATH}")
    print(f"\n{json.dumps(stats, indent=2)}")


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════


def main():
    print("=" * 70)
    print("ShramikSaathi — SFT Dataset Generator (Stage 1.1)")
    print("=" * 70)

    kb_by_id, kb_by_subdomain, subdomain_counts = load_kb()

    existing = load_incremental()
    already_by_subdomain = Counter(
        (e["metadata"]["domain"], e["metadata"]["subdomain"]) for e in existing
    )
    print(f"\n[Resume] {len(existing)} existing examples in {INCREMENTAL_PATH.name}")
    for k, v in sorted(already_by_subdomain.items()):
        print(f"         {k[0]}/{k[1]}: {v}")

    # Group intents by domain
    intents_by_domain = defaultdict(list)
    for intent, cfg in INTENT_CONFIGS.items():
        intents_by_domain[cfg["domain"]].append(intent)

    model, tokenizer, device = load_teacher()

    log_f = open(LOG_PATH, "a", encoding="utf-8")
    log_f.write(f"\n--- Run started {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")

    try:
        for domain, target in DOMAIN_TARGETS.items():
            generate_for_domain(
                domain,
                target,
                intents_by_domain[domain],
                kb_by_id,
                kb_by_subdomain,
                subdomain_counts,
                already_by_subdomain,
                model,
                tokenizer,
                device,
                log_f,
            )
            # Refresh counter for next domain (in case of cross-domain tracking)
            current = load_incremental()
            already_by_subdomain = Counter(
                (e["metadata"]["domain"], e["metadata"]["subdomain"]) for e in current
            )
    finally:
        log_f.close()

    # Final split
    all_examples = load_incremental()
    print(f"\n{'=' * 70}")
    print(f"FINAL: {len(all_examples)} validated examples")
    print(f"{'=' * 70}")
    split_and_stats(all_examples)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Incremental saves preserved. Re-run to resume.")
    except Exception as e:
        print(f"\n\n[FATAL] {type(e).__name__}: {e}")
        traceback.print_exc()
