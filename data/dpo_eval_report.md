# Stage 2.3 — DPO Held-out Evaluation Report

- Prompts: 20
- Systems: SFT-only + 3 DPO betas (0.05, 0.10, 0.20)
- Winner: **dpo_beta_0.05**

## Summary

| Metric | sft_only | dpo_beta_0.05 | dpo_beta_0.10 | dpo_beta_0.20 |
|---|---|---|---|---|
| citation_coverage | 1.000 | 1.000 | 1.000 | 1.000 |
| fabrication_rate | 0.000 | 0.000 | 0.000 | 0.050 |
| expected_cites_hit | 0.800 | 0.850 | 0.750 | 0.700 |
| verdict_accuracy | 0.650 | 0.750 | 0.750 | 0.750 |
| grounded_clean | 0.650 | 0.750 | 0.750 | 0.700 |
| key_facts_mean | 0.675 | 0.775 | 0.725 | 0.700 |
| fabrication_count | 0 | 0 | 0 | 1 |

## Per-domain grounded_clean

| Domain | sft_only | dpo_beta_0.05 | dpo_beta_0.10 | dpo_beta_0.20 |
|---|---|---|---|---|
| pf | 0.40 | 0.40 | 0.40 | 0.40 |
| payslip | 0.60 | 0.80 | 0.80 | 0.60 |
| labour | 0.80 | 1.00 | 1.00 | 1.00 |
| tax | 0.80 | 0.80 | 0.80 | 0.80 |

## Side-by-side samples

### pf_01 — pf/full_withdrawal
**Query:** resign kiye 4 mahine ho gaye, UAN active hai, KYC complete hai. total 7 saal kaam kiya pf me. pura paisa nikal sakta hu?

**Expected verdict:** eligible
**Expected cites:** ['FAQ_WD_023', 'CIRC_2024_TDS']

#### sft_only  cites=['CIRC_2024_TDS', 'FAQ_WD_023']  fab=[]  verdict=True
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

#### dpo_beta_0.05  cites=['CIRC_2024_TDS', 'FAQ_WD_023']  fab=[]  verdict=True
```
**Result:** You are eligible for full PF withdrawal.

**Eligibility Reasoning Trace:**
- You have been unemployed for 4 months [FAQ_WD_023].
- You have completed 7 years of service [FAQ_WD_023].
- Your UAN is active and KYC is complete [FAQ_WD_023].
- You are eligible for full withdrawal as you have completed 5 years of service [CIRC_2024_TDS].

**Next Steps:**
1. You can submit your withdrawal application without employer attestation by getting it attested from the bank where you maintain your account and submitting it to the Regional PF Commissioner [FAQ_WD_023].
2. Alternatively, you can submit a composite claim (Aadhaar) which only requires your signature, if you have activated your UAN and linked your bank account and Aadhaar [FAQ_WD_023].

**Warnings/Caveats:** None.
```

#### dpo_beta_0.10  cites=['CIRC_2024_TDS', 'FAQ_WD_023']  fab=[]  verdict=True
```
**Result:** You are eligible for full PF withdrawal.

**Eligibility Reasoning Trace:**
- You have been unemployed for 4 months [FAQ_WD_023].
- You have completed 7 years of service [FAQ_WD_023].
- Your UAN is active and KYC is complete [FAQ_WD_023].
- You are eligible for full withdrawal as you have completed 5 years of service [CIRC_2024_TDS].

**Next Steps:**
1. You can submit your withdrawal application without the employer's signature by getting attestation from the bank where you maintain your account and submitting it to the Regional PF Commissioner [FAQ_WD_023].
2. Alternatively, you can submit a composite claim (Aadhaar) which only requires your signature, if you have activated your UAN and linked your bank account and Aadhaar [FAQ_WD_023].

**Warnings/Caveats:** None.
```

#### dpo_beta_0.20  cites=['CIRC_2024_TDS', 'FAQ_WD_023']  fab=[]  verdict=True
```
**Result:** You are eligible for full PF withdrawal.

**Eligibility Reasoning Trace:**
- You have been unemployed for 4 months [FAQ_WD_023].
- You have completed 7 years of service [FAQ_WD_023].
- Your UAN is active and KYC is complete [FAQ_WD_023].

**Steps:**
1. Since you have completed 7 years of service, you are eligible for full PF withdrawal.
2. You can submit the withdrawal application without the employer's signature by getting attestation from the bank where you maintain your account and submitting it to the Regional PF Commissioner [FAQ_WD_023].
3. Alternatively, you can submit a composite claim (Aadhaar) which only requires your signature, if you have activated your UAN and linked your bank account and Aadhaar [FAQ_WD_023].

**Warnings/Caveats:** None.

**TDS Information:** Since you have completed 7 years of service, no TDS will be applicable on your withdrawal [CIRC_2024_TDS].
```

### pf_02 — pf/full_withdrawal
**Query:** I resigned just last month, worked for 3 years total. UAN is active, KYC done. Can I withdraw my PF fully now?

**Expected verdict:** not eligible
**Expected cites:** ['FAQ_WD_023']

#### sft_only  cites=['CIRC_2024_TDS']  fab=[]  verdict=False
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

#### dpo_beta_0.05  cites=['CIRC_2024_TDS', 'FAQ_WD_023']  fab=[]  verdict=False
```
**Result:** You are eligible to withdraw your PF fully.

**Eligibility Reasoning Trace:**
- You have been unemployed for 1 month, which is less than 2 months ( typical waiting period for full withdrawal).
- Your service period is 3 years, which meets the minimum requirement for full withdrawal.
- Your UAN is active and KYC is complete, allowing you to submit a composite claim.

**Steps:**

1.  You can submit a composite claim (Aadhaar) for full withdrawal as you have activated your UAN and linked your bank account and Aadhaar [FAQ_WD_023].
2.  Since you have been unemployed for less than 2 months, you do not need to wait for the typical 2-month waiting period for full withdrawal.
3.  As you have completed 3 years of service, you are eligible for full withdrawal without any service restrictions.

**Warnings/Caveats:** 
- Be aware that TDS may apply if your withdrawal exceeds Rs.50,000 and you have not completed 5 years of service [CIRC_2024_TDS]. However, since you have only 3 years of service, TDS will be applicable if your withdrawal exceeds Rs.50,000.
- Ensure you have a valid PAN to avoid a higher TDS rate of 20% if you are a resident without a valid PAN [CIRC_2024_TDS].
```

#### dpo_beta_0.10  cites=['CIRC_2024_TDS']  fab=[]  verdict=False
```
**Result:** You are eligible to withdraw your PF fully.

**Eligibility Reasoning Trace:**
- You have been unemployed for 1 month, which is less than 2 months ( typical waiting period for full withdrawal).
- Your UAN is active and KYC is complete.
- You have completed 3 years of service.

**Steps:**

1.  You can submit your full withdrawal application using the composite claim (Aadhaar) option, as your UAN is active and KYC is complete.
2.  You will need to get your bank account details attested by the bank where you maintain your account, as your employer has not attested the claim form.

**Warnings/Caveats:**
- Be aware that if your withdrawal exceeds Rs.50,000, TDS may be applicable if your service is less than 5 years. However, since you have completed 3 years of service, TDS will not be applicable in your case [CIRC_2024_TDS].
- Ensure you have a valid PAN to avoid a higher TDS rate of 20% [CIRC_2024_TDS].
```

#### dpo_beta_0.20  cites=['CIRC_2024_TDS']  fab=[]  verdict=False
```
**Result:** You are eligible to withdraw your PF fully.

**Eligibility Reasoning Trace:**
- You have been unemployed for 1 month, which is less than 2 months ( typical waiting period for full withdrawal).
- Your UAN is active and KYC is complete.
- You have completed 3 years of service.

**Steps:**

1.  You can submit your full withdrawal application using the composite claim (Aadhaar) option, as your UAN is active and KYC is complete.
2.  You will need to get your bank account details attested by the bank where you maintain your account, as your employer has not attested the claim form.

**Warnings/Caveats:**
- Be aware that if your withdrawal exceeds Rs.50,000, TDS may be applicable if your service is less than 5 years. However, since you have completed 3 years of service, TDS will not be applicable in your case [CIRC_2024_TDS].
- Ensure you have a valid PAN to avoid a higher TDS rate of 20% [CIRC_2024_TDS].
```

### pf_03 — pf/tds_query
**Query:** pf withdraw kiya 2 lakh ka, total service 3.5 years thi. TDS kitna lagega?

**Expected verdict:** conditional
**Expected cites:** ['CIRC_2024_TDS']

#### sft_only  cites=['CIRC_2024_TDS', 'FORM_15G_INSTRUCTIONS']  fab=[]  verdict=True
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

#### dpo_beta_0.05  cites=['CIRC_2024_TDS', 'FORM_15G_INSTRUCTIONS']  fab=[]  verdict=True
```
**Result:** TDS applicable

**Eligibility:** Not eligible for exemption (service < 5 years)

**Reasoning:** TDS is applicable if service is less than 5 years and withdrawal exceeds Rs.50,000 [CIRC_2024_TDS]. The user has 3 years of service, which is less than 5 years.

**Next Steps:**

1.  The user needs to provide their PAN to avoid TDS as a resident.
2.  If the user does not have a PAN, they will be charged 20% TDS [CIRC_2024_TDS].
3.  If the user is a non-resident, they will be charged 30% plus 4% cess [CIRC_2024_TDS].

**Warning:** The user may be able to avoid TDS by submitting Form 15G, but they must meet the eligibility criteria: age below 60 and total income below Rs.2.50 lakh [FORM_15G_INSTRUCTIONS]. However, this is not possible in this case since the user's service is less than 5 years.
```

#### dpo_beta_0.10  cites=['CIRC_2024_TDS', 'FORM_15G_INSTRUCTIONS']  fab=[]  verdict=True
```
**Result:** TDS applicable on your PF withdrawal of Rs. 2,00,000.

**Eligibility:** Not eligible for exemption (service < 5 years)

**Reasoning:** According to [CIRC_2024_TDS], TDS is applicable if service is less than 5 years and withdrawal exceeds Rs. 50,000. You have served for 3 years, which is less than 5 years.

**TDS Rate:** As a resident with valid PAN, you will be charged 10% TDS [CIRC_2024_TDS].

**Next Steps:**

1.  File your income tax return to claim TDS credit.
2.  Ensure you have a valid PAN to avoid higher TDS rates.

**Warning:** If you had submitted Form 15G to avoid TDS, it would not be applicable in this case since your service is less than 5 years [FORM_15G_INSTRUCTIONS].
```

#### dpo_beta_0.20  cites=['CIRC_2024_TDS', 'FORM_15G_INSTRUCTIONS']  fab=[]  verdict=True
```
**Result:** TDS applicable on your PF withdrawal of Rs. 2,00,000.

**Eligibility:** Not eligible for exemption from TDS.

**Reasoning:** Your service period is 3.5 years, which is less than 5 years [CIRC_2024_TDS]. The withdrawal amount exceeds Rs. 50,000, so TDS is applicable.

**TDS Rate:** As a resident with valid PAN, you will be charged 10% TDS [CIRC_2024_TDS].

**Next Steps:**

1.  File your income tax return to claim TDS credit.
2.  Ensure you have a valid PAN to avoid a higher TDS rate.

**Warning:** If you had submitted Form 15G, you may be eligible for exemption from TDS. However, since you did not mention submitting Form 15G, we cannot confirm its validity. If you have submitted Form 15G, please check if you meet the eligibility criteria: age below 60 and total income below Rs. 2.50 lakh [FORM_15G_INSTRUCTIONS].
```

### pf_04 — pf/transfer
**Query:** new company join kiya, old PF ka transfer karna hai. UAN active hai KYC done hai. kaise transfer hoga?

**Expected verdict:** informational
**Expected cites:** ['FAQ_WD_024', 'FORM_13_INSTRUCTIONS']

#### sft_only  cites=['CIRC_UAN_AUTO_TRANSFER', 'FAQ_WD_024']  fab=[]  verdict=False
```
**Result:** Your PF account can be transferred to the new establishment on change of employment.

**Eligibility:** Eligible (conditions met: UAN active [FAQ_WD_024], KYC complete [FAQ_WD_024])

**Steps:**

1.  Submit Form 13(R) or online transfer request through the member interface at the unified portal to transfer your PF account to the new establishment.
2.  If you have an active UAN and Aadhaar+Bank seeded, you can also submit the transfer claim online using the member interface.

**Warnings/Caveats:** Ensure your Date of Exit is updated in your previous account to facilitate the transfer process. If you have an active UAN and Aadhaar verification, your transfer may initiate automatically when the first month contribution is received in the new account from the new employer [CIRC_UAN_AUTO_TRANSFER].
```

#### dpo_beta_0.05  cites=['CIRC_UAN_AUTO_TRANSFER', 'FAQ_WD_024', 'FORM_13_INSTRUCTIONS']  fab=[]  verdict=False
```
**Result:** Your PF account can be transferred to the new establishment.

**Eligibility:** Eligible (conditions met: UAN active, KYC complete)

**Next Steps:**

1.  Submit Form 13(R) or online transfer request through the member interface at the unified portal.
2.  If you have an active UAN and Aadhaar is seeded, you may be eligible for auto-transfer. However, this requires the first month contribution to be received in the new account from the new employer.

**Warnings/Caveats:** Ensure your Date of Exit is updated in the previous account to facilitate transfer. If you have any issues with the online transfer process, you can submit a physical Form 13. [FAQ_WD_024] [FORM_13_INSTRUCTIONS] [CIRC_UAN_AUTO_TRANSFER]
```

#### dpo_beta_0.10  cites=['CIRC_UAN_AUTO_TRANSFER', 'FAQ_WD_024', 'FORM_13_INSTRUCTIONS']  fab=[]  verdict=False
```
**Result:** Your PF account can be transferred to the new establishment.

**Eligibility:** Eligible (conditions met: UAN active, KYC complete)

**Next Steps:**

1.  Submit Form 13(R) or online transfer request through the member interface at the unified portal.
2.  If you have an active UAN and Aadhaar is seeded, you may be eligible for auto-transfer. However, this requires the first month contribution to be received in the new account from the new employer.

**Warnings/Caveats:** Ensure your Date of Exit is updated in the previous account to facilitate transfer. If you have any issues with the online transfer process, you can submit a physical Form 13.

**Citation:** [FAQ_WD_024], [FORM_13_INSTRUCTIONS], [CIRC_UAN_AUTO_TRANSFER]
```

#### dpo_beta_0.20  cites=['CIRC_UAN_AUTO_TRANSFER', 'FAQ_WD_024', 'FORM_13_INSTRUCTIONS']  fab=[]  verdict=False
```
**Result:** Your PF account can be transferred to the new establishment.

**Eligibility:** Eligible (conditions met: UAN active, KYC complete)

**Next Steps:**

1.  Submit Form 13(R) or online transfer request through the member interface at the unified portal.
2.  If you have already updated your Date of Exit, you can initiate the transfer online using the online services.

**Warning/Caveats:** Ensure your UAN is activated, Aadhaar and bank details are seeded, and your Date of Exit is updated for online transfer. If you have already updated your Date of Exit, you can initiate the transfer online without submitting a physical Form 13.

**Citation:** [FAQ_WD_024], [FORM_13_INSTRUCTIONS], [CIRC_UAN_AUTO_TRANSFER]
```

### pf_05 — pf/kyc_issue
**Query:** KYC rejected dikha raha EPFO portal pe. Aadhaar aur PAN me name mismatch hai. kya kare?

**Expected verdict:** informational
**Expected cites:** ['FAQ_CLAIM_133']

#### sft_only  cites=['KYC_AADHAAR_GUIDE']  fab=[]  verdict=False
```
**Result:** KYC rejection ka samadhan karna hai.

**Eligibility:** Eligible (kyunki aap UAN me login kar sakte hain)

**Steps:**

1. Aapko apne UAN me login karna hoga.
2. Member portal par jaakar, Manage > KYC > Select Aadhaar > Enter Aadhaar number > Save karna hoga.
3. Agar name mismatch hai, to Joint Declaration kiya jaana hoga.

**Caveats:** Name mismatch ke liye Joint Declaration kiya jaana hoga, isliye aapko apne employer se saath me milna hoga. [KYC_AADHAAR_GUIDE]
```

#### dpo_beta_0.05  cites=['KYC_AADHAAR_GUIDE']  fab=[]  verdict=False
```
**Result:** KYC correction is possible, but name mismatch requires a joint declaration.

**Eligibility:** eligible=True

**Steps:**

1.  Login to the EPFO UAN portal.
2.  Update KYC by uploading necessary documents online.
3.  If name mismatch, use Method 2: e-KYC Portal on EPFO website or UMANG app for self-validation without employer approval. However, if the details do not match exactly, a joint declaration is required.

**Warnings/Caveats:** Name mismatch requires additional documentation (joint declaration). Ensure all necessary documents are uploaded and approved by the employer for successful KYC correction. [KYC_AADHAAR_GUIDE]
```

#### dpo_beta_0.10  cites=['KYC_AADHAAR_GUIDE']  fab=[]  verdict=False
```
**Result:** KYC correction is possible, but name mismatch requires a joint declaration.

**Eligibility:** eligible=True

**Steps:**

1.  Login to the EPFO UAN portal.
2.  Update KYC by uploading necessary documents online.
3.  If name mismatch, use Method 2: e-KYC Portal on EPFO website or UMANG app for self-validation without employer approval. However, if the details do not match exactly, a joint declaration is required.

**Warnings/Caveats:** Name mismatch requires additional documentation (joint declaration). Ensure all necessary documents are uploaded and approved by the employer for successful KYC correction. [KYC_AADHAAR_GUIDE]
```

#### dpo_beta_0.20  cites=['KYC_AADHAAR_GUIDE']  fab=[]  verdict=False
```
**Result:** KYC correction is possible, but name mismatch requires a joint declaration.

**Steps:**

1.  Login to the EPFO UAN portal.
2.  Update KYC by uploading necessary documents online.
3.  If name mismatch is the issue, use Method 2: e-KYC Portal on EPFO website or UMANG app for self-validation without employer approval. However, if the details do not match exactly, a joint declaration is required.

**Warnings/Caveats:** For name mismatch, a joint declaration is necessary, which may require additional documentation and employer approval. Ensure you have the necessary documents before proceeding. [KYC_AADHAAR_GUIDE]
```

### payslip_01 — payslip/verify_epf
**Query:** My basic salary is Rs 25000 and EPF deducted is Rs 3000 every month. Is the deduction correct?

**Expected verdict:** correct
**Expected cites:** ['EPF_ACT_S6_CONTRIB', 'TOOL_PAYSLIP_AUDIT']

#### sft_only  cites=['EPF_ACT_S6_CONTRIB', 'EPF_PARA_26A', 'TOOL_PAYSLIP_AUDIT']  fab=[]  verdict=True
```
**EPF Deduction Verification**

**Result:** The EPF deduction of ₹3,000 is **CORRECT**.

**Reasoning:** According to the EPF Act [EPF_ACT_S6_CONTRIB], both the employee and employer must each contribute 12% of the employee's basic wages. The wage ceiling for mandatory EPF/EPS contributions is ₹15,000 per month [EPF_PARA_26A]. Since the basic salary is ₹25,000, which is above the wage ceiling, the EPF deduction of ₹3,000 matches the expected deduction of ₹3,000 [TOOL_PAYSLIP_AUDIT].

**Next Steps:**

1. Verify the EPF contribution details with your employer to ensure it matches the expected deduction.
2. Check if you have any other deductions or contributions that may be applicable.

**Warning:** Since the basic salary is above ₹15,000, you may be eligible to contribute on your full wages voluntarily. You can discuss this with your employer and submit a joint request to opt for voluntary contributions. [EPF_PARA_26A]
```

#### dpo_beta_0.05  cites=['EPF_ACT_S6_CONTRIB', 'EPF_PARA_26A', 'TOOL_PAYSLIP_AUDIT']  fab=[]  verdict=True
```
**Result:** EPF deduction is CORRECT.

**Eligibility:** Eligible=True

**Reasoning:** The EPF deduction of ₹3,000 matches the expected deduction of ₹3,000, which is calculated as 12% of the basic salary of ₹25,000 [EPF_ACT_S6_CONTRIB]. The statutory wage ceiling for EPF/EPS contributions is ₹15,000 per month, and the employee's basic salary is within this limit [EPF_PARA_26A].

**Next Steps:**

1.  Verify that the employer is contributing 12% of the basic salary to the EPF account.
2.  Check if the employee has voluntarily opted to contribute on their full wages if their basic salary exceeds ₹15,000.

**Warning/Caveat:** The employee's gross salary is not provided, so it is unclear if they are eligible for other deductions such as ESI. However, since their basic salary exceeds ₹21,000, they are not eligible for ESI [TOOL_PAYSLIP_AUDIT].
```

#### dpo_beta_0.10  cites=['EPF_ACT_S6_CONTRIB', 'EPF_PARA_26A', 'TOOL_PAYSLIP_AUDIT']  fab=[]  verdict=True
```
**Result:** The EPF deduction of ₹3,000 is CORRECT.

**Reasoning:** The legal basis for this is that the EPF Act requires both the employee and employer to contribute 12% of the employee's basic wages [EPF_ACT_S6_CONTRIB]. The statutory wage ceiling for EPF/EPS contributions is ₹15,000 per month [EPF_PARA_26A], and the employee's basic salary of ₹25,000 exceeds this threshold. Therefore, the EPF deduction of ₹3,000 matches the expected deduction of ₹3,000 [TOOL_PAYSLIP_AUDIT].

**Next Steps:**

1.  Verify that the employer is contributing 12% of the employee's basic wages, with 8.33% diverted to the EPS and 3.67% to the EPF account.
2.  Check if the employee has voluntarily opted to contribute on their full wages above ₹15,000, if applicable.

**Warning/Caveat:** If the employee's gross salary exceeds ₹21,000, they may also be eligible for ESI benefits, but this is not applicable in this case since the gross salary is not provided. Additionally, the state is not provided, so the Professional Tax deduction cannot be computed.
```

#### dpo_beta_0.20  cites=['EPF_ACT_S6_CONTRIB', 'EPF_PARA_26A']  fab=[]  verdict=True
```
**Result:** The EPF deduction of ₹3,000 is CORRECT.

**Reasoning:** The legal basis for this is that 12% of the basic salary of ₹25,000 is ₹3,000, as per the EPF Act [EPF_ACT_S6_CONTRIB].

**Next Steps:**

1. Verify that the employer is contributing 12% of the basic salary, with 8.33% diverted to the EPS and 3.67% to the EPF account.
2. Check if the employee has voluntarily opted to contribute on their full wages if their basic salary exceeds ₹15,000.

**Warning/Caveat:** If the employee's basic salary exceeds ₹15,000, they may be eligible to contribute on their full wages by submitting a joint request with their employer within 6 months of joining [EPF_PARA_26A].
```

### payslip_02 — payslip/verify_epf
**Query:** Basic 18000 hai aur employer 1800 EPF kaat raha hai. ye sahi hai?

**Expected verdict:** incorrect
**Expected cites:** ['EPF_ACT_S6_CONTRIB', 'TOOL_PAYSLIP_AUDIT']

#### sft_only  cites=['EPF_ACT_S6_CONTRIB', 'EPF_PARA_26A']  fab=[]  verdict=True
```
**Result:** EPF under-deducted by ₹360.

**Eligibility:** Eligible for EPF contribution.

**Reasoning:** The employer is deducting ₹1800, which is less than the expected ₹2160 (12% of ₹18000) [EPF_ACT_S6_CONTRIB]. The statutory wage ceiling for EPF/EPS contributions is ₹15000 per month [EPF_PARA_26A], and the employee's basic salary is ₹18000, which exceeds this ceiling. However, the employee can voluntarily opt to contribute on their full wages by submitting a joint request with their employer [EPF_PARA_26A].

**Next Steps:**

1.  The employee should request their employer to increase the EPF deduction to ₹2160 per month.
2.  If the employee earns above ₹15000 per month, they can submit a joint request with their employer to contribute on their full wages.

**Warning/Caveat:** The employee's EPF contribution is under-deducted by ₹360, which may affect their retirement savings. It is recommended to rectify this issue as soon as possible.
```

#### dpo_beta_0.05  cites=['EPF_ACT_S6_CONTRIB', 'EPF_PARA_26A']  fab=[]  verdict=True
```
**Result:** EPF under-deducted by ₹360.

**Eligibility:** eligible=True

**Next Steps:**

1.  The employer should contribute 12% of the employee's basic salary to EPF, which is ₹2,160 per month (12% of ₹18,000).
2.  The employer has under-deducted EPF by ₹360, which is the difference between the expected and actual deduction.
3.  The employee should bring this to the employer's attention to ensure the correct EPF contribution.

**Warnings/Caveats:** The EPF wage ceiling is ₹15,000 per month, but since the employee's basic salary is ₹18,000, the employer is required to contribute on the full amount. [EPF_ACT_S6_CONTRIB] and [EPF_PARA_26A]
```

#### dpo_beta_0.10  cites=['EPF_PARA_26A']  fab=[]  verdict=True
```
**Result:** EPF under-deducted by ₹360.

**Eligibility:** eligible=True

**Next Steps:**

1.  The employer should contribute 12% of the employee's basic salary to EPF, which is ₹2,160 per month (12% of ₹18,000).
2.  The employer has under-deducted EPF by ₹360, which is the difference between the expected and actual deduction.
3.  The employee should bring this to the employer's attention to ensure the correct EPF contribution.

**Warnings/Caveats:** The statutory wage ceiling for EPF/EPS contributions is ₹15,000 per month [EPF_PARA_26A]. Since the employee's basic salary is ₹18,000, the employer is not required to contribute on wages above ₹15,000 unless a joint option under Para 26(6) is exercised. However, in this case, the employer has chosen to contribute on the full basic salary, resulting in under-deduction.
```

#### dpo_beta_0.20  cites=['EPF', 'EPF_ACT_S6_CONTRIB', 'EPF_PARA_26A', 'ESI']  fab=['EPF', 'ESI']  verdict=True
```
**Result:** EPF under-deducted by ₹360.

**Eligibility:** eligible=True

**Next Steps:**

1.  The employer should contribute 12% of the employee's basic salary to EPF, which is ₹2,160 per month [EPF_ACT_S6_CONTRIB].
2.  The statutory wage ceiling for EPF/EPS contributions is ₹15,000 per month, and the employee's basic salary is ₹18,000, so the employer should contribute on the full salary [EPF_PARA_26A].
3.  The employee should request their employer to contribute on their full wages by submitting a joint request within 6 months of joining [EPF_PARA_26A].

**Warnings/Caveats:** The employee's basic salary is ₹18,000, which is above the statutory wage ceiling of ₹15,000 per month. The employer should contribute on the full salary to avoid under-deduction.

**Payroll Audit Result:**

  [EPF]
    EPF under-deducted by ₹360. Expected ₹2,160, actual ₹1,800
    Legal basis: EPF Act: 12% of basic ₹18,000 = ₹2,160/month
    Verdict: UNDER_DEDUCTED

  [ESI]
    Expected ESI: ₹135/month. Actual not provided.
    Legal basis: ESI Act: employee 0.75% of gross ₹18,000 = ₹135/month
    Verdict: NO_ACTUAL

  [Professional Tax]
    State not provided — cannot compute PT
    Legal basis: State not provided — cannot compute PT
    Verdict: CANNOT_COMPUTE
```

### payslip_03 — payslip/verify_esi
**Query:** gross salary Rs 19000, ESI kat raha Rs 143 monthly. correct hai ya nahi?

**Expected verdict:** correct
**Expected cites:** ['ESI_WAGE_LIMIT', 'TOOL_PAYSLIP_AUDIT']

#### sft_only  cites=['ESI_WAGE_LIMIT', 'TOOL_PAYSLIP_AUDIT']  fab=[]  verdict=True
```
**Result:** ESI deduction of ₹143 is CORRECT.

**Eligibility:** Eligible (condition met)

**Reasoning:** The ESI scheme applies to employees whose gross salary is ₹21,000 per month or less [ESI_WAGE_LIMIT]. The user's gross salary is ₹19,000, which is within the eligible limit.

**Next Steps:**

1.  Verify the state to check if the Professional Tax (PT) deduction is correct.
2.  If the state is provided, re-run the payslip audit to check the PT deduction.

**Warning/Caveat:** The PT deduction cannot be computed without the state information [TOOL_PAYSLIP_AUDIT].
```

#### dpo_beta_0.05  cites=['ESI_WAGE_LIMIT', 'TOOL_PAYSLIP_AUDIT']  fab=[]  verdict=True
```
**Result:** ESI deduction of ₹143 is CORRECT.

**Eligibility:** Eligible (as per ESI_WAGE_LIMIT [ESI_WAGE_LIMIT])

**Reasoning Trace:** The user's gross salary of ₹19,000 is less than the ESI wage limit of ₹21,000 [ESI_WAGE_LIMIT], making them eligible for ESI.

**Next Steps:**

1.  The ESI deduction of ₹143 is correct as it matches the expected deduction of ₹142, which is calculated as 0.75% of the gross salary of ₹19,000 [TOOL_PAYSLIP_AUDIT].
2.  Since the user is eligible for ESI, they should continue to receive ESI benefits.

**Warnings/Caveats:** None.
```

#### dpo_beta_0.10  cites=['ESI_WAGE_LIMIT']  fab=[]  verdict=True
```
**Result:** ESI deduction of ₹143 is CORRECT.

**Eligibility:** Eligible (as per ESI_WAGE_LIMIT [ESI_WAGE_LIMIT])

**Reasoning:** The user's gross salary of ₹19,000 is less than the ESI wage limit of ₹21,000 [ESI_WAGE_LIMIT], making them eligible for ESI.

**Next Steps:**

1.  Verify the state to check if the Professional Tax deduction is correct.
2.  If the state is provided, re-run the payslip audit to check the Professional Tax deduction.

**Warning/Caveat:** The Professional Tax deduction cannot be computed without the state information. Please provide the state to get an accurate payslip audit result.
```

#### dpo_beta_0.20  cites=['ESI_WAGE_LIMIT']  fab=[]  verdict=True
```
**Result:** ESI deduction of ₹143 is CORRECT.

**Eligibility:** Eligible (as per ESI_WAGE_LIMIT [ESI_WAGE_LIMIT])

**Reasoning:** The user's gross salary of ₹19,000 is less than the ESI wage limit of ₹21,000 [ESI_WAGE_LIMIT], making them eligible for ESI.

**Next Steps:**

1.  Verify the state to check if the Professional Tax deduction is correct.
2.  If the state is provided, re-run the payslip audit to check the Professional Tax deduction.

**Warning/Caveat:** The Professional Tax deduction cannot be computed without the state information. Please provide the state to get an accurate payslip audit result.
```

### payslip_04 — payslip/check_minimum_wage
**Query:** Maharashtra me unskilled worker hu, monthly 11000 rupees milta hai gross. minimum wage mil raha hai?

**Expected verdict:** incorrect
**Expected cites:** ['MIN_WAGE_MAHARASHTRA_2024']

#### sft_only  cites=['MIN_WAGE_MAHARASHTRA_2024']  fab=[]  verdict=False
```
**Result:** Not eligible for minimum wage

**Reason:** Your gross salary of ₹11000 is less than the statutory minimum wage of ₹14000 [MIN_WAGE_MAHARASHTRA_2024] for an unskilled worker in Maharashtra.

**Eligibility Condition:** The condition for eligibility is that the gross salary must be at least ₹14000 per month for an unskilled worker in Maharashtra.

**Next Steps:** You may consider discussing a salary increase with your employer to meet the statutory minimum wage requirements.

**Warning/Caveat:** Paying below the minimum wage is a criminal offence under Section 22 of the Minimum Wages Act [MIN_WAGE_MAHARASHTRA_2024].
```

#### dpo_beta_0.05  cites=['MIN_WAGE_MAHARASHTRA_2024']  fab=[]  verdict=False
```
**Result:** Not eligible for minimum wage

**Reason:** Your gross salary of ₹11000 is less than the statutory minimum wage of ₹14000 [MIN_WAGE_MAHARASHTRA_2024] for an unskilled worker in Maharashtra.

**Eligibility Condition:** The condition for eligibility is that the gross salary must be at least ₹14000 per month for an unskilled worker in Maharashtra.

**Next Steps:** You may file a complaint under the Minimum Wages Act 1948 for non-payment of the statutory minimum wage. You can approach the Labour Commissioner's office in Maharashtra for guidance on the complaint process.

**Warning:** Paying below the statutory minimum wage is a criminal offence under Section 22 of the Minimum Wages Act.
```

#### dpo_beta_0.10  cites=['MIN_WAGE_MAHARASHTRA_2024']  fab=[]  verdict=False
```
**Result:** Not eligible for minimum wage

**Reason:** Your gross salary of ₹11000 is less than the statutory minimum wage of ₹14000 [MIN_WAGE_MAHARASHTRA_2024] for an unskilled worker in Maharashtra.

**Eligibility Condition:** The condition for eligibility is that the gross salary must be at least ₹14000 per month for an unskilled worker in Maharashtra.

**Next Steps:** You may file a complaint with the Labour Department of Maharashtra or the relevant authorities under the Minimum Wages Act 1948 for non-payment of minimum wages.

**Warning:** Paying below the statutory minimum wage is a criminal offence under Section 22 of the Minimum Wages Act.
```

#### dpo_beta_0.20  cites=['MIN_WAGE_MAHARASHTRA_2024']  fab=[]  verdict=False
```
**Result:** Not eligible for minimum wage

**Reason:** Your gross salary of ₹11000 is less than the statutory minimum wage of ₹14000 [MIN_WAGE_MAHARASHTRA_2024] for an unskilled worker in Maharashtra.

**Eligibility Condition:** The condition for eligibility is that the gross salary must be at least ₹14000 per month for an unskilled worker in Maharashtra.

**Next Steps:** You may consider filing a complaint with the Labour Department of Maharashtra or the relevant authorities under the Minimum Wages Act 1948 for non-payment of the statutory minimum wage.

**Warning:** Paying below the statutory minimum wage is a criminal offence under Section 22 of the Minimum Wages Act.
```

### payslip_05 — payslip/full_audit
**Query:** Basic 20000, Gross 28000, Karnataka me. EPF kata 2400, ESI 0. Full audit karo.

**Expected verdict:** mixed
**Expected cites:** ['EPF_ACT_S6_CONTRIB', 'TOOL_PAYSLIP_AUDIT']

#### sft_only  cites=['EPF_ACT_S6_CONTRIB', 'ESI_WAGE_LIMIT', 'PROF_TAX_KARNATAKA', 'TOOL_PAYSLIP_AUDIT']  fab=[]  verdict=False
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

#### dpo_beta_0.05  cites=['EPF_ACT_S6_CONTRIB', 'ESI_WAGE_LIMIT', 'PROF_TAX_KARNATAKA']  fab=[]  verdict=True
```
**Result:**
EPF and ESI deductions are correct, but Professional Tax deduction is incorrect.

**EPF:**
EPF deduction of ₹2,400 is correct [EPF_ACT_S6_CONTRIB]. The legal basis is 12% of basic ₹20,000 = ₹2,400/month [EPF_ACT_S6_CONTRIB].

**ESI:**
ESI is not applicable as the gross salary is ₹28,000, which exceeds the threshold of ₹21,000 [ESI_WAGE_LIMIT].

**Professional Tax:**
The expected Professional Tax is ₹150/month, but the deduction is not shown. According to the Karnataka Professional Tax slab, the deduction should be ₹150/month for salaries up to ₹29,999 [PROF_TAX_KARNATAKA]. The correct deduction should be ₹150/month.

**Next Steps:**
1. Verify the Professional Tax deduction with the employer.
2. Request the employer to correct the Professional Tax deduction to ₹150/month.

**Warnings/Caveats:**
- The employer must deduct Professional Tax from each employee's salary and remit to the state government [PROF_TAX_KARNATAKA].
- Failure to deduct or remit Professional Tax is an offence under the state PT Act [PROF_TAX_KARNATAKA].
```

#### dpo_beta_0.10  cites=['EPF_ACT_S6_CONTRIB', 'ESI_WAGE_LIMIT', 'PROF_TAX_KARNATAKA']  fab=[]  verdict=True
```
**Result:**
EPF and ESI deductions are correct, but Professional Tax deduction is incorrect.

**EPF:**
EPF deduction of ₹2,400 is correct [EPF_ACT_S6_CONTRIB]. The legal basis is 12% of basic ₹20,000 = ₹2,400/month [EPF_ACT_S6_CONTRIB].

**ESI:**
ESI is not applicable as the gross salary is ₹28,000, which exceeds the threshold of ₹21,000 [ESI_WAGE_LIMIT].

**Professional Tax:**
The expected Professional Tax is ₹150/month, but the actual deduction is not mentioned. According to the Karnataka Professional Tax slab, the deduction should be ₹150/month for salaries up to ₹29,999 [PROF_TAX_KARNATAKA]. However, the actual deduction is not provided in the given information.

**Next Steps:**
1. Verify the actual Professional Tax deduction with the employer.
2. Ensure the employer is deducting the correct amount based on the Karnataka Professional Tax slab.

**Warnings/Caveats:**
- The employer should ensure they are deducting the correct Professional Tax amount.
- The employee should verify their Professional Tax deduction with their employer.
```

#### dpo_beta_0.20  cites=['EPF_ACT_S6_CONTRIB', 'ESI_WAGE_LIMIT', 'PROF_TAX_KARNATAKA']  fab=[]  verdict=True
```
**Result:**
EPF deduction is correct, ESI deduction is correct, and Professional Tax deduction is correct.

**Steps:**

1. EPF deduction: ₹2,400 is the correct amount deducted, as it is 12% of the basic salary ₹20,000 [EPF_ACT_S6_CONTRIB].
2. ESI deduction: ESI is not applicable as the gross salary ₹28,000 exceeds the threshold of ₹21,000 [ESI_WAGE_LIMIT].
3. Professional Tax deduction: ₹150 is the correct amount deducted, as it is the applicable slab for salaries between ₹15,000 and ₹29,999 in Karnataka [PROF_TAX_KARNATAKA].

**Warnings/Caveats:**
- The EPF deduction amount of ₹2,400 matches the expected amount, but it is essential to verify if the employer has correctly diverted 8.33% of the employer's contribution to the Employees' Pension Scheme (EPS) [EPF_ACT_S6_CONTRIB].
- The employee's gross salary ₹28,000 exceeds the threshold for ESI, so no ESI deduction is required.
- The Professional Tax deduction of ₹150 is correct, but it is essential to ensure that the employer has remitted this amount to the state government as per the Karnataka Professional Tax Act [PROF_TAX_KARNATAKA].
```

### labour_01 — labour/gratuity
**Query:** Worked 6 years 3 months at a private company, resigned last month. Last drawn salary was Rs 45000. Am I eligible for gratuity and how much?

**Expected verdict:** eligible
**Expected cites:** ['GRATUITY_ACT_S4_ELIG']

#### sft_only  cites=['GRATUITY_ACT_S4_ELIG']  fab=[]  verdict=True
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

#### dpo_beta_0.05  cites=['GRATUITY_ACT_S4_ELIG']  fab=[]  verdict=True
```
**Eligibility:** Eligible

**Result:** You are eligible for gratuity.

**Reasoning:** You have completed more than 5 years of continuous service [GRATUITY_ACT_S4_ELIG], which is the minimum requirement for gratuity.

**Next Steps:**

1.  Calculate the gratuity amount using the formula: (Last Drawn Monthly Salary × 15 × Years of Service) ÷ 26.
2.  Since your last drawn salary was ₹45,000, the monthly salary is ₹45,000 ÷ 12 = ₹3,750.
3.  Plug in the values: (₹3,750 × 15 × 6) ÷ 26 = ₹4,265.38
4.  The maximum gratuity payable is ₹20 Lakhs, so your gratuity amount is capped at ₹20,00,000.
5.  File a claim with your employer for gratuity within 30 days of becoming due, and if not paid, approach the Labour Commissioner for recovery.

**Warning:** If your employer delays gratuity payment, you are entitled to simple interest at 10% per annum on the amount due.
```

#### dpo_beta_0.10  cites=['GRATUITY_ACT_S4_ELIG']  fab=[]  verdict=True
```
**Eligibility:** Eligible

**Result:** You are eligible for gratuity.

**Reasoning:** You have completed more than 5 years of continuous service [GRATUITY_ACT_S4_ELIG], which is the minimum requirement for gratuity.

**Next Steps:**

1.  Calculate the gratuity amount using the formula: (Last Drawn Monthly Salary × 15 × Years of Service) ÷ 26.
2.  Since your last drawn salary was ₹45,000, the monthly salary is ₹45,000 ÷ 12 = ₹3,750.
3.  Multiply the monthly salary by 15 and years of service: ₹3,750 × 15 × 6 = ₹337,500.
4.  Divide the result by 26: ₹337,500 ÷ 26 = ₹12,981.54.
5.  The maximum gratuity payable is ₹20 Lakhs, so your gratuity amount is capped at ₹20,00,000.

**Warning:** Ensure your employer pays gratuity within 30 days of becoming due and pays simple interest at 10% per annum for any delay [GRATUITY_ACT_S4_ELIG].
```

#### dpo_beta_0.20  cites=['GRATUITY_ACT_S4_ELIG']  fab=[]  verdict=True
```
**Eligibility:** Eligible

**Result:** You are eligible for gratuity.

**Reasoning:** You have completed more than 5 years of continuous service [GRATUITY_ACT_S4_ELIG], which is the minimum requirement for gratuity.

**Next Steps:**

1.  Calculate the gratuity amount using the formula: (Last Drawn Monthly Salary × 15 × Years of Service) ÷ 26.
2.  Since your last drawn salary was ₹45,000, the monthly salary is ₹45,000 ÷ 12 = ₹3,750.
3.  Multiply the monthly salary by 15 and the years of service: ₹3,750 × 15 × 6 = ₹337,500.
4.  Divide the result by 26: ₹337,500 ÷ 26 = ₹12,981.54.
5.  The maximum gratuity payable is ₹20 Lakhs, so your gratuity amount is capped at ₹20,00,000.

**Warning:** Ensure your employer pays gratuity within 30 days of becoming due and pays simple interest at 10% per annum for any delay [GRATUITY_ACT_S4_ELIG].
```

### labour_02 — labour/maternity_benefit
**Query:** 8 months pregnant, working at a private IT firm for 3 years. Manager said only 12 weeks leave allowed. Is that correct?

**Expected verdict:** informational
**Expected cites:** ['MATERNITY_BENEFIT_ACT_2017']

#### sft_only  cites=['MATERNITY_BENEFIT_ACT_2017']  fab=[]  verdict=False
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

#### dpo_beta_0.05  cites=['MATERNITY_BENEFIT_ACT_2017']  fab=[]  verdict=True
```
**Result:** Eligible for 26 weeks of paid maternity leave.

**Reasoning:** Eligible because you have completed 3 years of employment and are pregnant.

**Condition Trace:**
- You are pregnant [MATERNITY_BENEFIT_ACT_2017]
- You have completed 3 years of employment [MATERNITY_BENEFIT_ACT_2017]
- The employer type is private, which does not affect eligibility [MATERNITY_BENEFIT_ACT_2017]

**Next Steps:**
1. Confirm your expected delivery date and the 12-month period preceding it to ensure you have 80 days of actual work.
2. Discuss your entitlement with your HR or manager to ensure they are aware of your rights under the Maternity Benefit (Amendment) Act 2017.

**Warning/Caveat:** Ensure you have a record of your 80 days of actual work in the 12 months preceding your expected delivery to avoid any issues with your maternity benefit claim.
```

#### dpo_beta_0.10  cites=['MATERNITY_BENEFIT_ACT_2017']  fab=[]  verdict=True
```
**Result:** Eligible for 26 weeks of paid maternity leave.

**Eligibility Reasoning:**
- The user is pregnant [MATERNITY_BENEFIT_ACT_2017].
- She has completed 3 years of employment [MATERNITY_BENEFIT_ACT_2017].
- The user's employer type is private [MATERNITY_BENEFIT_ACT_2017].

**Next Steps:**
1.  The user should provide a doctor's certificate confirming her pregnancy and expected delivery date to her employer.
2.  The employer must provide 26 weeks of paid maternity leave as per the Maternity Benefit (Amendment) Act 2017.

**Warning/Caveat:** The employer's claim of only 12 weeks leave is incorrect. The user is entitled to 26 weeks of paid maternity leave. If the employer is not providing the full leave, the user may need to escalate the matter to the relevant authorities.
```

#### dpo_beta_0.20  cites=['MATERNITY_BENEFIT_ACT_2017']  fab=[]  verdict=True
```
**Result:** Eligible for 26 weeks of paid maternity leave.

**Eligibility Reasoning:**
- The user is pregnant [MATERNITY_BENEFIT_ACT_2017].
- She has been working for 3 years, which meets the 80 days of actual work in the 12 months preceding the expected delivery [MATERNITY_BENEFIT_ACT_2017].
- She is employed in a private firm, which is covered by the Maternity Benefit Act 2017 [MATERNITY_BENEFIT_ACT_2017].

**Next Steps:**
1.  The user is entitled to 26 weeks of paid maternity leave for her first two live births.
2.  She should inform her employer about her pregnancy and provide necessary documents to claim the benefit.
3.  The employer must provide paid maternity leave as per the Maternity Benefit Act 2017.

**Warnings/Caveats:** 
- The user should check her employer's policies for any additional benefits or provisions.
- She should keep records of her employment and pregnancy to support her claim.
- If the employer denies the benefit, the user can file a complaint with the relevant authorities.
```

### labour_03 — labour/notice_period
**Query:** I want to resign immediately but my contract says 90 days notice period. Can I just pay basic salary and buy it out?

**Expected verdict:** conditional
**Expected cites:** ['NOTICE_PERIOD_BUYOUT_RULE']

#### sft_only  cites=['NOTICE_PERIOD_BUYOUT_RULE', 'STANDING_ORDERS_ACT_NOTICE_PERIOD']  fab=[]  verdict=True
```
**Result:** You cannot immediately pay basic salary and buy out the 90-day notice period.

**Eligibility:** eligible=False

**Reasoning:** According to the Industrial Employment (Standing Orders) Act 1946 [STANDING_ORDERS_ACT_NOTICE_PERIOD], if the contract specifies a longer notice period (e.g., 90 days), that contractual period applies. In your case, the contract requires a 90-day notice period. Additionally, the notice buy-out rule [NOTICE_PERIOD_BUYOUT_RULE] states that an employer cannot withhold the full and final settlement solely because of a notice period dispute; any recovery must be through civil proceedings or agreed deduction from F&F.

**Warning:** You may be required to serve the full 90-day notice period or face pay deduction for the shortfall. If you are unable or unwilling to serve the full notice period, you may need to negotiate with your employer to agree on a notice buy-out or seek civil proceedings to resolve the dispute.

**Next Steps:** Review your employment contract and discuss with your employer to explore options for resolving the notice period dispute. If necessary, consider seeking legal advice to understand your rights and obligations.
```

#### dpo_beta_0.05  cites=['NOTICE_PERIOD_BUYOUT_RULE', 'STANDING_ORDERS_ACT_NOTICE_PERIOD']  fab=[]  verdict=True
```
**Result:** You cannot immediately pay basic salary and buy out the 90-day notice period.

**Eligibility:** eligible=False

**Reason:** According to the Industrial Employment (Standing Orders) Act 1946 [STANDING_ORDERS_ACT_NOTICE_PERIOD], if the contract specifies a longer notice period (e.g., 60 or 90 days), that contractual period applies. In your case, the contract requires a 90-day notice period.

**Condition Trace:** 
- The notice period specified in the contract is 90 days.
- The employee is resigning, which means they are terminating their employment.

**Next Steps:** You can try negotiating with your employer to allow a notice buy-out, but they cannot withhold the full and final settlement solely because of a notice period dispute. If an agreement cannot be reached, the employer may recover the shortfall through civil proceedings or agreed deduction from the final settlement.

**Warning:** An employee cannot be forced to serve the notice period against their will — specific performance of a service contract is barred under Section 14 of the Specific Relief Act 1963 [NOTICE_PERIOD_BUYOUT_RULE].
```

#### dpo_beta_0.10  cites=['NOTICE_PERIOD_BUYOUT_RULE', 'STANDING_ORDERS_ACT_NOTICE_PERIOD']  fab=[]  verdict=True
```
**Result:** You cannot immediately pay basic salary and buy out the 90-day notice period.

**Eligibility:** eligible=False

**Reason:** According to the Industrial Employment (Standing Orders) Act 1946 [STANDING_ORDERS_ACT_NOTICE_PERIOD], if the contract specifies a longer notice period (e.g., 90 days), that contractual period applies. You are required to serve the full 90-day notice period as per your contract.

**Warning:** If you resign without serving the notice period, your employer may deduct your pay for the shortfall [STANDING_ORDERS_ACT_NOTICE_PERIOD]. However, you cannot be forced to serve the notice period against your will — specific performance of a service contract is barred under Section 14 of the Specific Relief Act 1963 [NOTICE_PERIOD_BUYOUT_RULE]. Your employer must recover any recovery through civil proceedings or agreed deduction from the full and final settlement.
```

#### dpo_beta_0.20  cites=['NOTICE_PERIOD_BUYOUT_RULE', 'STANDING_ORDERS_ACT_NOTICE_PERIOD']  fab=[]  verdict=True
```
**Result:** You cannot immediately pay basic salary and buy out the 90-day notice period.

**Eligibility:** eligible=False

**Reason:** According to the Industrial Employment (Standing Orders) Act 1946 [STANDING_ORDERS_ACT_NOTICE_PERIOD], if the contract specifies a longer notice period (e.g., 90 days), that contractual period applies. You are required to serve the full 90-day notice period as per your contract.

**Warning:** If you resign without serving the notice period, your employer may deduct your pay for the shortfall [STANDING_ORDERS_ACT_NOTICE_PERIOD]. However, you cannot be forced to serve the notice period against your will — specific performance of a service contract is barred under Section 14 of the Specific Relief Act 1963 [NOTICE_PERIOD_BUYOUT_RULE]. Your employer must recover any recovery through civil proceedings or agreed deduction from the full and final settlement.
```

### labour_04 — labour/wrongful_termination
**Query:** HR fired me suddenly yesterday without any notice period pay or warning, and they are holding my relieving letter. What are my rights?

**Expected verdict:** informational
**Expected cites:** ['WRONGFUL_TERMINATION_REMEDIES', 'RELIEVING_LETTER_LEGAL_OBLIGATION']

#### sft_only  cites=['RELIEVING_LETTER_LEGAL_OBLIGATION', 'STANDING_ORDERS_ACT_NOTICE_PERIOD', 'WRONGFUL_TERMINATION_REMEDIES']  fab=[]  verdict=True
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

#### dpo_beta_0.05  cites=['RELIEVING_LETTER_LEGAL_OBLIGATION', 'WRONGFUL_TERMINATION_REMEDIES']  fab=[]  verdict=True
```
**Result:** You are eligible to take action against your employer for wrongful termination.

**Eligibility Reasoning:**
- You were terminated by your employer without any notice period pay or warning [WRONGFUL_TERMINATION_REMEDIES].
- You have the right to raise an industrial dispute before the Labour Commissioner or the Labour Court, as you are a workman [WRONGFUL_TERMINATION_REMEDIES].

**Next Steps:**

1.  File a complaint under the Industrial Disputes Act within 3 years of the wrongful termination.
2.  Approach the Labour Commissioner or the Labour Court to seek reinstatement with back wages.
3.  If your employer is withholding your relieving letter, you can challenge this as restraint of trade under Section 27 of the Indian Contract Act 1872 [RELIEVING_LETTER_LEGAL_OBLIGATION].

**Warnings/Caveats:**

*   If your employer is in an 'essential service', different notice requirements may apply [WRONGFUL_TERMINATION_REMEDIES].
*   You may need to approach civil courts or the High Court if you are a managerial or supervisory employee [WRONGFUL_TERMINATION_REMEDIES].
*   Withholding a relieving letter can be challenged, but there is no central statute mandating its issuance [RELIEVING_LETTER_LEGAL_OBLIGATION].
```

#### dpo_beta_0.10  cites=['RELIEVING_LETTER_LEGAL_OBLIGATION', 'WRONGFUL_TERMINATION_REMEDIES']  fab=[]  verdict=True
```
**Result:** You are eligible to take action against your employer for wrongful termination.

**Eligibility Reasoning:**
- You were terminated by your employer without any notice period pay or warning [WRONGFUL_TERMINATION_REMEDIES].
- You have the right to raise an industrial dispute before the Labour Commissioner or the Labour Court, as you are a workman [WRONGFUL_TERMINATION_REMEDIES].

**Next Steps:**

1.  File a complaint under the Industrial Disputes Act within 3 years of the wrongful termination.
2.  Approach the Labour Commissioner or the Labour Court to seek reinstatement with back wages.
3.  If your employer is withholding your relieving letter, you can challenge this as restraint of trade under Section 27 of the Indian Contract Act 1872 [RELIEVING_LETTER_LEGAL_OBLIGATION].

**Warnings/Caveats:**

*   If your employer is in an 'essential service', different notice requirements may apply [WRONGFUL_TERMINATION_REMEDIES].
*   You may need to approach civil courts or the High Court if you are a managerial or supervisory employee [WRONGFUL_TERMINATION_REMEDIES].
*   Withholding a relieving letter can be challenged, but there is no central statute mandating its issuance [RELIEVING_LETTER_LEGAL_OBLIGATION].
```

#### dpo_beta_0.20  cites=['RELIEVING_LETTER_LEGAL_OBLIGATION', 'WRONGFUL_TERMINATION_REMEDIES']  fab=[]  verdict=True
```
**Result:** You are eligible to take action against your employer for wrongful termination.

**Eligibility Reasoning:**
- You were terminated by your employer without any notice period pay or warning [WRONGFUL_TERMINATION_REMEDIES].
- You have the right to raise an industrial dispute before the Labour Commissioner or the Labour Court, as you are a workman [WRONGFUL_TERMINATION_REMEDIES].

**Next Steps:**

1.  File a complaint under the Industrial Disputes Act within 3 years of the wrongful termination [WRONGFUL_TERMINATION_REMEDIES].
2.  Approach the Labour Commissioner or the Labour Court to seek reinstatement with back wages [WRONGFUL_TERMINATION_REMEDIES].
3.  If your employer is withholding your relieving letter, you can challenge this as restraint of trade under Section 27 of the Indian Contract Act 1872 [RELIEVING_LETTER_LEGAL_OBLIGATION].

**Warnings/Caveats:**

*   If your employer is in an 'essential service', different notice requirements may apply [WRONGFUL_TERMINATION_REMEDIES].
*   You may need to approach civil courts or the High Court if you are a managerial or supervisory employee [WRONGFUL_TERMINATION_REMEDIES].
*   Withholding a relieving letter may be challenged, but there is no central statute mandating its issuance [RELIEVING_LETTER_LEGAL_OBLIGATION].
```

### labour_05 — labour/gratuity
**Query:** I completed 4 years and 245 days in my current company. Will I get gratuity? I heard about some Madras High court ruling.

**Expected verdict:** conditional
**Expected cites:** ['GRATUITY_COURT_RULING_4Y8M']

#### sft_only  cites=['GRATUITY_ACT_S4_ELIG', 'GRATUITY_COURT_RULING_4Y8M']  fab=[]  verdict=True
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

#### dpo_beta_0.05  cites=['GRATUITY_COURT_RULING_4Y8M']  fab=[]  verdict=True
```
**Result:** Eligible for gratuity

**Reasoning:** The user has completed 4 years and 245 days of service, which is more than the practical threshold of 4 years and 240 days (approximately 4 years and 8 months) as per the Madras High Court ruling [GRATUITY_COURT_RULING_4Y8M].

**Eligibility Condition:** The user meets the condition of completing 4 years and 240 days of service, as per the Madras High Court ruling.

**Next Steps:**

1.  Calculate the gratuity amount using the formula: (Last Drawn Monthly Salary × 15 × Years of Service) ÷ 26.
2.  Ensure the employer pays gratuity within 30 days of becoming due and pays simple interest at 10% per annum for any delay.

**Warning/Caveat:** The employer must operate 6 days a week for the user to qualify with 245 days in the fifth year. If the employer operates 5 days a week, the user may not qualify with 245 days.
```

#### dpo_beta_0.10  cites=['GRATUITY_ACT_S4_ELIG', 'GRATUITY_COURT_RULING_4Y8M']  fab=[]  verdict=True
```
**Result:** Eligible for gratuity

**Reasoning:** Based on the Madras High Court ruling [GRATUITY_COURT_RULING_4Y8M], an employee who completes 4 years and 240 days (or more) of service qualifies for gratuity.

**Condition Trace:** 
- The employee has completed 4 years of service [GRATUITY_ACT_S4_ELIG].
- The employee has completed more than 240 days in the fifth year, which constitutes a full year of service for establishments operating 6 days per week [GRATUITY_COURT_RULING_4Y8M].

**Next Steps:**
1. Calculate the gratuity amount using the formula: (Last Drawn Monthly Salary × 15 × Years of Service) ÷ 26.
2. Ensure the employer pays gratuity within 30 days of becoming due and pays simple interest at 10% per annum for any delay [GRATUITY_ACT_S4_ELIG].

**Warning/Caveat:** The maximum gratuity payable is ₹20 Lakhs [GRATUITY_ACT_S4_ELIG]. If the calculated amount exceeds this limit, the employee will receive ₹20 Lakhs.
```

#### dpo_beta_0.20  cites=['GRATUITY_ACT_S4_ELIG', 'GRATUITY_COURT_RULING_4Y8M']  fab=[]  verdict=True
```
**Result:** Eligible for gratuity

**Reasoning:** Based on the Madras High Court ruling [GRATUITY_COURT_RULING_4Y8M], an employee who completes 4 years and 240 days (or more) of service qualifies for gratuity.

**Condition Trace:** 
- The employee has completed 4 years of service [GRATUITY_ACT_S4_ELIG].
- The employee has completed more than 240 days in the fifth year, which constitutes a full year of service for establishments operating 6 days per week [GRATUITY_COURT_RULING_4Y8M].

**Next Steps:**
1. Calculate the gratuity amount using the formula: (Last Drawn Monthly Salary × 15 × Years of Service) ÷ 26.
2. Ensure the employer pays gratuity within 30 days of becoming due and pays simple interest at 10% per annum for any delay [GRATUITY_ACT_S4_ELIG].

**Warning/Caveat:** The maximum gratuity payable is ₹20 Lakhs [GRATUITY_ACT_S4_ELIG]. If the calculated gratuity exceeds this amount, it will be subject to the statutory limit.
```

### tax_01 — tax/deductions_80c
**Query:** Chose new tax regime this FY. Invested 1.5 lakh in PPF. Can I claim 80C deduction?

**Expected verdict:** not applicable
**Expected cites:** ['ITA_SECTION_80C', 'FINANCE_ACT_2023_NEW_REGIME']

#### sft_only  cites=['FINANCE_ACT_2023_NEW_REGIME', 'ITA_SECTION_80C']  fab=[]  verdict=False
```
**Result:** Not eligible for 80C deduction

**Reason:** You have chosen the new tax regime, which does not allow the 80C deduction [ITA_SECTION_80C].

**Eligibility Condition:** The new tax regime is the default for individuals from FY 2023-24 onward, and the 80C deduction is not available under this regime [FINANCE_ACT_2023_NEW_REGIME].

**Next Steps:** You can consider other tax-saving options available under the new tax regime, such as the standard deduction of ₹50,000 and the tax rebate of up to ₹25,000 under Section 87A if your total income does not exceed ₹7 lakh.

**Warning/Caveat:** It's essential to review the tax slabs and deductions available under the new tax regime to optimize your tax savings. Consult a tax professional if you have any further queries.
```

#### dpo_beta_0.05  cites=['FINANCE_ACT_2023_NEW_REGIME', 'ITA_SECTION_80C']  fab=[]  verdict=False
```
**Result:** Not eligible for 80C deduction

**Reason:** You have chosen the new tax regime, which does not allow 80C deductions [ITA_SECTION_80C].

**Eligibility Condition:** The new tax regime, introduced by Section 115BAC of the Income Tax Act as amended by the Finance Act 2023, is the default for individuals from FY 2023-24 onward.

**Next Steps:** Consider other tax-saving options available under the new tax regime, such as the standard deduction of ₹50,000 and the tax rebate of up to ₹25,000 under Section 87A if your total income does not exceed ₹7 lakh.

**Warning:** The new tax regime has different tax slabs compared to the old regime. It's essential to review the new tax slabs to understand your tax liability. The tax slabs under the new regime are: Income up to ₹3 lakh — Nil; ₹3–6 lakh — 5%; ₹6–9 lakh — 10%; ₹9–12 lakh — 15%; ₹12–15 lakh — 20%; Above ₹15 lakh — 30% [FINANCE_ACT_2023_NEW_REGIME].
```

#### dpo_beta_0.10  cites=['FINANCE_ACT_2023_NEW_REGIME', 'ITA_SECTION_80C']  fab=[]  verdict=False
```
**Result:** Not eligible for 80C deduction

**Reason:** You have chosen the new tax regime, which does not allow 80C deductions [ITA_SECTION_80C].

**Eligibility Condition:** The new tax regime, introduced by the Finance Act 2023, is the default for individuals from FY 2023-24 onward [FINANCE_ACT_2023_NEW_REGIME]. Under this regime, Section 80C deductions are not available.

**Next Steps:** Consider exploring other tax deductions available under the new tax regime, such as the standard deduction of ₹50,000 or the tax rebate under Section 87A. Consult a tax professional for personalized advice.

**Warning:** The new tax regime has different tax slabs and deductions compared to the old regime. It's essential to understand the changes and plan your investments accordingly.
```

#### dpo_beta_0.20  cites=['FINANCE_ACT_2023_NEW_REGIME', 'ITA_SECTION_80C']  fab=[]  verdict=False
```
**Result:** Not eligible for 80C deduction

**Reason:** You have chosen the new tax regime, which does not allow 80C deductions [ITA_SECTION_80C].

**Eligibility Condition:** The new tax regime is the default for individuals from FY 2023-24 onward, and 80C deductions are not available under this regime [FINANCE_ACT_2023_NEW_REGIME].

**Next Steps:** Consider exploring other tax deductions available under the new tax regime, such as the standard deduction of ₹50,000 or the tax rebate of up to ₹25,000 under Section 87A if your total income does not exceed ₹7 lakh.

**Warning:** Since you have invested ₹1.5 lakh in PPF, you may be able to claim a deduction under other sections, but this is not specified in the provided passages. It is recommended to consult the relevant tax laws or a tax professional for further guidance.
```

### tax_02 — tax/hra_exemption
**Query:** Paying Rs 18000 rent in Bangalore, basic salary 40000, HRA received 15000. HRA exemption kitna milega?

**Expected verdict:** informational
**Expected cites:** ['ITA_SECTION_10_13A']

#### sft_only  cites=['ITA_SECTION_10_13A']  fab=[]  verdict=True
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

#### dpo_beta_0.05  cites=['ITA_SECTION_10_13A']  fab=[]  verdict=True
```
**Result:** HRA exemption of ₹15,000 is available.

**Steps:**

1. Calculate the HRA exemption using the formula: minimum of actual HRA received, rent paid minus 10% of basic salary, and 40% of basic salary.
2. Rent paid: ₹18,000
3. 10% of basic salary: ₹4,000 (10% of ₹40,000)
4. 40% of basic salary: ₹16,000 (40% of ₹40,000)
5. Actual HRA received: ₹15,000
6. HRA exemption = minimum of ₹15,000, ₹18,000 - ₹4,000 = ₹14,000, and ₹16,000 [ITA_SECTION_10_13A]

**Warnings/Caveats:** Ensure the landlord's PAN is provided to the employer if rent paid exceeds ₹1 lakh per annum. This exemption is only available under the old tax regime. Employees under the new tax regime cannot claim HRA exemption. [ITA_SECTION_10_13A]
```

#### dpo_beta_0.10  cites=['ITA_SECTION_10_13A']  fab=[]  verdict=True
```
**Result:** HRA exemption of ₹15,000 is available.

**Steps:**

1. Calculate the HRA exemption using the formula: minimum of actual HRA received, rent paid minus 10% of basic salary, and 40% of basic salary.
2. Rent paid: ₹18,000
3. 10% of basic salary: ₹4,000 (10% of ₹40,000)
4. 40% of basic salary: ₹16,000 (40% of ₹40,000)
5. Actual HRA received: ₹15,000
6. HRA exemption = minimum of ₹15,000, ₹18,000 - ₹4,000 = ₹14,000, and ₹16,000 [ITA_SECTION_10_13A]

**Warnings/Caveats:** Ensure the landlord's PAN is provided to the employer if rent paid exceeds ₹1 lakh per annum. This exemption is only available under the old tax regime. Employees under the new tax regime cannot claim HRA exemption. [ITA_SECTION_10_13A]
```

#### dpo_beta_0.20  cites=['ITA_SECTION_10_13A']  fab=[]  verdict=True
```
**Result:** HRA exemption of ₹15,000 will be available.

**Steps:**

1. Calculate the HRA exemption using the formula: minimum of actual HRA received, rent paid minus 10% of basic salary, and 40% of basic salary.
2. Rent paid: ₹18,000
3. 10% of basic salary: ₹4,000 (10% of ₹40,000)
4. 40% of basic salary: ₹16,000 (40% of ₹40,000)
5. Actual HRA received: ₹15,000
6. HRA exemption = minimum of ₹15,000, ₹18,000 - ₹4,000 = ₹14,000, and ₹16,000 [ITA_SECTION_10_13A]

**Warnings/Caveats:** Ensure the landlord's PAN is provided to the employer if rent paid exceeds ₹1 lakh per annum. This exemption is only available under the old tax regime. Employees under the new tax regime cannot claim HRA exemption. [ITA_SECTION_10_13A]
```

### tax_03 — tax/refund_status
**Query:** My ITR refund is delayed by over 4 months now. Portal shows processed but no money. I don't have any outstanding demand.

**Expected verdict:** informational
**Expected cites:** ['ITR_REFUND_DELAY_GRIEVANCE']

#### sft_only  cites=['ITR_REFUND_DELAY_GRIEVANCE', 'ITR_REFUND_OUTSTANDING_DEMAND', 'ITR_REFUND_STATUS']  fab=[]  verdict=True
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

#### dpo_beta_0.05  cites=['ITR_REFUND_DELAY_GRIEVANCE', 'ITR_REFUND_STATUS']  fab=[]  verdict=True
```
**Result:** Your ITR refund is likely delayed due to a bank account issue.

**Eligibility:** Eligible for refund re-issue (if bank account was not pre-validated or account details were wrong)

**Reasoning Trace:** Since your refund is delayed by over 4 months and there is no outstanding demand, it is likely that the bank account issue is the cause. According to [ITR_REFUND_STATUS], refunds are typically credited within 20–45 days of ITR processing. If the bank account was not pre-validated or account details were wrong, you can raise a refund re-issue request on the e-filing portal under 'Services > Refund Reissue'.

**Next Steps:**

1.  Check if your bank account is pre-validated on the IT portal by logging in to the e-filing portal > My Profile > Bank Account.
2.  If not pre-validated, pre-validate your bank account on the IT portal.
3.  If the issue persists, raise a refund re-issue request on the e-filing portal under 'Services > Refund Reissue'.

**Warning:** If the issue is not resolved, you can escalate by filing a grievance on the e-filing portal under 'e-Nivaran / Grievance' with the processing reference number. Refund interest under Section 244A accrues at 0.5% per month from April 1 of the assessment year (or from the date of filing if filed after April 1) until the date the refund is granted [ITR_REFUND_DELAY_GRIEVANCE].
```

#### dpo_beta_0.10  cites=['ITR_REFUND_DELAY_GRIEVANCE', 'ITR_REFUND_OUTSTANDING_DEMAND', 'ITR_REFUND_STATUS']  fab=[]  verdict=True
```
**Result:** Your ITR refund is likely delayed due to a common issue.

**Eligibility:** Eligible for refund re-issue (if bank account was not pre-validated or account details were wrong) or grievance escalation.

**Reasoning Trace:** Since you mentioned your refund is delayed by over 4 months and there is no outstanding demand, we will first try to resolve the issue through refund re-issue or grievance escalation.

**Steps:**

1.  Check if your bank account is pre-validated on the IT portal by logging in to incometax.gov.in > Login > e-File > Income Tax Returns > View Filed Returns.
2.  If your bank account is not pre-validated, pre-validate it on the IT portal under 'My Profile > Bank Account'.
3.  If the issue persists, raise a refund re-issue request on the e-filing portal under 'Services > Refund Reissue' if the bank account was not pre-validated or account details were wrong.
4.  If the refund is still not credited within 45 days of ITR processing, file a grievance on the e-filing portal under 'e-Nivaran / Grievance' with the processing reference number.

**Warnings/Caveats:** If your refund is being held due to an outstanding tax demand, you will need to respond to the notice under Section 245 of the Income Tax Act within 30 days to avoid automatic adjustment. Check your 26AS to verify if TDS was correctly credited for the previous assessment year. [ITR_REFUND_OUTSTANDING_DEMAND]

**Additional Information:** Refunds are typically credited within 20–45 days of ITR processing. If you have not received your refund within this timeframe, you can use the CPC helpline at 1800-103-0025 for ITRs processed by CPC Bengaluru. Refund interest under Section 244A accrues at 0.5% per month from April 1 of the assessment year (or from the date of filing if filed after April 1) until the date the refund is granted. [ITR_REFUND_STATUS] [ITR_REFUND_DELAY_GRIEVANCE]
```

#### dpo_beta_0.20  cites=['ITR_REFUND_DELAY_GRIEVANCE', 'ITR_REFUND_OUTSTANDING_DEMAND', 'ITR_REFUND_STATUS']  fab=[]  verdict=True
```
**Result:** Your ITR refund is likely delayed due to a common issue.

**Eligibility:** Eligible for refund re-issue (if bank account was not pre-validated or account details were wrong) or grievance escalation.

**Reasoning Trace:** Since you mentioned your refund is delayed by over 4 months and there is no outstanding demand, we can rule out the possibility of refund being adjusted against a tax demand [ITR_REFUND_OUTSTANDING_DEMAND]. 

**Steps to resolve:**

1.  Check your bank account details on the IT portal under 'My Profile > Bank Account' to ensure they are correct.
2.  If your bank account was not pre-validated or account details were wrong, raise a refund re-issue request on the e-filing portal under 'Services > Refund Reissue'.
3.  If the issue persists, file a grievance on the e-filing portal under 'e-Nivaran / Grievance' with the processing reference number.
4.  If your ITR was processed by CPC Bengaluru, you can contact their helpline at 1800-103-0025.

**Warnings/Caveats:** Refunds are typically credited within 20–45 days of ITR processing [ITR_REFUND_STATUS]. If you have not received your refund within 45 days, you can escalate through the above steps. Refund interest under Section 244A accrues at 0.5% per month from April 1 of the assessment year (or from the date of filing if filed after April 1) until the date the refund is granted [ITR_REFUND_DELAY_GRIEVANCE].
```

### tax_04 — tax/tds_on_pf
**Query:** Withdrawing total 4 lakhs from PF after 3.5 years of service. PAN card is updated in UAN. What is the exact TDS percentage?

**Expected verdict:** informational
**Expected cites:** ['ITA_SECTION_192A_TDS_PF']

#### sft_only  cites=['ITA_SECTION_192A_TDS_PF']  fab=[]  verdict=True
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

#### dpo_beta_0.05  cites=['CIRC_2024_TDS', 'ITA_SECTION_192A_TDS_PF']  fab=[]  verdict=True
```
**Result**
You are eligible for TDS on PF withdrawal.

**Reasoning Trace**
- Service years: 3 (less than 5 years)
- Withdrawal amount: ₹400,000 (exceeds ₹50,000)
- PAN card is updated in UAN (valid PAN provided)

**TDS Percentage**
10% [ITA_SECTION_192A_TDS_PF]

**Next Steps**
1. Submit Form 15G/15H if eligible to avoid TDS.
2. If not eligible for Form 15G/15H, TDS will be deducted at 10% [ITA_SECTION_192A_TDS_PF].
3. Ensure your PAN is correctly updated in UAN to avoid 20% TDS.

**Warning**
If your service period is 5 or more years, no TDS will be applicable [CIRC_2024_TDS].
```

#### dpo_beta_0.10  cites=['ITA_SECTION_192A_TDS_PF']  fab=[]  verdict=True
```
**Result**
You are eligible for TDS on PF withdrawal.

**Reasoning Trace**
- Service years: 3 (less than 5 years)
- Withdrawal amount: ₹400,000 (exceeds ₹50,000)
- PAN card is updated in UAN (valid PAN provided)

**TDS Percentage**
10% [ITA_SECTION_192A_TDS_PF]

**Next Steps**
1. Submit Form 15G/15H if eligible to avoid TDS.
2. Ensure the PF withdrawal amount is correctly processed with the TDS deduction.

**Warning/Caveat**
If your service period is 5 or more years, no TDS will be applicable, regardless of the withdrawal amount.
```

#### dpo_beta_0.20  cites=['ITA_SECTION_192A_TDS_PF']  fab=[]  verdict=True
```
**Result**
You are eligible for TDS on PF withdrawal.

**Reasoning Trace**
- Service years: 3 (less than 5 years)
- Withdrawal amount: ₹400,000 (exceeds ₹50,000)
- PAN card is updated in UAN (valid PAN provided)

**TDS Percentage**
10% [ITA_SECTION_192A_TDS_PF]

**Next Steps**
1. Submit Form 15G/15H if eligible to avoid TDS.
2. Ensure the PF withdrawal amount is correctly processed with the TDS deduction.

**Warning/Caveat**
If your service period is 5 years or more, no TDS will be applicable, regardless of the withdrawal amount.
```

### tax_05 — tax/form16
**Query:** Resigned in September. I asked for Form 16 for my part-year salary but HR says they will give it only next year in June. Is this allowed?

**Expected verdict:** informational
**Expected cites:** ['FORM_16_OVERVIEW']

#### sft_only  cites=['FORM_16_OVERVIEW']  fab=[]  verdict=True
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

#### dpo_beta_0.05  cites=['FORM_16_OVERVIEW']  fab=[]  verdict=True
```
**Result:** Not eligible for Form 16 for part-year salary

**Reason:** Form 16 is issued by the employer by 15 June of the assessment year, but it covers the entire assessment year, not part-year salaries.

**Eligibility Condition:** Form 16 is issued for the entire assessment year, not for part-year salaries [FORM_16_OVERVIEW].

**Next Steps:** You can still file your Income Tax Return (ITR-1 or ITR-2) using Form 26AS (tax credit statement), pay slips, and bank statements.

**Warning/Caveat:** If your employer fails to issue Form 16, they may be penalised under Section 272A [FORM_16_OVERVIEW]. Consider reaching out to your employer to provide the necessary documents for your ITR filing.
```

#### dpo_beta_0.10  cites=['FORM_16_OVERVIEW']  fab=[]  verdict=True
```
**Result:** Not eligible for Form 16 for part-year salary

**Reason:** Form 16 is issued by the employer by 15 June of the assessment year, but it covers the entire assessment year, not part-year salaries.

**Eligibility Condition:** Form 16 is issued for the entire assessment year, not for part-year salaries [FORM_16_OVERVIEW].

**Next Steps:** You can still file your Income Tax Return (ITR-1 or ITR-2) using Form 26AS (tax credit statement), pay slips, and bank statements.

**Warning/Caveat:** If your employer fails to issue Form 16, they may be penalised under Section 272A [FORM_16_OVERVIEW]. Consider reaching out to your employer to provide the necessary documents for your ITR filing.
```

#### dpo_beta_0.20  cites=['FORM_16_OVERVIEW']  fab=[]  verdict=True
```
**Result:** Not eligible for Form 16 for part-year salary

**Reason:** Form 16 is issued by 15 June of the assessment year, but you resigned in September, which is within the same assessment year.

**Eligibility Condition:** Form 16 is typically issued for the full assessment year, not for part-year salaries.

**Warning:** Your employer may be able to provide a partial Form 16 or an alternative document, such as Form 26AS, to help you file your Income Tax Return.

**Next Steps:**

1.  Request your employer to provide a partial Form 16 or an alternative document, such as Form 26AS, to help you file your Income Tax Return.
2.  File your Income Tax Return using the provided document and your pay slips, bank statements.

**Caveat:** If your employer fails to issue Form 16, they may be penalised under Section 272A [FORM_16_OVERVIEW].
```
