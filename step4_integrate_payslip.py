"""
Patches app.py to integrate the ParsePayslip deterministic calculator.
Run from project root: python step4_integrate_payslip.py
"""

with open("app.py", "r") as f:
    code = f.read()

changes = 0

# 1. Add import for tools
import_line = "from search_kb import SearchKB"
new_import = "from search_kb import SearchKB\nfrom tools import parse_payslip, format_payslip_result"

if "parse_payslip" not in code:
    if import_line in code:
        code = code.replace(import_line, new_import)
        changes += 1
        print("[1/3] Added parse_payslip import")
    else:
        print("[1/3] WARNING: Could not find import insertion point")
else:
    print("[1/3] parse_payslip import already present")

# 2. Update build_generator_input to accept tool_context
old_gen_sig = "def build_generator_input(query, domain, passages, reasoning, slots):"
new_gen_sig = 'def build_generator_input(query, domain, passages, reasoning, slots, tool_context=""):'

if old_gen_sig in code and "tool_context" not in code:
    code = code.replace(old_gen_sig, new_gen_sig)

    # Add tool_context to the prompt string
    old_prompt_end = '+ "\\n\\nProduce the final answer now.")'
    new_prompt_end = '+ ("\\n\\nTOOL OUTPUT:\\n" + tool_context if tool_context else "")\n            + "\\n\\nProduce the final answer now.")'
    code = code.replace(old_prompt_end, new_prompt_end)
    changes += 1
    print("[2/3] Updated build_generator_input with tool_context parameter")
else:
    if "tool_context" in code:
        print("[2/3] tool_context already present")
    else:
        print("[2/3] WARNING: Could not find build_generator_input signature")

# 3. Add ParsePayslip execution before generator call
# Find the generator call section and inject tool execution before it
old_gen_call = '    # CALL 3: Generator'
new_gen_call = '''    # Tool: ParsePayslip (deterministic, payslip domain only)
    tool_context = ""
    if domain == "payslip":
        try:
            payslip_result = parse_payslip(slots)
            tool_context = format_payslip_result(payslip_result)
            trace.append("\\n### Tool: ParsePayslip (0.0s)")
            for calc in payslip_result.get("calculations", []):
                trace.append("  " + calc.get("component", "?") + ": " + calc.get("explanation", ""))
                if "reported" in calc:
                    trace.append("    Reported: " + str(calc["reported"]) + " | Expected: " + str(calc["expected"]) + " | " + calc.get("status", ""))
            if payslip_result.get("anomalies"):
                for a in payslip_result["anomalies"]:
                    trace.append("  ! " + a)
        except Exception as e:
            trace.append("\\n### Tool: ParsePayslip — error: " + str(e))

    # CALL 3: Generator'''

if "Tool: ParsePayslip" not in code:
    code = code.replace(old_gen_call, new_gen_call)
    changes += 1
    print("[3/3] Added ParsePayslip execution before generator")
else:
    print("[3/3] ParsePayslip execution already present")

# 4. Pass tool_context to build_generator_input
old_build_call = "user_content = build_generator_input(user_query, domain, passages, reasoning, slots)"
new_build_call = "user_content = build_generator_input(user_query, domain, passages, reasoning, slots, tool_context)"

if old_build_call in code and "tool_context)" not in code:
    code = code.replace(old_build_call, new_build_call)
    print("    Updated build_generator_input call with tool_context")

with open("app.py", "w") as f:
    f.write(code)

print(f"\nDone! {changes} changes applied to app.py.")
print("Run: python app.py")
print('Test: "My basic salary is 20000, EPF deducted is 1200. Is this correct?"')
