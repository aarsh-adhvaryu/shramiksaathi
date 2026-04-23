"""
ShramikSaathi Tools — deterministic tools for the ReAct loop

GetPolicy     — exact lookup by doc_id from KB
ParsePayslip  — computes expected EPF/ESI/PT deductions, compares with actuals

These are NOT LLM calls — they're deterministic calculations and lookups.
The ReAct loop decides WHEN to call them. The tools just compute.
"""

import json
from pathlib import Path


# ══════════════════════════════════════════════════════════════════════════════
# GetPolicy — exact document lookup by doc_id or section_id
# ══════════════════════════════════════════════════════════════════════════════


class PolicyStore:
    """Holds KB docs indexed by doc_id for exact lookup."""

    def __init__(self, store_path="../index/chunk_store.json"):
        with open(store_path, encoding="utf-8") as f:
            chunks = json.load(f)

        # Index by doc_id (first chunk per doc_id wins)
        self._by_doc_id = {}
        self._by_section_id = {}
        for c in chunks:
            doc_id = c.get("doc_id", "")
            section_id = c.get("section_id", "")
            if doc_id and doc_id not in self._by_doc_id:
                self._by_doc_id[doc_id] = c
            if section_id and section_id not in self._by_section_id:
                self._by_section_id[section_id] = c

    def get(self, identifier: str) -> dict | None:
        """
        Look up by doc_id or section_id.
        Returns full doc dict or None if not found.
        """
        result = self._by_doc_id.get(identifier)
        if result:
            return result
        result = self._by_section_id.get(identifier)
        return result

    def get_formatted(self, identifier: str) -> str:
        """Look up and return formatted string for the ReAct observation."""
        doc = self.get(identifier)
        if not doc:
            return f"[GetPolicy] No document found for '{identifier}'"

        return (
            f"doc_id: {doc.get('doc_id', '?')}\n"
            f"title: {doc.get('title', '?')}\n"
            f"domain: {doc.get('domain', '?')}\n"
            f"effective_date: {doc.get('effective_date', '?')}\n"
            f"content:\n{doc.get('content', '')}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# ParsePayslip — deterministic deduction calculator
# ══════════════════════════════════════════════════════════════════════════════

# ── Professional Tax slabs by state ────────────────────────────────────────────

PT_SLABS = {
    "Maharashtra": [
        (7500, 0), (10000, 175), (float("inf"), 200),
    ],
    "Karnataka": [
        (14999, 0), (29999, 150), (float("inf"), 200),
    ],
    "Tamil Nadu": [
        (3500, 0), (5000, 22), (7500, 52), (10000, 115),
        (12500, 171), (float("inf"), 208),
    ],
    "Telangana": [
        (15000, 0), (20000, 150), (float("inf"), 200),
    ],
    "West Bengal": [
        (10000, 0), (15000, 110), (25000, 130), (40000, 150),
        (float("inf"), 200),
    ],
    "Gujarat": [
        (5999, 0), (8999, 80), (11999, 150), (float("inf"), 200),
    ],
    "Kerala": [
        (1999, 0), (2999, 20), (4999, 30), (7499, 50),
        (11999, 75), (17999, 100), (29999, 125), (float("inf"), 200),
    ],
    "Bihar": [
        (25000, 0), (float("inf"), 208),
    ],
    "Madhya Pradesh": [
        (18750, 0), (float("inf"), 208),
    ],
    "Odisha": [
        (13304, 0), (25000, 125), (float("inf"), 200),
    ],
}

# States with NO professional tax
PT_EXEMPT_STATES = {
    "Delhi", "Uttar Pradesh", "Haryana", "Punjab",
    "Rajasthan", "Uttarakhand", "Himachal Pradesh",
    "Jammu and Kashmir", "Goa",
}


def _compute_pt(gross_salary: int, state: str) -> dict:
    """Compute monthly Professional Tax for a given state and gross salary."""
    if not state:
        return {"expected_pt": None, "basis": "State not provided — cannot compute PT"}

    if state in PT_EXEMPT_STATES:
        return {
            "expected_pt": 0,
            "basis": f"{state} does not levy Professional Tax",
        }

    slabs = PT_SLABS.get(state)
    if not slabs:
        return {"expected_pt": None, "basis": f"PT slabs not available for {state}"}

    for threshold, amount in slabs:
        if gross_salary <= threshold:
            return {
                "expected_pt": amount,
                "basis": f"{state} PT slab: salary ≤₹{threshold:,} → ₹{amount}/month",
            }

    return {"expected_pt": None, "basis": f"Could not determine PT for {state}"}


def _compute_epf(basic_salary: int) -> dict:
    """
    Compute monthly EPF deduction.
    Employee: 12% of basic (on actual basic, even if > ₹15,000)
    Employer: 12% of basic (3.67% → EPF, 8.33% → EPS, EPS capped at ₹15,000 basic)
    """
    employee_rate = 0.12
    employee_epf = round(basic_salary * employee_rate)

    # Employer split
    eps_base = min(basic_salary, 15000)  # EPS capped at ₹15,000
    employer_eps = round(eps_base * 0.0833)
    employer_epf = round(basic_salary * 0.12) - employer_eps

    return {
        "expected_employee_epf": employee_epf,
        "epf_rate": "12% of basic salary",
        "employer_epf": employer_epf,
        "employer_eps": employer_eps,
        "basis": f"EPF Act: 12% of basic ₹{basic_salary:,} = ₹{employee_epf:,}/month",
    }


def _compute_esi(gross_salary: int) -> dict:
    """
    Compute monthly ESI deduction.
    Applicable if gross ≤ ₹21,000/month.
    Employee: 0.75% of gross. Employer: 3.25% of gross.
    """
    if gross_salary > 21000:
        return {
            "esi_applicable": False,
            "expected_employee_esi": 0,
            "expected_employer_esi": 0,
            "basis": f"ESI not applicable: gross ₹{gross_salary:,} exceeds ₹21,000 threshold",
        }

    employee_esi = round(gross_salary * 0.0075)
    employer_esi = round(gross_salary * 0.0325)

    return {
        "esi_applicable": True,
        "expected_employee_esi": employee_esi,
        "expected_employer_esi": employer_esi,
        "basis": f"ESI Act: employee 0.75% of gross ₹{gross_salary:,} = ₹{employee_esi:,}/month",
    }


def parse_payslip(slots: dict) -> dict:
    """
    Deterministic payslip audit tool.

    Takes user's salary details, computes expected deductions,
    compares with actuals (if provided), returns pass/fail per deduction.

    Args:
        slots: dict with keys from payslip schema:
            basic_salary, gross_salary, epf_deducted, esi_deducted, state, employee_count

    Returns:
        dict with computed values, comparisons, and verdicts
    """
    basic = slots.get("basic_salary")
    gross = slots.get("gross_salary")
    epf_actual = slots.get("epf_deducted")
    esi_actual = slots.get("esi_deducted")
    state = slots.get("state")

    result = {
        "basic_salary": basic,
        "gross_salary": gross,
        "state": state,
        "deductions": [],
        "summary": [],
    }

    # ── EPF ────────────────────────────────────────────────────────────────────
    if basic is not None:
        epf = _compute_epf(basic)
        expected = epf["expected_employee_epf"]
        entry = {
            "type": "EPF",
            "expected": expected,
            "actual": epf_actual,
            "basis": epf["basis"],
            "employer_epf": epf["employer_epf"],
            "employer_eps": epf["employer_eps"],
        }

        if epf_actual is not None:
            diff = epf_actual - expected
            if abs(diff) <= 1:  # rounding tolerance
                entry["verdict"] = "CORRECT"
                entry["message"] = f"EPF deduction ₹{epf_actual:,} matches expected ₹{expected:,}"
            elif diff < 0:
                entry["verdict"] = "UNDER_DEDUCTED"
                entry["message"] = f"EPF under-deducted by ₹{abs(diff):,}. Expected ₹{expected:,}, actual ₹{epf_actual:,}"
            else:
                entry["verdict"] = "OVER_DEDUCTED"
                entry["message"] = f"EPF over-deducted by ₹{diff:,}. Expected ₹{expected:,}, actual ₹{epf_actual:,}"
        else:
            entry["verdict"] = "NO_ACTUAL"
            entry["message"] = f"Expected EPF: ₹{expected:,}/month. Actual not provided."

        result["deductions"].append(entry)
        result["summary"].append(entry["message"])

    # ── ESI ────────────────────────────────────────────────────────────────────
    salary_for_esi = gross if gross is not None else basic
    if salary_for_esi is not None:
        esi = _compute_esi(salary_for_esi)
        expected_esi = esi["expected_employee_esi"]
        entry = {
            "type": "ESI",
            "applicable": esi.get("esi_applicable", True),
            "expected": expected_esi,
            "actual": esi_actual,
            "basis": esi["basis"],
        }

        if esi_actual is not None:
            if not esi.get("esi_applicable", True):
                if esi_actual == 0:
                    entry["verdict"] = "CORRECT"
                    entry["message"] = f"ESI correctly not deducted — gross ₹{salary_for_esi:,} exceeds ₹21,000"
                else:
                    entry["verdict"] = "SHOULD_NOT_DEDUCT"
                    entry["message"] = f"ESI should NOT be deducted — gross ₹{salary_for_esi:,} exceeds ₹21,000 threshold, but ₹{esi_actual:,} is being deducted"
            else:
                diff = esi_actual - expected_esi
                if abs(diff) <= 1:
                    entry["verdict"] = "CORRECT"
                    entry["message"] = f"ESI deduction ₹{esi_actual:,} matches expected ₹{expected_esi:,}"
                elif diff < 0:
                    entry["verdict"] = "UNDER_DEDUCTED"
                    entry["message"] = f"ESI under-deducted by ₹{abs(diff):,}. Expected ₹{expected_esi:,}, actual ₹{esi_actual:,}"
                else:
                    entry["verdict"] = "OVER_DEDUCTED"
                    entry["message"] = f"ESI over-deducted by ₹{diff:,}. Expected ₹{expected_esi:,}, actual ₹{esi_actual:,}"
        else:
            if not esi.get("esi_applicable", True):
                entry["verdict"] = "NOT_APPLICABLE"
                entry["message"] = f"ESI not applicable — gross ₹{salary_for_esi:,} exceeds ₹21,000"
            else:
                entry["verdict"] = "NO_ACTUAL"
                entry["message"] = f"Expected ESI: ₹{expected_esi:,}/month. Actual not provided."

        result["deductions"].append(entry)
        result["summary"].append(entry["message"])

    # ── Professional Tax ───────────────────────────────────────────────────────
    salary_for_pt = gross if gross is not None else basic
    if salary_for_pt is not None:
        pt = _compute_pt(salary_for_pt, state)
        expected_pt = pt.get("expected_pt")
        entry = {
            "type": "Professional Tax",
            "expected": expected_pt,
            "basis": pt["basis"],
        }

        if expected_pt is not None:
            entry["verdict"] = "COMPUTED"
            entry["message"] = f"Expected PT: ₹{expected_pt:,}/month. {pt['basis']}"
        else:
            entry["verdict"] = "CANNOT_COMPUTE"
            entry["message"] = pt["basis"]

        result["deductions"].append(entry)
        result["summary"].append(entry["message"])

    return result


def format_payslip_result(result: dict) -> str:
    """Format ParsePayslip output as a string for the ReAct observation."""
    lines = ["PAYSLIP AUDIT RESULT:"]
    lines.append(f"  Basic Salary: ₹{result['basic_salary']:,}" if result['basic_salary'] else "  Basic Salary: not provided")
    lines.append(f"  Gross Salary: ₹{result['gross_salary']:,}" if result['gross_salary'] else "  Gross Salary: not provided")
    lines.append(f"  State: {result['state'] or 'not provided'}")
    lines.append("")

    for d in result["deductions"]:
        lines.append(f"  [{d['type']}]")
        lines.append(f"    {d['message']}")
        lines.append(f"    Legal basis: {d['basis']}")
        if d.get("verdict"):
            lines.append(f"    Verdict: {d['verdict']}")
        lines.append("")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    # Test GetPolicy
    print("=" * 60)
    print("TEST: GetPolicy")
    print("=" * 60)
    store = PolicyStore()
    for doc_id in ["EPF_ACT_S68_S69", "GRATUITY_ACT_S4_ELIG", "ITA_SECTION_10_13A", "NONEXISTENT_DOC"]:
        result = store.get_formatted(doc_id)
        print(f"\n  GetPolicy('{doc_id}'):")
        print(f"  {result[:150]}...")

    # Test ParsePayslip
    print("\n" + "=" * 60)
    print("TEST: ParsePayslip")
    print("=" * 60)

    # Case 1: EPF correct
    print("\n── Case 1: Basic 20000, EPF 2400 (correct) ──")
    r = parse_payslip({"basic_salary": 20000, "gross_salary": 25000, "epf_deducted": 2400, "state": "Maharashtra"})
    print(format_payslip_result(r))

    # Case 2: EPF under-deducted
    print("\n── Case 2: Basic 20000, EPF 1800 (under by 600) ──")
    r = parse_payslip({"basic_salary": 20000, "gross_salary": 25000, "epf_deducted": 1800, "state": "Karnataka"})
    print(format_payslip_result(r))

    # Case 3: ESI not applicable
    print("\n── Case 3: Gross 28000, ESI 0 (correct, above threshold) ──")
    r = parse_payslip({"basic_salary": 15000, "gross_salary": 28000, "esi_deducted": 0, "state": "Karnataka"})
    print(format_payslip_result(r))

    # Case 4: ESI wrongly deducted
    print("\n── Case 4: Gross 25000, ESI 500 (should not deduct) ──")
    r = parse_payslip({"basic_salary": 15000, "gross_salary": 25000, "esi_deducted": 500, "state": "Tamil Nadu"})
    print(format_payslip_result(r))

    # Case 5: Delhi — no PT
    print("\n── Case 5: Delhi, no PT ──")
    r = parse_payslip({"basic_salary": 20000, "gross_salary": 30000, "state": "Delhi"})
    print(format_payslip_result(r))

    # Case 6: ESI correct
    print("\n── Case 6: Gross 18500, ESI 139 (correct) ──")
    r = parse_payslip({"basic_salary": 10000, "gross_salary": 18500, "esi_deducted": 139, "state": "Telangana"})
    print(format_payslip_result(r))
