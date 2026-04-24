# Stage 1.3 Held-out Eval Report

- Prompts: 20
- Adapter: `/teamspace/studios/this_studio/shramiksaathi/out/lora_v2`

## Summary

| Metric | BASE | LoRA | Δ |
|---|---:|---:|---:|
| citation_coverage | 0.950 | 1.000 | +0.050 |
| fabrication_rate | 0.000 | 0.000 | +0.000 |
| expected_cites_hit | 0.700 | 0.800 | +0.100 |
| verdict_accuracy | 0.700 | 0.650 | -0.050 |
| grounded_clean | 0.650 | 0.650 | +0.000 |
| key_facts_mean | 0.650 | 0.675 | +0.025 |
| fabrication_count | 0 | 0 | — |

## Per-domain grounded_clean

| Domain | BASE | LoRA | Δ |
|---|---:|---:|---:|
| pf | 0.40 | 0.40 | +0.00 |
| payslip | 0.60 | 0.60 | +0.00 |
| labour | 1.00 | 0.80 | -0.20 |
| tax | 0.60 | 0.80 | +0.20 |

## Side-by-side (per prompt)

### pf_01 — pf/full_withdrawal
**Query:** resign kiye 4 mahine ho gaye, UAN active hai, KYC complete hai. total 7 saal kaam kiya pf me. pura paisa nikal sakta hu?
**Expected verdict:** eligible  |  **Expected cites:** ['FAQ_WD_023', 'CIRC_2024_TDS']

#### BASE  cites=['CIRC_2024_TDS']  fab=[]  verdict=True
```
**Eligibility:** eligible=True

**Result:** You can withdraw your entire PF amount.

**Reason:** You have been employed for 7 years, which is more than the required 5 years for full withdrawal [CIRC_2024_TDS].

**Next Steps:**

1.  Ensure you have a valid PAN card to avoid a higher TDS rate.
2.  If you have a bank account linked to your UAN and Aadhaar, you can submit a composite claim (Aadhaar) which only requires your signature.
3.  If there's a dispute, you can get attestation from your bank and submit to the Regional PF Commissioner explaining the reasons for not obtaining your employer's signature.

**Warning:** If you withdraw an amount exceeding Rs. 50,000, TDS will be applicable. The TDS rate will be 10% if you're a resident with a valid PAN, 20% if you're a resident without a valid PAN, and 30% plus 4% cess if you're a non-resident.
```
#### LoRA  cites=['CIRC_2024_TDS', 'FAQ_WD_023']  fab=[]  verdict=True
```
**Result:** You are eligible for full withdrawal of your PF amount.

**Eligibility Reasoning Trace:**
- You have been unemployed for 4 months [FAQ_WD_023].
- You have completed 7 years of service [FAQ_WD_023].
- Your UAN is active and KYC is complete [FAQ_WD_023].
- You have not specified any other conditions that would affect your eligibility.

**Steps:**

1.  You can submit your withdrawal application without the employer's signature by getting attestation from the bank where you maintain your account and submitting it to the Regional PF Commissioner [FAQ_WD_023].
2.  Alternatively, if you have activated your UAN and linked your bank account and Aadhaar, you can submit a composite claim (Aadhaar) which only requires your signature [FAQ_WD_023].
3.  Since you have completed 7 years of service, no TDS will be applicable on your withdrawal [CIRC_2024_TDS].

**Warnings/Caveats:** None.
```

### pf_02 — pf/full_withdrawal
**Query:** I resigned just last month, worked for 3 years total. UAN is active, KYC done. Can I withdraw my PF fully now?
**Expected verdict:** not eligible  |  **Expected cites:** ['FAQ_WD_023']

#### BASE  cites=['CIRC_2024_TDS', 'FAQ_WD_023']  fab=[]  verdict=False
```
**Eligibility:** eligible=False

**Reason:** You have not completed 5 years of service, which is a requirement for a full PF withdrawal without TDS [CIRC_2024_TDS].

**TDS Applicable:** Yes, since your service is less than 5 years and the withdrawal amount exceeds Rs. 50,000, TDS will be applicable. The applicable rate is 20% as you are a resident without a valid PAN [CIRC_2024_TDS].

**Next Steps:**

1.  Complete 5 years of service to be eligible for a full PF withdrawal without TDS.
2.  If you need to withdraw your PF now, you can submit a composite claim (Aadhaar) with your signature, but you will be subject to TDS [FAQ_WD_023].
3.  Ensure you have a valid PAN to avoid a higher TDS rate.

**Warning:** If you withdraw your PF now, you will be subject to TDS, and the amount deducted will be 20% of the withdrawal amount.
```
#### LoRA  cites=['CIRC_2024_TDS']  fab=[]  verdict=False
```
**Result:** You are eligible to withdraw your PF partially.

**Eligibility Reasoning Trace:**
- You have been unemployed for 1 month, which is less than 2 months (typically considered for full withdrawal).
- You have an active UAN and complete KYC.
- You have completed 3 years of service.

**Steps:**

1.  You can submit a partial withdrawal application using the composite claim (Aadhaar) option, which only requires your signature.
2.  Since you have been unemployed for less than 2 months, you may not be eligible for full withdrawal. However, you can withdraw a partial amount.
3.  As you have an active UAN and complete KYC, you can proceed with the composite claim.

**Warnings/Caveats:**
- If you have any disputes with your employer regarding the claim form, you can get attestation from your bank and submit to the Regional PF Commissioner.
- Be aware that TDS may be applicable if your withdrawal exceeds Rs.50,000 and you have less than 5 years of service. The applicable rate is 10% for resident with valid PAN, 20% for resident without valid PAN, and 30% plus 4% cess for non-resident. [CIRC_2024_TDS]
```

### pf_03 — pf/tds_query
**Query:** pf withdraw kiya 2 lakh ka, total service 3.5 years thi. TDS kitna lagega?
**Expected verdict:** conditional  |  **Expected cites:** ['CIRC_2024_TDS']

#### BASE  cites=['CIRC_2024_TDS', 'FORM_15G_INSTRUCTIONS']  fab=[]  verdict=True
```
**Result:**
You are eligible for PF withdrawal of Rs. 2,00,000.

**Eligibility Reasoning:**
Condition 1: Service years < 5 years [CIRC_2024_TDS]
Condition 2: Withdrawal amount exceeds Rs. 50,000 [CIRC_2024_TDS]
Condition 3: Service years = 3.5 years (satisfies Condition 1)
Condition 4: Withdrawal amount = Rs. 2,00,000 (satisfies Condition 2)

**Next Steps:**

1.  Since your service years are less than 5 years, TDS will be applicable.
2.  As a resident with a valid PAN, the TDS rate is 10% [CIRC_2024_TDS].
3.  You can submit Form 15G to avoid TDS if your total income is below the taxable limit (Rs. 2.50 lakh) and you are below 60 years old [FORM_15G_INSTRUCTIONS].

**Warning/Caveat:** Ensure you have a valid PAN to submit Form 15G and to avoid higher TDS rates.

**Expected TDS Calculation:**
TDS = 10% of Rs. 2,00,000 = Rs. 20,000

**Actual TDS will be deducted at the time of withdrawal, not at the time of PF withdrawal application.**
```
#### LoRA  cites=['CIRC_2024_TDS', 'FORM_15G_INSTRUCTIONS']  fab=[]  verdict=True
```
**Result:** TDS applicable on your PF withdrawal of Rs. 2,00,000.

**Eligibility:** Not eligible for exemption from TDS.

**Reasoning:** You have less than 5 years of service [CIRC_2024_TDS], and the withdrawal amount exceeds Rs. 50,000 [CIRC_2024_TDS].

**TDS Calculation:**

* Resident with valid PAN: 10% of Rs. 2,00,000 = Rs. 20,000
* Resident without valid PAN: 20% of Rs. 2,00,000 = Rs. 40,000
* Non-resident: 30% of Rs. 2,00,000 = Rs. 60,000 + 4% cess = Rs. 62,400

**Next Steps:**

1. Ensure you have a valid PAN to avoid a higher TDS rate.
2. Submit Form 15G to your employer if you meet the eligibility criteria (age below 60 and total income below Rs. 2.50 lakh) [FORM_15G_INSTRUCTIONS]. However, note that this form is only applicable for income below Rs. 2.50 lakh, which may not be the case in your scenario.

**Warning:** If you have any doubts or concerns, consult your employer or a tax professional for further guidance.
```

### pf_04 — pf/transfer
**Query:** new company join kiya, old PF ka transfer karna hai. UAN active hai KYC done hai. kaise transfer hoga?
**Expected verdict:** informational  |  **Expected cites:** ['FAQ_WD_024', 'FORM_13_INSTRUCTIONS']

#### BASE  cites=['CIRC_UAN_AUTO_TRANSFER', 'FAQ_WD_024']  fab=[]  verdict=False
```
**Result:** You are eligible to transfer your old PF account to the new company.

**Eligibility Reasoning Trace:**

1. You have an active UAN [FAQ_WD_024].
2. Your KYC is complete [FAQ_WD_024].

**Next Steps:**

1. Log in to the unified portal using your UAN and password.
2. Go to "Online Services" and select "One Member - One EPF Account (Transfer Request)".
3. Select your previous Member ID and submit the transfer request.
4. If you have an Aadhaar and bank account linked to your UAN, you may be eligible for auto-transfer [CIRC_UAN_AUTO_TRANSFER].

**Warning/Caveat:** Ensure your Date of Exit is updated in your old PF account to facilitate a smooth transfer process.

**Note:** If you have any issues or concerns, you can contact the EPFO or visit the unified portal for more information.
```
#### LoRA  cites=['CIRC_UAN_AUTO_TRANSFER', 'FAQ_WD_024']  fab=[]  verdict=False
```
**Result:** Your PF account can be transferred to the new establishment on change of employment.

**Eligibility:** Eligible (conditions met: UAN active [FAQ_WD_024], KYC complete [FAQ_WD_024])

**Steps:**

1.  Submit Form 13(R) or online transfer request through the member interface at the unified portal to transfer your PF account to the new establishment.
2.  If you have an active UAN and Aadhaar+Bank seeded, you can also submit the transfer claim online using the member interface.

**Warnings/Caveats:** Ensure your Date of Exit is updated in your previous account to facilitate the transfer process. If you have an active UAN and Aadhaar verification, your transfer may initiate automatically when the first month contribution is received in the new account from the new employer [CIRC_UAN_AUTO_TRANSFER].
```

### pf_05 — pf/kyc_issue
**Query:** KYC rejected dikha raha EPFO portal pe. Aadhaar aur PAN me name mismatch hai. kya kare?
**Expected verdict:** informational  |  **Expected cites:** ['FAQ_CLAIM_133']

#### BASE  cites=['FAQ_CLAIM_133', 'KYC_AADHAAR_GUIDE']  fab=[]  verdict=False
```
**Result:** You are eligible to apply for correction in KYC/member details.

**Steps:**

1.  You need to login to the EPFO UAN portal with your UAN.
2.  Update your KYC by uploading necessary documents online.
3.  If you have a name mismatch issue, you can use either Method 1 (employer approval) or Method 2 (self-validation through e-KYC Portal or UMANG app) to correct the details.

**Warnings/Caveats:**

*   For name mismatch, a Joint Declaration is required.
*   Ensure the details match exactly for self-validation through e-KYC Portal or UMANG app.

**Citations:**

*   [FAQ_CLAIM_133] for online correction process
*   [KYC_AADHAAR_GUIDE] for Method 1 and Method 2
```
#### LoRA  cites=['KYC_AADHAAR_GUIDE']  fab=[]  verdict=False
```
**Result:** KYC rejection ka samadhan karna hai.

**Eligibility:** Eligible (kyunki aap UAN me login kar sakte hain)

**Steps:**

1. Aapko apne UAN me login karna hoga.
2. Member portal par jaakar, Manage > KYC > Select Aadhaar > Enter Aadhaar number > Save karna hoga.
3. Agar name mismatch hai, to Joint Declaration kiya jaana hoga.

**Caveats:** Name mismatch ke liye Joint Declaration kiya jaana hoga, isliye aapko apne employer se saath me milna hoga. [KYC_AADHAAR_GUIDE]
```

### payslip_01 — payslip/verify_epf
**Query:** My basic salary is Rs 25000 and EPF deducted is Rs 3000 every month. Is the deduction correct?
**Expected verdict:** correct  |  **Expected cites:** ['EPF_ACT_S6_CONTRIB', 'TOOL_PAYSLIP_AUDIT']

#### BASE  cites=['EPF_ACT_S6_CONTRIB', 'EPF_PARA_26A', 'TOOL_PAYSLIP_AUDIT']  fab=[]  verdict=True
```
**Result:** The EPF deduction of ₹3,000 is CORRECT.

**Reason:** According to the EPF Act, both the employee and employer must each contribute 12% of the employee's basic wages [EPF_ACT_S6_CONTRIB]. The employee's basic salary is ₹25,000, and 12% of this amount is ₹3,000 [TOOL_PAYSLIP_AUDIT].

**Next Steps:**

1.  Verify that the employer is also contributing 12% of the employee's basic wages.
2.  Check if the employee has voluntarily opted to contribute on their full wages, if their basic salary exceeds ₹15,000 per month [EPF_PARA_26A].

**Warning/Caveat:** The EPF wage ceiling is ₹15,000 per month. If the employee's basic salary exceeds this amount, they may be eligible to contribute voluntarily on their full wages.

**Citation:** [EPF_ACT_S6_CONTRIB], [EPF_PARA_26A], [TOOL_PAYSLIP_AUDIT]
```
#### LoRA  cites=['EPF_ACT_S6_CONTRIB', 'EPF_PARA_26A', 'TOOL_PAYSLIP_AUDIT']  fab=[]  verdict=True
```
**EPF Deduction Verification**

**Result:** The EPF deduction of ₹3,000 is **CORRECT**.

**Reasoning:** According to the EPF Act [EPF_ACT_S6_CONTRIB], both the employee and employer must each contribute 12% of the employee's basic wages. The wage ceiling for mandatory EPF/EPS contributions is ₹15,000 per month [EPF_PARA_26A]. Since the basic salary is ₹25,000, which is above the wage ceiling, the EPF deduction of ₹3,000 matches the expected deduction of ₹3,000 [TOOL_PAYSLIP_AUDIT].

**Next Steps:**

1. Verify the EPF contribution details with your employer to ensure it matches the expected deduction.
2. Check if you have any other deductions or contributions that may be applicable.

**Warning:** Since the basic salary is above ₹15,000, you may be eligible to contribute on your full wages voluntarily. You can discuss this with your employer and submit a joint request to opt for voluntary contributions. [EPF_PARA_26A]
```

### payslip_02 — payslip/verify_epf
**Query:** Basic 18000 hai aur employer 1800 EPF kaat raha hai. ye sahi hai?
**Expected verdict:** incorrect  |  **Expected cites:** ['EPF_ACT_S6_CONTRIB', 'TOOL_PAYSLIP_AUDIT']

#### BASE  cites=['EPF_ACT_S6_CONTRIB']  fab=[]  verdict=False
```
**Result:** Not eligible for EPF contribution

**Reason:** Employer's EPF contribution of ₹1800 is less than the expected ₹2160 [EPF_ACT_S6_CONTRIB].

**Eligibility Condition:** The employer must contribute 12% of the employee's basic wages to the EPF account [EPF_ACT_S6_CONTRIB]. The expected EPF contribution for a basic salary of ₹18,000 is ₹2160, but the employer has deducted only ₹1800.

**Next Steps:** The employee should discuss this with their employer to rectify the under-deduction.

**Warning:** The employee may also want to check their ESI contribution, as the actual amount is not provided in the payslip audit result.
```
#### LoRA  cites=['EPF_ACT_S6_CONTRIB', 'EPF_PARA_26A']  fab=[]  verdict=True
```
**Result:** EPF under-deducted by ₹360.

**Eligibility:** Eligible for EPF contribution.

**Reasoning:** The employer is deducting ₹1800, which is less than the expected ₹2160 (12% of ₹18000) [EPF_ACT_S6_CONTRIB]. The statutory wage ceiling for EPF/EPS contributions is ₹15000 per month [EPF_PARA_26A], and the employee's basic salary is ₹18000, which exceeds this ceiling. However, the employee can voluntarily opt to contribute on their full wages by submitting a joint request with their employer [EPF_PARA_26A].

**Next Steps:**

1.  The employee should request their employer to increase the EPF deduction to ₹2160 per month.
2.  If the employee earns above ₹15000 per month, they can submit a joint request with their employer to contribute on their full wages.

**Warning/Caveat:** The employee's EPF contribution is under-deducted by ₹360, which may affect their retirement savings. It is recommended to rectify this issue as soon as possible.
```

### payslip_03 — payslip/verify_esi
**Query:** gross salary Rs 19000, ESI kat raha Rs 143 monthly. correct hai ya nahi?
**Expected verdict:** correct  |  **Expected cites:** ['ESI_WAGE_LIMIT', 'TOOL_PAYSLIP_AUDIT']

#### BASE  cites=['ESI_WAGE_LIMIT', 'TOOL_PAYSLIP_AUDIT']  fab=[]  verdict=True
```
**Result:** ESI deduction of ₹143 is correct.

**Reasoning:** The ESI scheme applies to employees with a gross salary of ₹21,000 or less [ESI_WAGE_LIMIT]. The employee's gross salary is ₹19,000, which is within the eligible limit.

**Steps:**

1. Check the employee's gross salary to ensure it is within the ESI wage limit.
2. Verify the ESI contribution rate, which is 0.75% of gross wages [TOOL_PAYSLIP_AUDIT].

**Warning/Caveat:** The Professional Tax (PT) deduction cannot be computed as the state is not provided.

**Eligibility:** Eligible (since the gross salary is within the ESI wage limit)

**Next Steps:** No further action required.
```
#### LoRA  cites=['ESI_WAGE_LIMIT', 'TOOL_PAYSLIP_AUDIT']  fab=[]  verdict=True
```
**Result:** ESI deduction of ₹143 is CORRECT.

**Eligibility:** Eligible (condition met)

**Reasoning:** The ESI scheme applies to employees whose gross salary is ₹21,000 per month or less [ESI_WAGE_LIMIT]. The user's gross salary is ₹19,000, which is within the eligible limit.

**Next Steps:**

1.  Verify the state to check if the Professional Tax (PT) deduction is correct.
2.  If the state is provided, re-run the payslip audit to check the PT deduction.

**Warning/Caveat:** The PT deduction cannot be computed without the state information [TOOL_PAYSLIP_AUDIT].
```

### payslip_04 — payslip/check_minimum_wage
**Query:** Maharashtra me unskilled worker hu, monthly 11000 rupees milta hai gross. minimum wage mil raha hai?
**Expected verdict:** incorrect  |  **Expected cites:** ['MIN_WAGE_MAHARASHTRA_2024']

#### BASE  cites=['MIN_WAGE_MAHARASHTRA_2024']  fab=[]  verdict=False
```
**Result:** Not eligible for minimum wage

**Reason:** Your gross salary of ₹11000 is less than the minimum wage of ₹14000 [MIN_WAGE_MAHARASHTRA_2024] for an unskilled worker in Maharashtra.

**Next Steps:**

1.  You should claim the difference between the minimum wage and your actual salary from your employer.
2.  Your employer must pay you the difference as a part of your salary.

**Warning:** Failure to pay the minimum wage is a criminal offence under Section 22 of the Minimum Wages Act [MIN_WAGE_MAHARASHTRA_2024].
```
#### LoRA  cites=['MIN_WAGE_MAHARASHTRA_2024']  fab=[]  verdict=False
```
**Result:** Not eligible for minimum wage

**Reason:** Your gross salary of ₹11000 is less than the statutory minimum wage of ₹14000 [MIN_WAGE_MAHARASHTRA_2024] for an unskilled worker in Maharashtra.

**Eligibility Condition:** The condition for eligibility is that the gross salary must be at least ₹14000 per month for an unskilled worker in Maharashtra.

**Next Steps:** You may consider discussing a salary increase with your employer to meet the statutory minimum wage requirements.

**Warning/Caveat:** Paying below the minimum wage is a criminal offence under Section 22 of the Minimum Wages Act [MIN_WAGE_MAHARASHTRA_2024].
```

### payslip_05 — payslip/full_audit
**Query:** Basic 20000, Gross 28000, Karnataka me. EPF kata 2400, ESI 0. Full audit karo.
**Expected verdict:** mixed  |  **Expected cites:** ['EPF_ACT_S6_CONTRIB', 'TOOL_PAYSLIP_AUDIT']

#### BASE  cites=['EPF_ACT_S6_CONTRIB', 'ESI_WAGE_LIMIT', 'PROF_TAX_KARNATAKA']  fab=[]  verdict=True
```
**Result:**

EPF deduction of ₹2,400 is **CORRECT** [EPF_ACT_S6_CONTRIB]. The employer's contribution to EPF is 12% of the employee's basic wages, which is ₹2,400 [EPF_ACT_S6_CONTRIB].

ESI deduction of ₹0 is **CORRECT** [ESI_WAGE_LIMIT]. The employee is not covered by ESI as their gross salary is ₹28,000, which exceeds the threshold of ₹21,000 [ESI_WAGE_LIMIT].

Professional Tax deduction of ₹150 is **CORRECT** [PROF_TAX_KARNATAKA]. The employer must deduct ₹150 as the employee's salary is ₹28,000, which falls under the slab of ₹15,000–29,999 [PROF_TAX_KARNATAKA].

**Next Steps:**

1. The EPF deduction of ₹2,400 is correct and matches the expected amount.
2. The ESI deduction of ₹0 is correct as the employee is not covered by ESI.
3. The Professional Tax deduction of ₹150 is correct and computed according to the Karnataka PT slab.

**Warnings/Caveats:**

* The employee's gross salary of ₹28,000 exceeds the EPF wage ceiling of ₹15,000 per month, but this does not affect the EPF deduction as the employee is still eligible for EPF [EPF_ACT_S6_CONTRIB].
* The employee is not covered by ESI due to their gross salary exceeding the threshold of ₹21,000 [ESI_WAGE_LIMIT].
```
#### LoRA  cites=['EPF_ACT_S6_CONTRIB', 'ESI_WAGE_LIMIT', 'PROF_TAX_KARNATAKA', 'TOOL_PAYSLIP_AUDIT']  fab=[]  verdict=False
```
**Result:**

Your payslip audit is complete. Here are the results:

* EPF deduction of ₹2,400 is **CORRECT** [EPF_ACT_S6_CONTRIB]. The legal basis is 12% of basic ₹20,000 = ₹2,400/month [EPF_ACT_S6_CONTRIB].
* ESI deduction of ₹0 is **CORRECT** [ESI_WAGE_LIMIT]. The legal basis is that ESI is not applicable since your gross salary ₹28,000 exceeds ₹21,000 [ESI_WAGE_LIMIT].
* Professional Tax deduction of ₹0 is **INCORRECT**. The expected PT is ₹150/month [TOOL_PAYSLIP_AUDIT]. The legal basis is the Karnataka PT slab: salary ≤ ₹29,999 → ₹150/month [PROF_TAX_KARNATAKA].

**Next Steps:**

1. Your employer should deduct ₹150/month as Professional Tax from your salary.
2. Please verify that your employer remits the deducted Professional Tax to the state government.

**Warnings/Caveats:**

* Since your gross salary is ₹28,000, you are not eligible for ESI [ESI_WAGE_LIMIT].
* The EPF deduction of ₹2,400 is within the legal limit of 12% of basic ₹20,000 [EPF_ACT_S6_CONTRIB].
```

### labour_01 — labour/gratuity
**Query:** Worked 6 years 3 months at a private company, resigned last month. Last drawn salary was Rs 45000. Am I eligible for gratuity and how much?
**Expected verdict:** eligible  |  **Expected cites:** ['GRATUITY_ACT_S4_ELIG']

#### BASE  cites=['GRATUITY_ACT_S4_ELIG']  fab=[]  verdict=True
```
**Eligibility:**

You are eligible for gratuity as you have completed more than 5 years of continuous service [GRATUITY_ACT_S4_ELIG].

**Calculation:**

To calculate the gratuity, we need to use the formula: (Last Drawn Monthly Salary × 15 × Years of Service) ÷ 26.

Given your last drawn salary is Rs 45,000, and you have worked for 6 years 3 months, we need to convert the years to months. 6 years is 72 months, and adding 3 months, you have a total of 75 months.

However, the formula requires years of service. To convert 75 months to years, we divide by 12: 75 months ÷ 12 = 6.25 years.

Now, let's calculate the gratuity:

(45,000 × 15 × 6.25) ÷ 26 = 28,359.62

**Result:**

You are eligible for a gratuity of approximately Rs 28,359.62.

**Next Steps:**

1.  Check with your employer to confirm the gratuity amount and the payment process.
2.  If your employer delays payment, you can claim simple interest at 10% per annum.

**Warning:**

The maximum gratuity payable is ₹20 Lakhs. If your calculated gratuity exceeds this amount, you will receive the maximum of ₹20 Lakhs.
```
#### LoRA  cites=['GRATUITY_ACT_S4_ELIG']  fab=[]  verdict=True
```
**Eligibility for Gratuity:**
You are eligible for gratuity as you have completed more than 5 years of continuous service [GRATUITY_ACT_S4_ELIG].

**Calculation of Gratuity:**
To calculate the gratuity, we use the formula: (Last Drawn Monthly Salary × 15 × Years of Service) ÷ 26.
Given your last drawn salary is Rs 45,000 per month, the calculation is:
(45,000 × 15 × 6) ÷ 26 = Rs 32,615

**Next Steps:**
1. Check if your employer has paid gratuity within 30 days of becoming due.
2. If not, calculate the interest payable at 10% per annum for any delay.
3. Ensure your employer has paid the maximum gratuity of Rs 20 Lakhs.

**Warning:** The employer must pay simple interest at 10% per annum for any delay in paying gratuity.
```

### labour_02 — labour/maternity_benefit
**Query:** 8 months pregnant, working at a private IT firm for 3 years. Manager said only 12 weeks leave allowed. Is that correct?
**Expected verdict:** informational  |  **Expected cites:** ['MATERNITY_BENEFIT_ACT_2017']

#### BASE  cites=['MATERNITY_BENEFIT_ACT_2017']  fab=[]  verdict=True
```
**Result:** Not eligible for 26 weeks of paid maternity leave.

**Reason:** The user is not eligible for 26 weeks of paid maternity leave because she has not completed the required 80 days of actual work in the 12 months preceding the expected delivery [MATERNITY_BENEFIT_ACT_2017].

**Eligibility Condition Trace:**
- The user is pregnant (given).
- The user has been working at a private IT firm for 3 years (given).
- The user needs to have worked for 80 days in the 12 months preceding the expected delivery, which is not specified.

**Next Steps:**
1. Check the user's employment records to confirm the number of days worked in the 12 months preceding the expected delivery.
2. If the user has worked for less than 80 days, she may be eligible for 12 weeks of paid maternity leave.

**Warning/Caveat:** The user should confirm her eligibility with her employer and ensure she understands the company's maternity leave policy.
```
#### LoRA  cites=['MATERNITY_BENEFIT_ACT_2017']  fab=[]  verdict=False
```
**Result:** You are eligible for 26 weeks of paid maternity leave.

**Eligibility Reasoning:**
- You are pregnant [MATERNITY_BENEFIT_ACT_2017].
- You have been working at the private IT firm for 3 years, which meets the eligibility criteria.
- You are entitled to 26 weeks of paid maternity leave for the first two live births [MATERNITY_BENEFIT_ACT_2017].

**Next Steps:**
1. Confirm your expected delivery date and calculate the 12 months preceding it to ensure you have 80 days of actual work.
2. Discuss your eligibility and benefits with your HR or manager to ensure they are aware of your entitlement.
3. If you have any concerns or issues, you can reach out to the Labour Department or a relevant authority for support.

**Warning/Caveat:** Ensure you have a record of your 80 days of actual work in the 12 months preceding your expected delivery to avoid any issues with your maternity benefit claim.
```

### labour_03 — labour/notice_period
**Query:** I want to resign immediately but my contract says 90 days notice period. Can I just pay basic salary and buy it out?
**Expected verdict:** conditional  |  **Expected cites:** ['NOTICE_PERIOD_BUYOUT_RULE']

#### BASE  cites=['NOTICE_PERIOD_BUYOUT_RULE']  fab=[]  verdict=True
```
**Result:** You can buy out the notice period, but with certain conditions.

**Eligibility:** eligible=True

**Reasoning:** According to [NOTICE_PERIOD_BUYOUT_RULE], an employer may allow a 'notice buy-out' when an employee resigns and is unable or unwilling to serve the full notice period. The amount to be paid is calculated as (Basic + DA) ÷ 30 × remaining notice days.

**Next Steps:**

1.  Check your employment contract or standing orders to confirm the notice period specified.
2.  Calculate the amount to be paid for the notice buy-out using the formula: (Basic + DA) ÷ 30 × remaining notice days.
3.  Discuss the notice buy-out with your employer and come to an agreement on the terms.

**Warning/Caveat:** The employer cannot withhold the full and final settlement solely because of a notice period dispute; any recovery must be through civil proceedings or agreed deduction from F&F.
```
#### LoRA  cites=['NOTICE_PERIOD_BUYOUT_RULE', 'STANDING_ORDERS_ACT_NOTICE_PERIOD']  fab=[]  verdict=True
```
**Result:** You cannot immediately pay basic salary and buy out the 90-day notice period.

**Eligibility:** eligible=False

**Reasoning:** According to the Industrial Employment (Standing Orders) Act 1946 [STANDING_ORDERS_ACT_NOTICE_PERIOD], if the contract specifies a longer notice period (e.g., 90 days), that contractual period applies. In your case, the contract requires a 90-day notice period. Additionally, the notice buy-out rule [NOTICE_PERIOD_BUYOUT_RULE] states that an employer cannot withhold the full and final settlement solely because of a notice period dispute; any recovery must be through civil proceedings or agreed deduction from F&F.

**Warning:** You may be required to serve the full 90-day notice period or face pay deduction for the shortfall. If you are unable or unwilling to serve the full notice period, you may need to negotiate with your employer to agree on a notice buy-out or seek civil proceedings to resolve the dispute.

**Next Steps:** Review your employment contract and discuss with your employer to explore options for resolving the notice period dispute. If necessary, consider seeking legal advice to understand your rights and obligations.
```

### labour_04 — labour/wrongful_termination
**Query:** HR fired me suddenly yesterday without any notice period pay or warning, and they are holding my relieving letter. What are my rights?
**Expected verdict:** informational  |  **Expected cites:** ['WRONGFUL_TERMINATION_REMEDIES', 'RELIEVING_LETTER_LEGAL_OBLIGATION']

#### BASE  cites=['RELIEVING_LETTER_LEGAL_OBLIGATION', 'STANDING_ORDERS_ACT_NOTICE_PERIOD', 'WRONGFUL_TERMINATION_REMEDIES']  fab=[]  verdict=True
```
**Eligibility:** eligible=True

**Result:** You have several remedies for wrongful termination. Since you were fired without a notice period, you can consider the following options:

1.  You can raise an industrial dispute before the Labour Commissioner, and if unresolved, before the Labour Court, which can award reinstatement with back wages [WRONGFUL_TERMINATION_REMEDIES].
2.  You can file a complaint under the Industrial Disputes Act within 3 years of the wrongful termination [WRONGFUL_TERMINATION_REMEDIES].
3.  If your employer is in an 'essential service', different notice requirements may apply [WRONGFUL_TERMINATION_REMEDIES].

**Next Steps:**

1.  Gather all relevant documents, including your offer letter or contract, to determine the notice period specified.
2.  Check if your employer has certified standing orders that specify the notice period required for termination [STANDING_ORDERS_ACT_NOTICE_PERIOD].
3.  If you believe your employer has wrongfully terminated you, consider filing a complaint with the Labour Commissioner or a civil suit for recovery of the relieving letter [RELIEVING_LETTER_LEGAL_OBLIGATION].

**Warning:** Filing a complaint or lawsuit can be a lengthy and complex process. It is recommended that you consult with a legal expert or a labour rights organization for guidance.

**Caveat:** The Industrial Disputes Act requires that you file a complaint within 3 years of the wrongful termination [WRONGFUL_TERMINATION_REMEDIES].
```
#### LoRA  cites=['RELIEVING_LETTER_LEGAL_OBLIGATION', 'STANDING_ORDERS_ACT_NOTICE_PERIOD', 'WRONGFUL_TERMINATION_REMEDIES']  fab=[]  verdict=True
```
**Result:**
You are eligible to take action against your employer for wrongful termination.

**Eligibility Reasoning:**
You were terminated by your employer without any notice period pay or warning, which is a wrongful termination [WRONGFUL_TERMINATION_REMEDIES].

**Next Steps:**
1.  You can raise an industrial dispute before the Labour Commissioner, and if unresolved, before the Labour Court, which can award reinstatement with back wages [WRONGFUL_TERMINATION_REMEDIES].
2.  You can also approach the Labour Commissioner or file a civil suit for recovery of the relieving letter, as withholding it may be challenged as restraint of trade under Section 27 of the Indian Contract Act 1872 [RELIEVING_LETTER_LEGAL_OBLIGATION].
3.  If you were a permanent workman, your employer may have breached the Industrial Employment (Standing Orders) Act 1946 by not providing the agreed notice period, which is typically 30 days [STANDING_ORDERS_ACT_NOTICE_PERIOD].

**Warnings/Caveats:**
- You must file a complaint under the Industrial Disputes Act within 3 years of the wrongful termination [WRONGFUL_TERMINATION_REMEDIES].
- If your employer is in an 'essential service', different notice requirements may apply [WRONGFUL_TERMINATION_REMEDIES].
- You may need to approach civil courts or the High Court if you are a managerial or supervisory employee [WRONGFUL_TERMINATION_REMEDIES].
```

### labour_05 — labour/gratuity
**Query:** I completed 4 years and 245 days in my current company. Will I get gratuity? I heard about some Madras High court ruling.
**Expected verdict:** conditional  |  **Expected cites:** ['GRATUITY_COURT_RULING_4Y8M']

#### BASE  cites=['GRATUITY_ACT_S4_ELIG', 'GRATUITY_COURT_RULING_4Y8M']  fab=[]  verdict=True
```
**Eligibility: False**

You are not eligible for gratuity as you have completed only 4 years and 245 days of service, which does not meet the minimum requirement of 5 years of continuous service [GRATUITY_ACT_S4_ELIG]. The Madras High Court ruling [GRATUITY_COURT_RULING_4Y8M] provides a judicial interpretation that an employee with 4 years and 240 days of service qualifies for gratuity, but this does not apply to your situation since you have not completed the required 5 years.

**Why not eligible:** The Payment of Gratuity Act 1972 requires a minimum of 5 years of continuous service for gratuity to be payable. You have completed 4 years and 245 days, which is less than the required period.

**Next steps:** You may consider reviewing your employment contract or consulting with your HR department to understand the company's gratuity policy. If you have any further questions or concerns, you may also consider reaching out to the Labour Department or a relevant authority for guidance.

**Caveat:** The Madras High Court ruling [GRATUITY_COURT_RULING_4Y8M] is specific to certain conditions and may not be applicable in all cases. It's essential to consult the relevant laws and regulations for accurate information.
```
#### LoRA  cites=['GRATUITY_ACT_S4_ELIG', 'GRATUITY_COURT_RULING_4Y8M']  fab=[]  verdict=True
```
**Result:** Eligible for gratuity

**Reasoning:** Based on the Madras High Court ruling [GRATUITY_COURT_RULING_4Y8M], an employee who completes 4 years and 240 days (or more) of service qualifies for gratuity. Since you have completed 4 years and 245 days, you meet this threshold.

**Eligibility Condition:** The condition for gratuity eligibility is met when an employee completes 4 years and 240 days (or more) of service [GRATUITY_COURT_RULING_4Y8M].

**Next Steps:**

1.  Calculate your gratuity using the formula: (Last Drawn Monthly Salary × 15 × Years of Service) ÷ 26.
2.  Ensure your employer pays gratuity within 30 days of becoming due and pays simple interest at 10% per annum for any delay [GRATUITY_ACT_S4_ELIG].
3.  Review your employment contract to understand the terms and conditions related to gratuity.

**Warning/Caveat:** Gratuity is payable only on termination of service, and the amount is subject to a maximum of ₹20 Lakhs. If you have any doubts or concerns, consider consulting with a labour law expert.
```

### tax_01 — tax/deductions_80c
**Query:** Chose new tax regime this FY. Invested 1.5 lakh in PPF. Can I claim 80C deduction?
**Expected verdict:** not applicable  |  **Expected cites:** ['ITA_SECTION_80C', 'FINANCE_ACT_2023_NEW_REGIME']

#### BASE  cites=['FINANCE_ACT_2023_NEW_REGIME']  fab=[]  verdict=False
```
**Result:** Not eligible for 80C deduction

**Reason:** The new tax regime is the default for individuals from FY 2023-24 onward, and the 80C deduction is not available under this regime [FINANCE_ACT_2023_NEW_REGIME].

**Condition Trace:** The user chose the new tax regime, and the new tax regime does not offer the 80C deduction.

**Next Steps:** Consider other deductions available under the new tax regime, such as the standard deduction of ₹50,000 or the tax rebate under Section 87A.

**Warning/Caveat:** The new tax regime has different tax slabs and deductions compared to the old tax regime. It's essential to understand the new rules to optimize tax savings.
```
#### LoRA  cites=['FINANCE_ACT_2023_NEW_REGIME', 'ITA_SECTION_80C']  fab=[]  verdict=False
```
**Result:** Not eligible for 80C deduction

**Reason:** You have chosen the new tax regime, which does not allow the 80C deduction [ITA_SECTION_80C].

**Eligibility Condition:** The new tax regime is the default for individuals from FY 2023-24 onward, and the 80C deduction is not available under this regime [FINANCE_ACT_2023_NEW_REGIME].

**Next Steps:** You can consider other tax-saving options available under the new tax regime, such as the standard deduction of ₹50,000 and the tax rebate of up to ₹25,000 under Section 87A if your total income does not exceed ₹7 lakh.

**Warning/Caveat:** It's essential to review the tax slabs and deductions available under the new tax regime to optimize your tax savings. Consult a tax professional if you have any further queries.
```

### tax_02 — tax/hra_exemption
**Query:** Paying Rs 18000 rent in Bangalore, basic salary 40000, HRA received 15000. HRA exemption kitna milega?
**Expected verdict:** informational  |  **Expected cites:** ['ITA_SECTION_10_13A']

#### BASE  cites=[]  fab=[]  verdict=True
```
**Result:**
HRA exemption of ₹15,000 can be claimed.

**Steps:**

1. Calculate the exemption under Section 10(13A) of the Income Tax Act.
2. The exemption is the minimum of three amounts:
   - Actual HRA received from employer: ₹15,000
   - Rent paid minus 10% of basic salary: ₹18,000 - (10% of ₹40,000) = ₹18,000 - ₹4,000 = ₹14,000
   - 50% of basic salary for non-metro cities: 50% of ₹40,000 = ₹20,000
3. Since ₹14,000 is the minimum of the three amounts, the HRA exemption is ₹14,000. However, the actual HRA received is ₹15,000, which is higher than the calculated exemption. Therefore, the HRA exemption of ₹15,000 can be claimed.

**Warnings/Caveats:**

* The HRA exemption is available only under the old tax regime. If the tax regime is new, HRA exemption cannot be claimed.
* If rent paid exceeds ₹1 lakh per annum, the landlord's PAN must be provided to the employer.
```
#### LoRA  cites=['ITA_SECTION_10_13A']  fab=[]  verdict=True
```
**Result:** HRA exemption of ₹15,000 is available.

**Steps:**

1. Calculate the HRA exemption using the formula: minimum of actual HRA received, rent paid minus 10% of basic salary, and 40% of basic salary.
2. Rent paid: ₹18,000
3. 10% of basic salary: ₹4,000 (10% of ₹40,000)
4. 40% of basic salary: ₹16,000 (40% of ₹40,000)
5. Actual HRA received: ₹15,000
6. HRA exemption: minimum of ₹15,000, ₹18,000 - ₹4,000 = ₹14,000, and ₹16,000 [ITA_SECTION_10_13A]

**Warnings/Caveats:** Ensure the landlord's PAN is provided to the employer if rent paid exceeds ₹1 lakh per annum. This exemption is only available under the old tax regime. Employees under the new tax regime cannot claim HRA exemption. [ITA_SECTION_10_13A]
```

### tax_03 — tax/refund_status
**Query:** My ITR refund is delayed by over 4 months now. Portal shows processed but no money. I don't have any outstanding demand.
**Expected verdict:** informational  |  **Expected cites:** ['ITR_REFUND_DELAY_GRIEVANCE']

#### BASE  cites=['ITR_REFUND_DELAY_GRIEVANCE', 'ITR_REFUND_STATUS']  fab=[]  verdict=True
```
**Result:** Your ITR refund is likely delayed due to a possible issue with your bank account or a mismatch in PAN-bank account details.

**Eligibility:** eligible=True

**Next Steps:**

1. Check your bank account on the IT portal under 'My Profile > Bank Account' to ensure it is pre-validated.
2. Verify that your bank account IFSC has not been changed or closed.
3. If your PAN-bank account details are mismatched, pre-validate your bank account on the IT portal.

**Warning/Caveat:** If your refund is not credited within 45 days of ITR processing, you can escalate through the steps mentioned in [ITR_REFUND_DELAY_GRIEVANCE].

**Citations:**

* Refund processing and delay: [ITR_REFUND_STATUS]
* Bank account validation: [ITR_REFUND_STATUS]
* PAN-bank account mismatch: [ITR_REFUND_STATUS]
* Refund delay escalation: [ITR_REFUND_DELAY_GRIEVANCE]
* Refund interest accrual: [ITR_REFUND_DELAY_GRIEVANCE]
```
#### LoRA  cites=['ITR_REFUND_DELAY_GRIEVANCE', 'ITR_REFUND_OUTSTANDING_DEMAND', 'ITR_REFUND_STATUS']  fab=[]  verdict=True
```
**Result:** Your ITR refund is likely delayed due to a common issue.

**Eligibility:** Eligible for refund (assuming no outstanding demand)

**Reasoning Trace:** Since you don't have any outstanding demand, the refund should have been processed by now. However, the refund status shows processed but no money has been credited.

**Steps to resolve:**

1.  Check the refund status on the NSDL portal at tin.tin.nsdl.com to confirm the processing status.
2.  Verify that your bank account is pre-validated on the IT portal under 'My Profile > Bank Account'. If not, pre-validate it to ensure the refund is credited correctly.
3.  If the bank account IFSC has changed or closed, update it on the IT portal to avoid any issues.
4.  If the refund is still not credited after 45 days, you can escalate the issue by raising a grievance on the e-filing portal under 'e-Nivaran / Grievance' with the processing reference number.

**Warnings/Caveats:** Refunds are typically credited within 20–45 days of ITR processing [ITR_REFUND_STATUS]. If the refund is not credited within 45 days, you can escalate the issue through the steps mentioned above [ITR_REFUND_DELAY_GRIEVANCE]. Additionally, if there is an outstanding tax demand, the refund may be adjusted against it [ITR_REFUND_OUTSTANDING_DEMAND]. However, since you don't have any outstanding demand, this is not applicable in your case.
```

### tax_04 — tax/tds_on_pf
**Query:** Withdrawing total 4 lakhs from PF after 3.5 years of service. PAN card is updated in UAN. What is the exact TDS percentage?
**Expected verdict:** informational  |  **Expected cites:** ['ITA_SECTION_192A_TDS_PF']

#### BASE  cites=['ITA_SECTION_192A_TDS_PF']  fab=[]  verdict=True
```
**Result:**
You are eligible for TDS on PF withdrawal.

**Reasoning:**
Since your service years (3) are less than 5 years, and the withdrawal amount (₹400,000) exceeds ₹50,000, TDS is applicable.

**TDS Percentage:**
As your PAN card is updated in UAN, the TDS rate is 10% [ITA_SECTION_192A_TDS_PF].

**Next Steps:**
1. Check if you have submitted Form 15G/15H, as this might exempt you from TDS.
2. Ensure you have the necessary documents ready for the PF withdrawal process.

**Caveat:**
If you had 5 or more years of service, the TDS would not apply.
```
#### LoRA  cites=['ITA_SECTION_192A_TDS_PF']  fab=[]  verdict=True
```
**Result**
You are eligible for TDS on PF withdrawal.

**TDS Percentage**
The TDS percentage for your PF withdrawal is 10% as you have provided a valid PAN card and your service period is less than 5 years [ITA_SECTION_192A_TDS_PF].

**Next Steps**
1. Submit your PF withdrawal claim to your employer or the EPFO.
2. Ensure that your PAN card details are correctly updated in your UAN.

**Warning/Caveat**
Note that if your service period was 5 years or more, no TDS would have been applicable [ITA_SECTION_192A_TDS_PF]. Additionally, if you had not provided a valid PAN card, the TDS percentage would have been 20% [ITA_SECTION_192A_TDS_PF].
```

### tax_05 — tax/form16
**Query:** Resigned in September. I asked for Form 16 for my part-year salary but HR says they will give it only next year in June. Is this allowed?
**Expected verdict:** informational  |  **Expected cites:** ['FORM_16_OVERVIEW']

#### BASE  cites=['FORM_16_OVERVIEW']  fab=[]  verdict=True
```
**Result:** Not eligible to receive Form 16 for part-year salary immediately.

**Eligibility:** eligible=False

**Reason:** According to [FORM_16_OVERVIEW], Form 16 is issued by the employer by 15 June of the assessment year. Since you resigned in September, the assessment year has not started yet, and the employer is not required to issue Form 16 immediately.

**Warning:** The employer can be penalised under Section 272A if they fail to issue Form 16. You can still file ITR using Form 26AS, pay slips, and bank statements.

**Next Steps:** You can wait until the assessment year starts and the employer issues Form 16 by 15 June. If you need to file ITR before that, you can use Form 26AS, pay slips, and bank statements as alternatives.
```
#### LoRA  cites=['FORM_16_OVERVIEW']  fab=[]  verdict=True
```
**Result:** Not eligible for Form 16 for part-year salary

**Eligibility Reasoning Trace:** 
- The user resigned in September, which is within the same financial year.
- Form 16 is issued by the employer by 15 June of the assessment year.
- Since the user resigned in September, the employer is not required to issue Form 16 for the part-year salary.

**Answer:** According to the tax laws, an employer is not required to issue Form 16 for a part-year salary [FORM_16_OVERVIEW]. The employer's decision to provide Form 16 only in June of the next year is not in compliance with the tax laws, but it is not a violation of any specific rule. However, the employer can be penalised under Section 272A for failing to issue Form 16 [FORM_16_OVERVIEW].

**Next Steps:**

1.  Request the employer to provide a partial Form 16 or a separate document showing the TDS deposited and salary breakup for the part-year salary.
2.  File the Income Tax Return (ITR-1 or ITR-2) using Form 26AS, pay slips, and bank statements as alternative documents.

**Warning/Caveat:** The employer's delay in issuing Form 16 may cause inconvenience while filing the ITR. It is recommended to keep a record of all communication with the employer regarding the Form 16.
```
