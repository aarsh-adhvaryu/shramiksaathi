"""
ShramikSaathi — DPO Dataset Generator (Lightning AI edition)

Generates 1000+ DPO preference pairs using LOCAL LLaMA 3.1 8B inference.
No external APIs. No rate limits. No hangs.

Strategy:
  1. Load KB (311 docs across 4 domains)
  2. Generate Phase 1: ~50 template-based pairs (deterministic, fast, high-quality)
  3. Generate Phase 2: ~1000 LLM-based pairs via batched inference
     - Batch size 4 (A10G 24GB has plenty of headroom for 8B)
     - Strict validation on every pair
     - Incremental save every 10 validated pairs
     - Resumable from checkpoint
  4. Combine into data/dpo_dataset_final.jsonl

Expected runtime on A10G 24GB:
  - Model load: ~45s
  - Template generation: ~5s
  - LLM generation: ~2-2.5 hours for 1000 validated pairs
  - Total: ~2.5 hours

Run from shramiksaathi/ root:
    python src/generate_dataset.py

Resumable: re-run to continue from last saved checkpoint.
Output: data/dpo_dataset_final.jsonl
"""

import os
import sys
import re
import json
import time
import random
import traceback
from pathlib import Path
from collections import Counter, defaultdict

random.seed(42)

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
KB_PATH = PROJECT_ROOT / "data" / "kb.jsonl"
OUTPUT_PATH = PROJECT_ROOT / "data" / "dpo_dataset_final.jsonl"
INCREMENTAL_PATH = PROJECT_ROOT / "data" / ".dataset_incremental.jsonl"
LOG_PATH = PROJECT_ROOT / "data" / "dataset_generation.log"

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"
BATCH_SIZE = 4
TARGET_PER_DOMAIN = 250  # => ~1000 total LLM pairs
MAX_NEW_TOKENS = 800
MAX_ATTEMPTS_MULTIPLIER = 3  # if target=250, max attempts = 750

# ══════════════════════════════════════════════════════════════════════════════
# KB LOADING
# ══════════════════════════════════════════════════════════════════════════════

def load_kb():
    """Load KB and index by doc_id. Filter substantive docs."""
    kb_by_id = {}
    kb_by_domain = defaultdict(list)
    with open(KB_PATH, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            if len(doc.get('content', '')) < 50:
                continue
            doc_id = doc.get('doc_id', '')
            kb_by_id[doc_id] = doc
            kb_by_domain[doc.get('domain', 'unknown')].append(doc_id)
    print(f"[KB] Loaded {len(kb_by_id)} docs")
    for d, ids in sorted(kb_by_domain.items()):
        print(f"     {d}: {len(ids)} docs")
    return kb_by_id, kb_by_domain


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

DOC_ID_REGEX = re.compile(r'\[([A-Za-z][A-Za-z0-9_]+)\]')


def validate_pair(pair, valid_doc_ids_in_passages):
    """Return (ok: bool, reason: str)."""
    chosen = pair.get('chosen', '')
    rejected = pair.get('rejected', '')

    if len(chosen) < 80 or len(rejected) < 80:
        return False, "too short"
    if len(chosen) > 4000 or len(rejected) > 4000:
        return False, "too long"

    ratio = len(chosen) / max(len(rejected), 1)
    if not (0.75 <= ratio <= 1.35):
        return False, f"length ratio {ratio:.2f} out of bounds"

    chosen_cites = set(DOC_ID_REGEX.findall(chosen))
    chosen_invalid = chosen_cites - valid_doc_ids_in_passages
    if chosen_invalid:
        return False, f"chosen has invalid cites: {sorted(chosen_invalid)[:3]}"

    if chosen == rejected:
        return False, "chosen == rejected"

    if not chosen_cites:
        return False, "chosen has no citations"

    rejected_cites = set(DOC_ID_REGEX.findall(rejected))
    if not rejected_cites and chosen_cites:
        return False, "rejected has no brackets (surface feature)"

    if len(chosen) > 1.30 * len(rejected):
        return False, f"chosen much longer ({len(chosen)}/{len(rejected)})"

    return True, "ok"


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_TEMPLATE = """You are ShramikSaathi, an Indian worker rights support copilot.

Domain: {domain}
User slots: {slots_json}

Retrieved passages:
{passages}

User query: {query}

Produce a clear, cited, structured answer."""


def build_prompt(domain, slots, passages, query):
    return PROMPT_TEMPLATE.format(
        domain=domain,
        slots_json=json.dumps({k: v for k, v in slots.items() if v is not None}),
        passages=passages,
        query=query,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1: TEMPLATE-BASED GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def gen_templates(kb):
    """Deterministic template pairs — real doc_ids, failure modes baked in."""
    pairs = []

    # ── PF full withdrawal ──────────────────────────────────────────────
    doc = kb.get('EPF_ACT_S68_S69')
    tds = kb.get('CIRC_2024_TDS')
    if doc and tds:
        passages = f"[EPF_ACT_S68_S69] {doc['content'][:600]}\n[CIRC_2024_TDS] {tds['content'][:400]}"
        valid_ids = {'EPF_ACT_S68_S69', 'CIRC_2024_TDS'}
        for months, years in [(3, 6), (4, 7), (6, 10), (5, 8)]:
            slots = {"intent": "full_withdrawal", "employment_status": "unemployed",
                     "months_unemployed": months, "service_years": years,
                     "uan_status": "active", "kyc_status": "complete"}
            query = f"Left my job {months} months ago. Worked {years} years. UAN active, KYC done. Can I withdraw full PF?"
            chosen = f"""Yes, you are eligible for full PF withdrawal.

Condition check [EPF_ACT_S68_S69]:
- Unemployment: {months} months >= 2 months required
- UAN: active
- KYC: complete

Since service is {years} years (>= 5 years), no TDS applies [CIRC_2024_TDS].

How to apply [EPF_ACT_S68_S69]:
1. Login unifiedportal-mem.epfindia.gov.in
2. Online Services -> Claim -> Form 19
3. Verify bank details match KYC
4. Submit. Processing: 20 working days."""
            rejected = f"""Yes, withdraw PF [EPF_ACT_S68_S69].

Condition [EPF_ACT_S68_S69_unemployment]:
- {months} months [EPF_ACT_S68_S69_2mo]
- UAN active [EPF_ACT_S68_S69_uan]
- KYC [EPF_ACT_S68_S69_kyc]

TDS: {years} years [CIRC_2024_TDS_5yr].

Apply [EPF_ACT_S68_S69_form19]:
1. Login portal
2. Form 19
3. Bank details
4. Submit, 20 days [EPF_ACT_S68_S69_timeline]."""
            pairs.append({
                "prompt": build_prompt("pf", slots, passages, query),
                "chosen": chosen, "rejected": rejected,
                "domain": "pf", "intent": "full_withdrawal",
                "dimension": "citation_reuse",
                "_valid_ids": valid_ids,
            })

    # ── Gratuity ────────────────────────────────────────────────────────
    grat = kb.get('GRATUITY_ACT_S4_ELIG')
    if grat:
        passages = f"[GRATUITY_ACT_S4_ELIG] {grat['content'][:600]}"
        valid_ids = {'GRATUITY_ACT_S4_ELIG'}
        for years, salary in [(6, 30000), (8, 50000), (10, 45000), (7, 35000)]:
            slots = {"intent": "gratuity", "employment_years": years,
                     "termination_reason": "resignation", "last_drawn_salary": salary}
            amount = int((salary * 15 * years) / 26)
            query = f"Resigned after {years} years. Salary Rs.{salary}. Gratuity eligible?"
            chosen = f"""Yes, eligible for gratuity.

Eligibility [GRATUITY_ACT_S4_ELIG]:
- Service: {years} years > 5 years minimum
- Resignation does not disqualify (misconduct termination would)

Calculation [GRATUITY_ACT_S4_ELIG]:
(Rs.{salary} x 15 x {years}) / 26 = Rs.{amount:,}

Payment rules [GRATUITY_ACT_S4_ELIG]:
- Employer pays within 30 days of last working day
- Tax-free up to Rs.20 lakh
- If delayed, file with Controlling Authority"""
            rejected = f"""Yes eligible [GRATUITY_ACT_S4_ELIG_yes].

Eligibility [GRATUITY_ACT_S4_ELIG_5yr]:
- {years} years [GRATUITY_ACT_S4_ELIG_service]
- Resignation OK [GRATUITY_ACT_S4_ELIG_resign]

Calc [GRATUITY_ACT_S4_ELIG_formula]:
(Rs.{salary} x 15 x {years}) / 26 = Rs.{amount:,}

Pay [GRATUITY_ACT_S4_ELIG_pay]:
- 30 days [GRATUITY_ACT_S4_ELIG_30d]
- Tax-free 20L [GRATUITY_ACT_S4_ELIG_tax]
- Delay remedy [GRATUITY_ACT_S4_ELIG_remedy]"""
            pairs.append({
                "prompt": build_prompt("labour", slots, passages, query),
                "chosen": chosen, "rejected": rejected,
                "domain": "labour", "intent": "gratuity",
                "dimension": "citation_reuse",
                "_valid_ids": valid_ids,
            })

    # ── Payslip EPF verify ──────────────────────────────────────────────
    epf_doc = kb.get('EPF_ACT_S6_CONTRIB')
    tool_content = "EPF expected = 12% of basic. ESI if gross <= 21000."
    passages = f"[TOOL_PAYSLIP_AUDIT] {tool_content}"
    valid_ids = {'TOOL_PAYSLIP_AUDIT'}
    if epf_doc:
        passages += f"\n[EPF_ACT_S6_CONTRIB] {epf_doc['content'][:300]}"
        valid_ids.add('EPF_ACT_S6_CONTRIB')

    for basic, actual, expected in [(15000, 1800, 1800), (20000, 2400, 2400),
                                     (18000, 1800, 2160), (25000, 1800, 3000)]:
        correct = actual == expected
        slots = {"intent": "verify_epf", "basic_salary": basic, "epf_deducted": actual}
        query = f"Basic {basic}, EPF {actual}. Correct?"
        if correct:
            chosen = f"""Yes, EPF is correct.

Calculation [TOOL_PAYSLIP_AUDIT]:
- Expected: 12% of Rs.{basic} = Rs.{expected}
- Actual: Rs.{actual}
- Match: YES

Employer following statutory rate [EPF_ACT_S6_CONTRIB]. No action needed."""
            rejected = f"""EPF correct [TOOL_PAYSLIP_AUDIT_ok].

Calc [TOOL_PAYSLIP_AUDIT_calc]:
- Expected Rs.{expected} [EPF_ACT_S6_CONTRIB_12pct]
- Actual Rs.{actual} [TOOL_PAYSLIP_AUDIT_actual]
- Match [TOOL_PAYSLIP_AUDIT_match]

Compliant [EPF_ACT_S6_CONTRIB_rule]."""
        else:
            shortfall = expected - actual
            chosen = f"""No, EPF is INCORRECT - shortfall Rs.{shortfall}/month.

Calculation [TOOL_PAYSLIP_AUDIT]:
- Expected: 12% of Rs.{basic} = Rs.{expected}
- Actual: Rs.{actual}
- Shortfall: Rs.{shortfall}/month

Statute [EPF_ACT_S6_CONTRIB] requires 12% of basic.

Action:
1. Written query to HR
2. If unresolved, file EPFIGMS grievance"""
            rejected = f"""EPF INCORRECT [TOOL_PAYSLIP_AUDIT_wrong].

Calc [TOOL_PAYSLIP_AUDIT_calc]:
- Expected [EPF_ACT_S6_CONTRIB_12pct]
- Actual [TOOL_PAYSLIP_AUDIT_actual]
- Gap [TOOL_PAYSLIP_AUDIT_gap]

Statute [EPF_ACT_S6_CONTRIB_rule]: 12% [EPF_ACT_S6_CONTRIB_basic].

Action [TOOL_PAYSLIP_AUDIT_actions]:
1. HR query [TOOL_PAYSLIP_AUDIT_hr]
2. EPFIGMS [TOOL_PAYSLIP_AUDIT_grievance]"""

        pairs.append({
            "prompt": build_prompt("payslip", slots, passages, query),
            "chosen": chosen, "rejected": rejected,
            "domain": "payslip", "intent": "verify_epf",
            "dimension": "citation_reuse",
            "_valid_ids": valid_ids,
        })

    # ── Tax 80C ─────────────────────────────────────────────────────────
    doc = kb.get('ITA_SECTION_80C')
    if doc:
        passages = f"[ITA_SECTION_80C] {doc['content'][:500]}"
        valid_ids = {'ITA_SECTION_80C'}
        for amounts, total in [({"ppf": 150000}, 150000),
                               ({"ppf": 50000, "elss": 60000}, 110000),
                               ({"ppf": 150000, "loan": 80000}, 230000)]:
            slots = {**amounts, "intent": "deductions_80c", "tax_regime": "old_regime"}
            breakdown = ", ".join(f"{k} {v:,}" for k, v in amounts.items())
            query = f"Old regime. 80C: {breakdown}. Claim?"
            if total <= 150000:
                chosen = f"""Claim full Rs.{total:,} under 80C.

Analysis [ITA_SECTION_80C]:
- Total eligible: Rs.{total:,}
- Cap: Rs.1,50,000
- Under cap - fully deductible

Tax saved at 30% slab: Rs.{int(total * 0.312):,} (with cess)

Room to invest Rs.{150000 - total:,} more [ITA_SECTION_80C].

Important [ITA_SECTION_80C]: 80C only under old regime."""
                rejected = f"""Claim Rs.{total:,} [ITA_SECTION_80C_claim].

Analysis [ITA_SECTION_80C_total]:
- Total [ITA_SECTION_80C_sum]
- Cap [ITA_SECTION_80C_limit]
- Under cap [ITA_SECTION_80C_under]

Saved: Rs.{int(total * 0.312):,} [ITA_SECTION_80C_savings]

Room [ITA_SECTION_80C_headroom].

Note [ITA_SECTION_80C_regime]: Old only [ITA_SECTION_80C_old]."""
            else:
                chosen = f"""Max claim Rs.1,50,000 (investments Rs.{total:,}).

Analysis [ITA_SECTION_80C]:
- Total: Rs.{total:,}
- Cap: Rs.1,50,000 hard limit
- Excess: Rs.{total - 150000:,} not deductible under 80C

Tax saved at 30%: Rs.{int(150000 * 0.312):,}

Excess still earns returns [ITA_SECTION_80C] but no tax benefit above cap.

Important [ITA_SECTION_80C]: Only under old regime."""
                rejected = f"""Max Rs.1.5L [ITA_SECTION_80C_capped].

Analysis [ITA_SECTION_80C_sum]:
- Total [ITA_SECTION_80C_agg]
- Cap [ITA_SECTION_80C_cap]
- Excess [ITA_SECTION_80C_over]

Saved [ITA_SECTION_80C_savings]
Excess returns [ITA_SECTION_80C_returns]

Note [ITA_SECTION_80C_regime]: Old only [ITA_SECTION_80C_old]."""
            pairs.append({
                "prompt": build_prompt("tax", slots, passages, query),
                "chosen": chosen, "rejected": rejected,
                "domain": "tax", "intent": "deductions_80c",
                "dimension": "citation_reuse",
                "_valid_ids": valid_ids,
            })

    return pairs


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2: LLM-BASED GENERATION (BATCHED)
# ══════════════════════════════════════════════════════════════════════════════

LLM_SYSTEM_PROMPT = """You generate DPO training pairs for an Indian worker rights copilot.

Output format: JSON object with "chosen" and "rejected" keys.

chosen: high-quality response with correct citations (use ONLY doc_ids from RETRIEVED PASSAGES).
rejected: same structure and similar length, but demonstrates the specified FAILURE MODE.

FAILURE MODES:
- CITATION_FABRICATION: rejected invents doc_id suffix variants like [DOC_ID_extra] NOT in passages
- WRONG_ELIGIBILITY: rejected flips eligibility verdict
- WEAK_ESCALATION: rejected suggests weak remedies ('talk to HR') instead of proper grievance
- JARGON_TONE: rejected uses heavy legal jargon
- MISSED_WARNING: rejected omits critical warnings (TDS, deadlines)
- WRONG_TOOL: rejected computes manually without citing tool

STRICT RULES:
1. chosen cites ONLY doc_ids from RETRIEVED PASSAGES
2. rejected length 85-115% of chosen
3. Both 400-1200 characters
4. Output JSON ONLY, no preamble"""


def build_llm_prompt(dimension, domain, query, passages_block, valid_doc_ids):
    dim_desc = {
        "CITATION_FABRICATION": "In rejected, invent 2-4 doc_id suffix variants like [DOC_ID_extra] NOT in passages.",
        "WRONG_ELIGIBILITY": "In rejected, flip the eligibility verdict.",
        "WEAK_ESCALATION": "In rejected, replace grievance steps with weak advice.",
        "JARGON_TONE": "In rejected, use heavy legal jargon.",
        "MISSED_WARNING": "In rejected, omit a critical warning.",
        "WRONG_TOOL": "In rejected, compute manually instead of citing TOOL_PAYSLIP_AUDIT.",
    }
    return f"""Failure mode: {dimension}
{dim_desc[dimension]}

USER QUERY: {query}
DOMAIN: {domain}

RETRIEVED PASSAGES:
{passages_block}

Valid doc_ids: {sorted(valid_doc_ids)}

Return JSON only: {{"chosen": "...", "rejected": "..."}}"""


def parse_llm_output(raw_text):
    """Extract JSON from LLM output, handling markdown fences."""
    raw = raw_text.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    # Find the first { and matching }
    start = raw.find('{')
    if start < 0:
        return None
    # Find matching closing brace
    depth = 0
    end = -1
    for i, c in enumerate(raw[start:], start):
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        return None
    try:
        parsed = json.loads(raw[start:end])
        if 'chosen' in parsed and 'rejected' in parsed:
            return parsed
    except json.JSONDecodeError:
        pass
    return None


# ── Incremental save ──────────────────────────────────────────────────────────

def load_incremental():
    if not INCREMENTAL_PATH.exists():
        return []
    pairs = []
    with open(INCREMENTAL_PATH, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    pairs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return pairs


def append_incremental(pair):
    with open(INCREMENTAL_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(pair, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def count_by_domain(pairs):
    return Counter(p.get('domain', '?') for p in pairs)


# ── Main LLM generation loop ──────────────────────────────────────────────────

def generate_llm_pairs(kb, model, tokenizer, device, log_f):
    domain_seeds = {
        "pf": ["EPF_ACT_S68_S69", "CIRC_2024_TDS", "EPF_ACT_S6_CONTRIB",
               "EMPLOYER_DEFAULT_REMEDIES", "KYC_REJECTION_REASONS_RESOLUTION",
               "FORM_13_INSTRUCTIONS", "EPS_1995_SCHEME", "EPF_ACT_S14B",
               "CIRC_KYC_GUIDELINES", "TRANSFER_JOB_CHANGE_STEP_BY_STEP"],
        "payslip": ["ESI_WAGE_LIMIT", "EPF_ACT_S6_CONTRIB", "BONUS_ACT_1965",
                    "MIN_WAGE_DELHI_2024", "MIN_WAGE_MAHARASHTRA_2024",
                    "MIN_WAGE_KARNATAKA_2024", "PROF_TAX_MAHARASHTRA",
                    "PROF_TAX_KARNATAKA", "CODE_ON_WAGES_2019_BASICS"],
        "labour": ["GRATUITY_ACT_S4_ELIG", "MATERNITY_BENEFIT_ACT_2017",
                   "FACTORIES_ACT_S59_OVERTIME", "ID_ACT_S25F_RETRENCHMENT",
                   "STANDING_ORDERS_ACT_NOTICE_PERIOD", "GRATUITY_COURT_RULING_4Y8M",
                   "WRONGFUL_TERMINATION_REMEDIES", "POSH_ACT_2013_ICC"],
        "tax": ["ITA_SECTION_80C", "ITA_SECTION_10_13A", "ITA_SECTION_192A_TDS_PF",
                "ITA_OLD_REGIME_SLABS", "FINANCE_ACT_2023_NEW_REGIME",
                "FORM_16_OVERVIEW", "ITR_REFUND_DELAY_GRIEVANCE",
                "ITA_SECTION_80D_MEDICAL"],
    }

    domain_queries = {
        "pf": [
            ("full_withdrawal", "Can I withdraw full PF after leaving job?"),
            ("full_withdrawal", "Unemployed 5 months, claim full PF?"),
            ("tds_query", "Will TDS be cut on my PF withdrawal?"),
            ("tds_query", "PF withdrawal 60000, service 4 years, no PAN"),
            ("kyc_issue", "KYC got rejected, name mismatch"),
            ("kyc_issue", "Aadhaar seeding failed on UAN portal"),
            ("transfer", "How to transfer PF from old employer to new?"),
            ("employer_complaint", "Employer deducts PF but not depositing"),
            ("employer_complaint", "PF not in passbook for 3 months"),
            ("partial_withdrawal", "Partial PF for medical emergency?"),
            ("partial_withdrawal", "Need PF for home loan down payment?"),
        ],
        "payslip": [
            ("verify_epf", "Basic 22000, EPF 1800. Right?"),
            ("verify_epf", "Basic 30000, EPF 2500 deducted. Correct?"),
            ("verify_esi", "Gross 18000, ESI 135. Correct?"),
            ("verify_esi", "Gross 23000 but ESI still deducted"),
            ("check_minimum_wage", "Earning 14000 Karnataka, above minimum?"),
            ("check_minimum_wage", "Paid 10000 Mumbai. Legal?"),
            ("full_audit", "Basic 20k, gross 30k, EPF 2400, ESI 0, PT 200"),
            ("check_bonus", "No statutory bonus paid. Basic 18k"),
            ("check_deductions", "What is PT for Kerala?"),
        ],
        "labour": [
            ("gratuity", "Resigned after 7 years, salary 40000"),
            ("gratuity", "Fired after 6 years for performance"),
            ("gratuity", "Company shut down after 5.5 years"),
            ("wrongful_termination", "Fired verbally after 2 years in factory"),
            ("wrongful_termination", "Termination email, no notice paid"),
            ("maternity_benefit", "6 months pregnant, 1.5 years employed"),
            ("maternity_benefit", "Company has 15 employees, maternity rules?"),
            ("overtime_pay", "11 hours daily in factory. OT rules?"),
            ("notice_period", "3-month notice, want to leave in 1"),
            ("notice_period", "Employer refusing relieving letter"),
        ],
        "tax": [
            ("tds_on_salary", "12 lakh old regime, 1.5L in 80C"),
            ("tds_on_salary", "8 lakh new regime. Tax?"),
            ("tds_on_pf", "PF withdrawal 1.2L, 4 years service. TDS?"),
            ("hra_exemption", "Basic 40k, HRA 20k, rent 25k Delhi"),
            ("hra_exemption", "Bangalore basic 50k, HRA 25k, rent 30k"),
            ("deductions_80c", "ELSS 80k, home loan 50k, LIC 30k"),
            ("deductions_80c", "New regime - can I claim 80C?"),
            ("form16", "No Form 16 yet, deadline passed"),
            ("refund_status", "Filed ITR 3 months ago, no refund"),
        ],
    }

    dimensions = ["CITATION_FABRICATION", "WRONG_ELIGIBILITY", "WEAK_ESCALATION",
                  "JARGON_TONE", "MISSED_WARNING", "WRONG_TOOL"]

    # Resume from checkpoint
    existing = load_incremental()
    existing_counts = count_by_domain(existing)
    total_existing = sum(existing_counts.values())
    if total_existing > 0:
        print(f"\n[Resume] Found {total_existing} previous pairs: {dict(existing_counts)}")

    import torch

    for domain in ["pf", "payslip", "labour", "tax"]:
        queries = domain_queries[domain]
        seeds = domain_seeds[domain]
        already = existing_counts.get(domain, 0)
        target = TARGET_PER_DOMAIN
        remaining = max(0, target - already)

        if remaining == 0:
            print(f"\n[{domain}] Already have {already} pairs, skipping")
            continue

        print(f"\n[{domain}] Have {already}, generating {remaining} more...")
        count = already
        attempts = 0
        max_attempts = remaining * MAX_ATTEMPTS_MULTIPLIER
        t_domain_start = time.time()

        while count < target and attempts < max_attempts:
            # Build a batch of prompts
            batch_prompts = []
            batch_meta = []
            for _ in range(BATCH_SIZE):
                if count + len(batch_prompts) >= target:
                    break
                intent, query = random.choice(queries)
                seed_ids = random.sample(seeds, min(3, len(seeds)))
                dimension = random.choice(dimensions)

                valid_ids = set()
                passages_list = []
                for sid in seed_ids:
                    d = kb.get(sid)
                    if d:
                        valid_ids.add(sid)
                        passages_list.append(f"[{sid}] {d['content'][:400]}")
                if not passages_list:
                    continue
                passages_block = "\n".join(passages_list)

                user_prompt = build_llm_prompt(dimension, domain, query, passages_block, valid_ids)
                messages = [
                    {"role": "system", "content": LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
                chat_text = tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
                batch_prompts.append(chat_text)
                batch_meta.append({
                    "dimension": dimension, "domain": domain, "intent": intent,
                    "query": query, "passages_block": passages_block,
                    "valid_ids": valid_ids,
                })

            if not batch_prompts:
                attempts += 1
                continue

            attempts += len(batch_prompts)

            # Batched generation
            try:
                inputs = tokenizer(batch_prompts, return_tensors="pt", padding=True,
                                    truncation=True, max_length=2048).to(device)

                with torch.no_grad():
                    outputs = model.generate(
                        **inputs,
                        max_new_tokens=MAX_NEW_TOKENS,
                        do_sample=True,
                        temperature=0.7,
                        top_p=0.9,
                        pad_token_id=tokenizer.eos_token_id,
                    )

                # Decode only the generated portion for each sample
                for i, meta in enumerate(batch_meta):
                    n_in = inputs['input_ids'][i].shape[0]
                    # Trim padding tokens from input
                    input_len = (inputs['input_ids'][i] != tokenizer.pad_token_id).sum().item()
                    generated_tokens = outputs[i][n_in:]
                    generated_text = tokenizer.decode(generated_tokens, skip_special_tokens=True)

                    parsed = parse_llm_output(generated_text)
                    if not parsed:
                        log_f.write(f"[reject-parse] {meta['domain']} {meta['dimension']}: could not parse JSON\n")
                        log_f.flush()
                        continue

                    pair = {
                        "prompt": build_prompt(meta['domain'],
                                              {"intent": meta['intent']},
                                              meta['passages_block'],
                                              meta['query']),
                        "chosen": parsed['chosen'],
                        "rejected": parsed['rejected'],
                        "domain": meta['domain'],
                        "intent": meta['intent'],
                        "dimension": meta['dimension'].lower(),
                        "_valid_ids": list(meta['valid_ids']),
                    }

                    ok, reason = validate_pair(pair, meta['valid_ids'])
                    if ok:
                        pair_to_save = {k: v for k, v in pair.items() if not k.startswith('_')}
                        append_incremental(pair_to_save)
                        count += 1
                        if count % 5 == 0:
                            elapsed = time.time() - t_domain_start
                            rate = (count - already) / max(attempts, 1) * 100
                            eta = ((target - count) / max((count - already) / elapsed, 0.01)) if count > already else 0
                            print(f"  [{domain}] {count}/{target} saved ({attempts} attempts, {rate:.0f}% pass, ETA {eta/60:.0f}min)")
                    else:
                        log_f.write(f"[reject] {meta['domain']} {meta['dimension']}: {reason}\n")
                        log_f.flush()

            except Exception as e:
                err = str(e)[:200]
                log_f.write(f"[batch-error] {err}\n")
                log_f.flush()
                print(f"  [{domain}] Batch error: {err}")
                continue

        elapsed = (time.time() - t_domain_start) / 60
        rate = (count - already) / max(attempts, 1) * 100
        print(f"  [{domain}] Done: {count} pairs ({attempts} attempts, {rate:.0f}% pass, {elapsed:.1f}min)")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("ShramikSaathi — DPO Dataset Generator (Lightning, LLaMA 3.1 8B local)")
    print("=" * 70)

    # Load KB
    kb, kb_by_domain = load_kb()

    log_f = open(LOG_PATH, 'a', encoding='utf-8')

    # ── Phase 1: Templates ──────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("PHASE 1: Template generation (deterministic)")
    print("=" * 70)
    template_pairs = gen_templates(kb)
    validated_templates = []
    rejected = Counter()
    for p in template_pairs:
        ok, reason = validate_pair(p, set(p['_valid_ids']))
        if ok:
            validated_templates.append({k: v for k, v in p.items() if not k.startswith('_')})
        else:
            rejected[reason] += 1
    print(f"[Phase 1] {len(template_pairs)} generated, {len(validated_templates)} passed")
    if rejected:
        print(f"  Rejected: {dict(rejected)}")

    # ── Load model ─────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"Loading {MODEL_ID}...")
    print("=" * 70)

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"  # required for batched generation

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        attn_implementation="sdpa",
    )
    model.eval()
    device = next(model.parameters()).device
    print(f"Model loaded in {time.time() - t0:.1f}s on {device}")
    if torch.cuda.is_available():
        print(f"VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")

    # ── Phase 2: LLM generation ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"PHASE 2: LLM batched generation (target {TARGET_PER_DOMAIN}/domain = {TARGET_PER_DOMAIN*4} total)")
    print("=" * 70)
    print(f"Incremental save: {INCREMENTAL_PATH}")
    print(f"Log: {LOG_PATH}")

    t_llm_start = time.time()
    generate_llm_pairs(kb, model, tokenizer, device, log_f)
    llm_elapsed = (time.time() - t_llm_start) / 60
    print(f"\n[Phase 2] Total time: {llm_elapsed:.1f} minutes")

    # ── Combine ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("COMBINING datasets")
    print("=" * 70)

    llm_pairs = load_incremental()
    print(f"LLM pairs (incremental): {len(llm_pairs)}")
    print(f"Template pairs: {len(validated_templates)}")

    combined = validated_templates + llm_pairs
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        for p in combined:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"\n✓ FINAL: {len(combined)} pairs -> {OUTPUT_PATH}")
    print(f"  By domain: {dict(Counter(p.get('domain', '?') for p in combined))}")
    print(f"  By dimension: {dict(Counter(p.get('dimension', '?') for p in combined))}")

    log_f.close()
    print("\n✓ Done. Next step: train LoRA + DPO on this dataset.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Incremental saves preserved.")
        print(f"Re-run the script to resume.")
    except Exception as e:
        print(f"\n\n[FATAL] {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)
