import json

rules = {
  "pf": {
    "full_withdrawal": [
      {"field": "employment_status", "operator": "eq", "value": "unemployed", "mandatory": True, "doc_id": "FAQ_WD_022"},
      {"field": "months_unemployed", "operator": "gte", "value": 2, "mandatory": True, "doc_id": "FAQ_WD_022"},
      {"field": "uan_status", "operator": "eq", "value": "active", "mandatory": True, "doc_id": "FAQ_WD_022"},
      {"field": "kyc_status", "operator": "eq", "value": "complete", "mandatory": True, "doc_id": "FAQ_WD_022"},
      {"field": "service_years", "operator": "lt", "value": 5, "mandatory": False, "doc_id": "CIRC_2024_TDS"}
    ],
    "partial_withdrawal": [
      {"field": "employment_status", "operator": "eq", "value": "unemployed", "mandatory": True, "doc_id": "WD_FORM31_PARTIAL_PRACTICAL"},
      {"field": "months_unemployed", "operator": "gte", "value": 1, "mandatory": True, "doc_id": "WD_FORM31_PARTIAL_PRACTICAL"}
    ],
    "tds_query": [
      {"field": "service_years", "operator": "lt", "value": 5, "mandatory": False, "doc_id": "CIRC_2024_TDS"},
      {"field": "pf_withdrawal_amount", "operator": "gte", "value": 50000, "mandatory": False, "doc_id": "CIRC_2024_TDS"}
    ],
    "transfer": [], "kyc_issue": [], "employer_complaint": [], "pension": []
  },
  "labour": {
    "gratuity": [
      {"field": "employment_years", "operator": "gte", "value": 5, "mandatory": True, "doc_id": "GRATUITY_ACT_S4_ELIG"},
      {"field": "employer_type", "operator": "in", "value": ["private","factory","government"], "mandatory": False, "doc_id": "GRATUITY_ACT_S4_ELIG"}
    ],
    "wrongful_termination": [
      {"field": "termination_reason", "operator": "eq", "value": "employer_terminated", "mandatory": True, "doc_id": "IDA_S25F"}
    ],
    "maternity_benefit": [
      {"field": "employment_years", "operator": "gte", "value": 1, "mandatory": True, "doc_id": "MATERNITY_BENEFIT_ACT_2017"}
    ],
    "overtime_pay": [], "notice_period": []
  },
  "payslip": {
    "verify_epf": [
      {"field": "basic_salary", "operator": "not_null", "value": None, "mandatory": True, "doc_id": "EPF_ACT_S6_CONTRIB"}
    ],
    "verify_esi": [
      {"field": "gross_salary", "operator": "not_null", "value": None, "mandatory": True, "doc_id": "ESI_ACT_COVERAGE"}
    ],
    "check_deductions": [
      {"field": "basic_salary", "operator": "not_null", "value": None, "mandatory": True, "doc_id": "EPF_ACT_S6_CONTRIB"}
    ],
    "full_audit": [
      {"field": "basic_salary", "operator": "not_null", "value": None, "mandatory": True, "doc_id": "EPF_ACT_S6_CONTRIB"}
    ],
    "check_bonus": []
  },
  "tax": {
    "tds_on_salary": [
      {"field": "annual_income", "operator": "not_null", "value": None, "mandatory": True, "doc_id": "IT_TDS_SALARY"}
    ],
    "tds_on_pf": [
      {"field": "service_years", "operator": "lt", "value": 5, "mandatory": False, "doc_id": "CIRC_2024_TDS"}
    ],
    "hra_exemption": [
      {"field": "tax_regime", "operator": "eq", "value": "old_regime", "mandatory": True, "doc_id": "IT_HRA_EXEMPTION"}
    ],
    "deductions_80c": [
      {"field": "tax_regime", "operator": "eq", "value": "old_regime", "mandatory": True, "doc_id": "IT_80C"}
    ],
    "itr_filing": []
  }
}

with open("data/eligibility_rules.json", "w") as f:
    json.dump(rules, f, indent=2)

total = sum(len(v) for d in rules.values() for v in d.values())
print(f"Created data/eligibility_rules.json with {total} conditions")
