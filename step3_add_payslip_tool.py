"""
Adds parse_payslip and format_payslip_result to src/tools.py
Run from project root: python step3_add_payslip_tool.py
"""
from pathlib import Path

TOOLS_PATH = Path("src/tools.py")

PAYSLIP_CODE = '''

# ── ParsePayslip: Deterministic Statutory Deduction Calculator ──

# Professional Tax slabs (monthly, select states)
PROF_TAX_SLABS = {
    "maharashtra": [(7500, 0), (10000, 175), (float("inf"), 200)],
    "karnataka":   [(15000, 0), (float("inf"), 200)],
    "gujarat":     [(12000, 0), (float("inf"), 200)],
    "west_bengal": [(10000, 0), (15000, 110), (25000, 130), (40000, 150), (float("inf"), 200)],
    "default":     [(15000, 0), (float("inf"), 200)],
}


def parse_payslip(slots: dict) -> dict:
    """
    Statutory deduction calculator.
    Computes expected EPF, ESI, and professional tax from slot values.
    Returns dict with expected values, anomalies, and explanations.
    """
    basic = slots.get("basic_salary")
    gross = slots.get("gross_salary")
    epf_reported = slots.get("epf_deducted")
    esi_reported = slots.get("esi_deducted")
    state = slots.get("state", "default").lower().replace(" ", "_")

    result = {
        "basic_salary": basic,
        "gross_salary": gross,
        "calculations": [],
        "anomalies": [],
        "summary": "",
    }

    if basic is None and gross is None:
        result["summary"] = "Insufficient data: need at least basic_salary or gross_salary."
        return result

    # ── EPF Calculation ──
    if basic is not None:
        # EPF wage ceiling: Rs 15,000
        epf_wage = min(int(basic), 15000)
        # Employee contribution: 12% of basic (or wage ceiling, whichever is less)
        expected_epf_employee = round(int(basic) * 0.12)
        # Employer contribution: 3.67% to EPF + 8.33% to EPS (on wage ceiling)
        eps_contribution = round(epf_wage * 0.0833)
        employer_epf = round(int(basic) * 0.12) - eps_contribution if int(basic) <= 15000 else round(int(basic) * 0.12) - round(15000 * 0.0833)

        calc = {
            "component": "EPF (Employee Share)",
            "formula": "12% of basic salary",
            "basic_salary": int(basic),
            "expected": expected_epf_employee,
            "explanation": f"12% of Rs {int(basic):,} = Rs {expected_epf_employee:,}",
        }

        if epf_reported is not None:
            calc["reported"] = int(epf_reported)
            diff = int(epf_reported) - expected_epf_employee
            if abs(diff) > 1:  # allow Rs 1 rounding
                calc["status"] = "MISMATCH"
                if diff < 0:
                    result["anomalies"].append(
                        f"EPF under-deducted by Rs {abs(diff):,}. "
                        f"Expected Rs {expected_epf_employee:,} (12% of Rs {int(basic):,}), "
                        f"got Rs {int(epf_reported):,}."
                    )
                else:
                    result["anomalies"].append(
                        f"EPF over-deducted by Rs {abs(diff):,}. "
                        f"Expected Rs {expected_epf_employee:,}, got Rs {int(epf_reported):,}."
                    )
            else:
                calc["status"] = "OK"
        else:
            calc["status"] = "NOT_REPORTED"

        result["calculations"].append(calc)

    # ── ESI Calculation ──
    if gross is not None:
        gross_val = int(gross)
        if gross_val <= 21000:
            expected_esi = round(gross_val * 0.0075)
            calc = {
                "component": "ESI (Employee Share)",
                "formula": "0.75% of gross salary (applicable if gross <= Rs 21,000)",
                "gross_salary": gross_val,
                "expected": expected_esi,
                "explanation": f"0.75% of Rs {gross_val:,} = Rs {expected_esi:,}",
            }
            if esi_reported is not None:
                calc["reported"] = int(esi_reported)
                diff = int(esi_reported) - expected_esi
                if abs(diff) > 1:
                    calc["status"] = "MISMATCH"
                    result["anomalies"].append(
                        f"ESI mismatch: expected Rs {expected_esi:,}, got Rs {int(esi_reported):,}."
                    )
                else:
                    calc["status"] = "OK"
            else:
                calc["status"] = "NOT_REPORTED"
            result["calculations"].append(calc)
        else:
            result["calculations"].append({
                "component": "ESI",
                "status": "NOT_APPLICABLE",
                "explanation": f"Gross salary Rs {gross_val:,} exceeds Rs 21,000 threshold. ESI not applicable.",
            })

    # ── Professional Tax ──
    salary_for_pt = gross if gross is not None else basic
    if salary_for_pt is not None:
        sal = int(salary_for_pt)
        slabs = PROF_TAX_SLABS.get(state, PROF_TAX_SLABS["default"])
        pt = 0
        for threshold, amount in slabs:
            if sal <= threshold:
                pt = amount
                break
        result["calculations"].append({
            "component": "Professional Tax",
            "state": state,
            "salary_used": sal,
            "expected": pt,
            "explanation": f"Professional tax for {state}: Rs {pt}/month on salary Rs {sal:,}",
            "status": "INFORMATIONAL",
        })

    # ── Summary ──
    if result["anomalies"]:
        result["summary"] = "ANOMALIES FOUND: " + " | ".join(result["anomalies"])
    else:
        result["summary"] = "All reported deductions are within expected statutory limits."

    return result


def format_payslip_result(result: dict) -> str:
    """Format parse_payslip output as context string for the generator prompt."""
    lines = ["PAYSLIP TOOL OUTPUT (deterministic calculation):"]

    for calc in result.get("calculations", []):
        component = calc.get("component", "?")
        status = calc.get("status", "?")
        explanation = calc.get("explanation", "")
        lines.append(f"  {component}: {explanation}")
        if "reported" in calc:
            lines.append(f"    Reported: Rs {calc['reported']:,}  |  Expected: Rs {calc['expected']:,}  |  Status: {status}")
        elif status == "NOT_APPLICABLE":
            lines.append(f"    Status: {status}")

    if result.get("anomalies"):
        lines.append("")
        lines.append("  ANOMALIES:")
        for a in result["anomalies"]:
            lines.append(f"    ! {a}")

    lines.append(f"  Summary: {result.get('summary', '')}")
    return "\\n".join(lines)
'''

# Check if tools.py exists
if TOOLS_PATH.exists():
    existing = TOOLS_PATH.read_text()
    if "parse_payslip" in existing:
        print("parse_payslip already exists in src/tools.py — skipping")
    else:
        with open(TOOLS_PATH, "a") as f:
            f.write(PAYSLIP_CODE)
        print(f"Added parse_payslip + format_payslip_result to {TOOLS_PATH}")
else:
    with open(TOOLS_PATH, "w") as f:
        f.write('"""ShramikSaathi — Tools"""\n' + PAYSLIP_CODE)
    print(f"Created {TOOLS_PATH} with parse_payslip + format_payslip_result")
