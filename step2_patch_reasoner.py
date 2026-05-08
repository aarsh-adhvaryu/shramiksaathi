"""
Patches app.py to use deterministic eligibility rules instead of LLM reasoner.
Run from project root: python step2_patch_reasoner.py
"""

with open("app.py", "r") as f:
    code = f.read()

# 1. Add rules loading and fast_reasoner function after ALL_KB_DOC_IDS block
insert_after = 'ALL_KB_DOC_IDS.add(json.loads(line)["doc_id"])\n'

rules_code = '''
# Pre-cached eligibility rules (deterministic, no LLM call)
with open(ROOT / "data" / "eligibility_rules.json") as f:
    ELIGIBILITY_RULES = json.load(f)

def fast_reasoner(slots, domain, intent):
    conditions = ELIGIBILITY_RULES.get(domain, {}).get(intent, [])
    if not conditions:
        return {"decision": "ANSWER", "eligible": True, "coverage": 1.0,
                "met": [], "failed": [], "warnings": [], "unresolved": [], "question": None}
    met, failed, warnings, unresolved = [], [], [], []
    for c in conditions:
        field = c.get("field", "")
        slot_val = slots.get(field)
        mandatory = c.get("mandatory", True)
        if slot_val is None:
            if mandatory:
                unresolved.append(dict(c))
            continue
        result = evaluate_condition(slot_val, c.get("operator", "eq"), c.get("value"))
        entry = dict(c)
        entry["slot_value"] = slot_val
        if not mandatory:
            warnings.append(entry)
        elif result:
            met.append(entry)
        else:
            failed.append(entry)
    total = len(met) + len(failed) + len(unresolved)
    resolved = len(met) + len(failed)
    coverage = round(resolved / total, 2) if total > 0 else 1.0
    if failed:
        decision, eligible = "ANSWER", False
    elif unresolved:
        decision, eligible = "ASK", None
    else:
        decision, eligible = "ANSWER", True
    question = None
    if decision == "ASK" and unresolved:
        field = unresolved[0].get("field", "unknown")
        questions = {
            "employment_status": "Are you currently employed, unemployed, or retired?",
            "service_years": "How many total years have you contributed to PF?",
            "months_unemployed": "How many months have you been unemployed?",
            "uan_status": "Is your UAN currently active?",
            "kyc_status": "Is your KYC complete on the EPFO portal?",
            "employment_years": "How many years have you worked with this employer?",
            "termination_reason": "Did you resign, were you fired, or retrenched?",
            "annual_income": "What is your total annual income?",
            "tax_regime": "Are you on the old or new tax regime?",
            "basic_salary": "What is your monthly basic salary?",
            "gross_salary": "What is your monthly gross salary?",
        }
        question = questions.get(field, "Could you provide your " + field.replace("_", " ") + "?")
    return {"decision": decision, "eligible": eligible, "coverage": coverage,
            "met": met, "failed": failed, "warnings": warnings, "unresolved": unresolved, "question": question}
'''

if insert_after in code:
    code = code.replace(insert_after, insert_after + rules_code)
    print("[1/3] Added fast_reasoner function")
else:
    print("[1/3] WARNING: Could not find insertion point for fast_reasoner")

# 2. Replace batched_reasoner call with fast_reasoner
old_call = "reasoning = batched_reasoner(passages, slots, domain, intent)"
new_call = "reasoning = fast_reasoner(slots, domain, intent)"
if old_call in code:
    code = code.replace(old_call, new_call)
    print("[2/3] Replaced batched_reasoner with fast_reasoner")
else:
    print("[2/3] WARNING: Could not find batched_reasoner call")

# 3. Update trace label
old_label = '"### Call 2: Batched Reasoner ("'
new_label = '"### Call 2: Eligibility Reasoner ("'
if old_label in code:
    code = code.replace(old_label, new_label)
    print("[3/3] Updated trace label")
else:
    print("[3/3] WARNING: Could not find trace label to update")

with open("app.py", "w") as f:
    f.write(code)

print("\nDone! app.py patched with deterministic eligibility reasoner.")
print("Run: python app.py")
