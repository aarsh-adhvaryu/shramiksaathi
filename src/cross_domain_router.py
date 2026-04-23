"""
Cross-domain Router — classifies user query into pf | payslip | labour | tax
LLM version (zero-shot) + keyword baseline
"""

import os
import re
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Domain keyword lists (baseline) ───────────────────────────────────────────

DOMAIN_KEYWORDS = {
    "pf": [
        "pf",
        "epf",
        "epfo",
        "provident fund",
        "uan",
        "uan number",
        "withdrawal",
        "withdraw",
        "nikalna",
        "nikal",
        "form 19",
        "form 31",
        "form 10c",
        "form 13",
        "form 15g",
        "form 15h",
        "pf transfer",
        "pf balance",
        "pf claim",
        "pf settlement",
        "eps",
        "pension scheme",
        "employer deposit",
        "passbook",
        "epfigms",
        "grievance",
        "umang",
        "unified portal",
        "kyc",
        "aadhaar seed",
        "aadhar",
        "pf account",
        "nomination",
        "pf nomination",
    ],
    "payslip": [
        "payslip",
        "salary slip",
        "pay slip",
        "wage slip",
        "basic salary",
        "basic pay",
        "gross salary",
        "net salary",
        "deduction",
        "deducted",
        "kata",
        "kat raha",
        "esi",
        "esic",
        "professional tax",
        "pt",
        "minimum wage",
        "min wage",
        "bonus",
        "statutory bonus",
        "ctc",
        "take home",
        "in hand",
        "epf deduction",
        "pf deduction",
        "pf kata",
    ],
    "labour": [
        "gratuity",
        "termination",
        "terminated",
        "fired",
        "nikala",
        "retrenchment",
        "retrenched",
        "notice period",
        "wrongful termination",
        "maternity",
        "pregnant",
        "pregnancy",
        "maternity leave",
        "overtime",
        "ot pay",
        "labour law",
        "labor law",
        "industrial dispute",
        "sexual harassment",
        "posh",
        "resign",
        "resigned",
        "resignation",
    ],
    "tax": [
        "income tax",
        "tax",
        "tds",
        "itr",
        "it return",
        "form 16",
        "80c",
        "80d",
        "section 80",
        "hra",
        "house rent",
        "rent allowance",
        "tax regime",
        "old regime",
        "new regime",
        "tax slab",
        "taxable income",
        "refund",
        "deduction under",
        "nps",
        "elss",
        "26as",
        "ais",
        "tis",
    ],
}

# ── Keyword baseline ──────────────────────────────────────────────────────────


def baseline_route(query: str) -> str:
    """
    Keyword-count baseline router.
    Counts keyword matches per domain, picks the domain with most hits.
    Ties → 'pf' (most common domain).
    """
    q = query.lower()
    scores = {}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in q:
                # Longer keywords get more weight to avoid substring false positives
                score += len(kw.split())
        scores[domain] = score

    max_score = max(scores.values())
    if max_score == 0:
        return "pf"  # default fallback

    # Get all domains with max score
    top_domains = [d for d, s in scores.items() if s == max_score]

    # Tie-breaking priority: pf > tax > payslip > labour
    priority = ["pf", "tax", "payslip", "labour"]
    for p in priority:
        if p in top_domains:
            return p

    return top_domains[0]


# ── LLM router (zero-shot) ────────────────────────────────────────────────────

ROUTER_PROMPT = """You are a query classifier for an Indian worker rights support system called ShramikSaathi.

Classify the user's query into exactly ONE domain.

DOMAINS:
- pf       → PF/EPF/EPFO account matters: withdrawal, transfer, balance, UAN, KYC, passbook, nomination, employer PF non-deposit, PF grievance, EPS pension claim
- payslip  → salary/payslip verification and deduction math: is EPF/ESI/PT deduction correct, minimum wage amount check, statutory bonus calculation, CTC breakup, contribution percentages, salary structure
- labour   → employment rights and legal action: wrongful termination, gratuity claim after leaving, notice period disputes, maternity leave entitlement, overtime rights, POSH, relieving letter disputes, labour court
- tax      → income tax matters: TDS on salary, TDS on PF withdrawal, Form 16, 80C/80D/HRA deductions, ITR filing, old vs new regime, refund status, landlord PAN for rent

CRITICAL DISAMBIGUATION RULES:
1. "Is my deduction correct?" / "kitna katna chahiye?" / percentage or amount verification → payslip
2. "My rights are violated" / "kya kar sakta hu?" / legal action / fired / not getting due → labour
3. Minimum wage AMOUNT check ("kitna milna chahiye") → payslip
4. Professional tax, ESI percentage, EPF contribution rate → payslip
5. Gratuity, termination, notice period, maternity leave, overtime RIGHTS → labour
6. TDS on PF withdrawal, Form 15G for PF → tax (not pf — the core question is about tax)
7. HRA exemption, rent allowance calculation → tax
8. PF withdrawal process, UAN issue, PF transfer, KYC → pf
9. "Employer deducting wrong PF from salary" → payslip (verifying deduction amount)
10. "Employer not depositing PF" → pf (PF account issue, not payslip)

OUTPUT: Only a valid JSON object: {"domain": "...", "confidence": 0.0-1.0}
No explanation, no markdown."""


def llm_route(query: str) -> dict:
    """
    LLM zero-shot router.
    Returns {"domain": str, "confidence": float}
    """
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": ROUTER_PROMPT},
            {"role": "user", "content": query},
        ],
        temperature=0.0,
        max_tokens=50,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"```json|```", "", raw).strip()

    try:
        parsed = json.loads(raw)
        domain = parsed.get("domain", "pf").lower().strip()
        confidence = float(parsed.get("confidence", 0.5))

        valid_domains = {"pf", "payslip", "labour", "tax"}
        if domain not in valid_domains:
            print(f"[Router] Invalid domain '{domain}' — falling back to pf")
            domain = "pf"

        return {"domain": domain, "confidence": confidence}

    except (json.JSONDecodeError, ValueError):
        print(f"[Router] Parse failed: {raw}")
        return {"domain": "pf", "confidence": 0.0}


def route(query: str, use_llm: bool = True) -> str:
    """Main entry point. Returns domain string."""
    if use_llm:
        return llm_route(query)["domain"]
    else:
        return baseline_route(query)


# ── Test ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_queries = [
        "bhai maine company left kia 3 month ho gaye, EPFO portal me form 19 submit nahi ho ra",
        "salary slip dekha abhi, gross 22000 h aur ESI 165 rps kata h. correct hai ye?",
        "boss fired me randomly yesterday over whatsapp, no warning letter nothing",
        "form 16 nhi diya ab tak IT return kaise bharu next week due date hai",
        "gratuity amount nahi de rahe, maine 4 years 8 months continuous kaam kiya",
        "new tax scheme me 80C ka 1.5lakh deduction claim kar sakte hai?",
        "my PF is showing wrong amount in passbook, employer ne kam deposit kiya",
        "im pregnant 7 months, manager is saying only 12 weeks leave",
    ]

    print("=" * 70)
    print("BASELINE vs LLM ROUTER")
    print("=" * 70)

    for q in test_queries:
        bl = baseline_route(q)
        llm = llm_route(q)
        match = "✓" if bl == llm["domain"] else "✗"
        print(f"\n  Query:    {q[:80]}")
        print(f"  Baseline: {bl}")
        print(f"  LLM:      {llm['domain']} (conf={llm['confidence']})")
        print(f"  Match:    {match}")
