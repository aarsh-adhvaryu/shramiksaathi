# Stage 2.3 — DPO Held-out Evaluation Report

- Prompts: 20
- Systems: SFT-only + 3 DPO betas (0.05, 0.10, 0.20)
- Winner: **dpo_beta_0.05**

## Summary

| Metric | sft_only | dpo_beta_0.05 | dpo_beta_0.10 | dpo_beta_0.20 |
|---|---|---|---|---|
| citation_coverage | 1.000 | 1.000 | 1.000 | 1.000 |
| fabrication_rate | 0.000 | 0.000 | 0.000 | 0.000 |
| expected_cites_hit | 0.800 | 0.700 | 0.750 | 0.700 |
| verdict_accuracy | 0.700 | 0.750 | 0.700 | 0.700 |
| grounded_clean | 0.700 | 0.750 | 0.700 | 0.700 |
| key_facts_mean | 0.675 | 0.775 | 0.700 | 0.700 |
| fabrication_count | 0 | 0 | 0 | 0 |

## Per-domain grounded_clean

| Domain | sft_only | dpo_beta_0.05 | dpo_beta_0.10 | dpo_beta_0.20 |
|---|---|---|---|---|
| pf | 0.40 | 0.40 | 0.40 | 0.40 |
| payslip | 0.60 | 0.80 | 0.80 | 0.80 |
| labour | 1.00 | 1.00 | 0.80 | 0.80 |
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
1. You can submit your withdrawal application without employer attestation by getting it attested from the bank where you maintain your account and explaining the reasons for not obtaining employer signature [FAQ_WD_023].
2. Alternatively, you can submit a composite claim (Aadhaar) which only requires your signature, if you have activated your UAN and linked your bank account and Aadhaar [FAQ_WD_023].

**Warnings/Caveats:** 
- Be aware that TDS will be applicable if your withdrawal exceeds Rs.50,000 and you have less than 5 years of service [CIRC_2024_TDS]. The applicable rate will be 10% if you are a resident with a valid PAN, 20% if you are a resident without a valid PAN, and 30% plus 4% cess if you are a non-resident.
```

#### dpo_beta_0.10  cites=['CIRC_2024_TDS', 'FAQ_WD_023']  fab=[]  verdict=True
```
**Result:** You are eligible for full PF withdrawal.

**Eligibility Reasoning Trace:**
- You have been unemployed for 4 months [FAQ_WD_023].
- You have completed 7 years of service [FAQ_WD_023].
- Your UAN is active and KYC is complete [FAQ_WD_023].

**Steps:**
1. Since you have completed 7 years of service, you are eligible for full PF withdrawal.
2. You can submit the withdrawal application using the composite claim (Aadhaar) option, which only requires your signature [FAQ_WD_023].
3. If your employer does not attest the claim form, you can get attestation from your bank where you maintain your account and submit it to the Regional PF Commissioner [FAQ_WD_023].

**Warnings/Caveats:** None

**TDS Information:** Since you have completed 7 years of service, no TDS will be applicable on your withdrawal [CIRC_2024_TDS].
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

#### sft_only  cites=['CIRC_2024_TDS', 'FAQ_WD_023']  fab=[]  verdict=False
```
**Result:** You are eligible to withdraw your PF partially.

**Eligibility Reasoning Trace:**
- You have been unemployed for 1 month, which is less than 2 months (typically considered for full withdrawal).
- You have an active UAN and complete KYC.
- You have completed 3 years of service.

**Steps:**

1.  You can submit a partial withdrawal application using the composite claim (Aadhaar) option, which only requires your signature.
2.  Since you have been unemployed for less than 2 months, you may not be eligible for a full withdrawal. However, you can still submit a partial withdrawal application.
3.  Ensure you have the necessary documents, including your Aadhaar card, to complete the application process.

**Warnings/Caveats:**
- TDS may be applicable if your withdrawal exceeds Rs. 50,000 and you have not completed 5 years of service. The TDS rates are:
    - Resident with valid PAN: 10%
    - Resident without valid PAN: 20%
    - Non-resident: 30% plus 4% cess
    - No TDS if service >= 5 years or transfer of funds [CIRC_2024_TDS]

**Next Steps:**
- Visit the EPFO website to submit your partial withdrawal application.
- Ensure you have the necessary documents and follow the instructions carefully.

**Caveat:** If you have any issues or disputes, you can get attestation from your bank and submit to the Regional PF Commissioner explaining the reasons for not obtaining employer signature [FAQ_WD_023].
```

#### dpo_beta_0.05  cites=['CIRC_2024_TDS']  fab=[]  verdict=False
```
**Result:** You are eligible to withdraw your PF fully.

**Eligibility Reasoning Trace:**
- You have been unemployed for 1 month, which is less than 2 months (typical waiting period for full withdrawal).
- Your UAN is active and KYC is complete.
- You have completed 3 years of service.

**Steps:**

1.  Login to the EPFO member portal or UAN portal with your UAN and password.
2.  Click on 'One Member - One EPF Account' and select 'Transfer Request (Form 13)'.
3.  Enter your previous PF account number and select the bank account where you want to transfer the funds.
4.  Submit the composite claim (Aadhaar) application, which only requires your signature.

**Warnings/Caveats:** 
- Ensure you have sufficient balance in your PF account to withdraw.
- If you have any outstanding loans or advances, you may need to settle those before withdrawing.
- TDS may be applicable if your withdrawal exceeds Rs.50,000 and you have less than 5 years of service [CIRC_2024_TDS]. The applicable rate will be 10% if you are a resident with a valid PAN, 20% if you are a resident without a valid PAN, and 30% plus 4% cess if you are a non-resident. No TDS will be deducted if you have 5 or more years of service or if you are transferring funds.
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
- Be aware that if your withdrawal exceeds Rs.50,000, TDS may be applicable if your service is less than 5 years [CIRC_2024_TDS].
- Ensure you have a valid PAN to avoid a higher TDS rate of 20% [CIRC_2024_TDS].
- If you are a non-resident, additional TDS of 4% cess may apply [CIRC_2024_TDS].
```

#### dpo_beta_0.20  cites=['CIRC_2024_TDS']  fab=[]  verdict=False
```
**Result:** You are eligible to withdraw your PF fully.

**Eligibility Reasoning Trace:**
- You have been unemployed for 1 month, which is less than 2 months ( typical waiting period for full withdrawal).
- Your UAN is active and KYC is complete.
- You have completed 3 years of service.

**Steps:**

1.  You can submit your full withdrawal application using the composite claim (Aadhaar) option, as your UAN is active and you have linked your bank account and Aadhaar.
2.  You will need to get your bank account details attested by the bank manager or a bank official, as your employer has not attested the claim form.
3.  Submit the composite claim to the Regional PF Commissioner, explaining the reasons for not obtaining employer signature.

**Warnings/Caveats:**
- Be aware that TDS may be applicable if your withdrawal exceeds Rs.50,000 and you have not completed 5 years of service. The TDS rates are:
    - Resident with valid PAN: 10%
    - Resident without valid PAN: 20%
    - Non-resident: 30% plus 4% cess
    - No TDS if service >= 5 years or transfer of funds [CIRC_2024_TDS]
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

#### dpo_beta_0.05  cites=['CIRC_2024_TDS']  fab=[]  verdict=True
```
**Result:** TDS applicable

**Eligibility:** Not eligible for exemption (service < 5 years)

**Reasoning:** TDS is applicable if service is less than 5 years and withdrawal exceeds Rs.50,000 [CIRC_2024_TDS]. The user has 3 years of service and withdrew Rs.2,00,000, which exceeds the threshold.

**Next Steps:**

1.  The user needs to provide their PAN to avoid a higher TDS rate.
2.  The user will be charged 10% TDS as they are a resident with a valid PAN [CIRC_2024_TDS].

**Warning:** If the user does not provide their PAN, they will be charged 20% TDS as a resident without a valid PAN [CIRC_2024_TDS].
```

#### dpo_beta_0.10  cites=['CIRC_2024_TDS', 'FORM_15G_INSTRUCTIONS']  fab=[]  verdict=True
```
**Result:** TDS applicable on your PF withdrawal of Rs. 2,00,000.

**Eligibility:** Not eligible for exemption (service < 5 years)

**Reasoning:** According to [CIRC_2024_TDS], TDS is applicable if service is less than 5 years and the withdrawal amount exceeds Rs. 50,000. You have served for 3 years, which is less than 5 years.

**TDS Rate:** As a resident with valid PAN, you will be charged 10% TDS [CIRC_2024_TDS].

**Next Steps:**

1.  File your income tax return to claim TDS credit.
2.  Ensure you have a valid PAN to avoid higher TDS rates.

**Warning:** If you had a total income below the taxable limit (Rs. 2.50 lakh) and were below 60 years old, you could have submitted Form 15G to avoid TDS [FORM_15G_INSTRUCTIONS]. However, since you have served for less than 5 years, this option is not available to you.
```

#### dpo_beta_0.20  cites=['CIRC_2024_TDS', 'FORM_15G_INSTRUCTIONS']  fab=[]  verdict=True
```
**Result:** TDS applicable on your PF withdrawal of Rs. 2,00,000.

**Eligibility:** Not eligible for exemption (service < 5 years)

**Reasoning:** According to [CIRC_2024_TDS], TDS is applicable if service is less than 5 years and the withdrawal amount exceeds Rs. 50,000. You have served for 3 years, which is less than 5 years.

**TDS Rate:** As a resident with valid PAN, you will be charged 10% TDS [CIRC_2024_TDS].

**Next Steps:**

1.  File your income tax return to claim TDS credit.
2.  Ensure you have a valid PAN to avoid a higher TDS rate of 20%.

**Warning:** If you had a valid PAN and your total income was below the taxable limit (Rs. 2.50 lakh), you could have submitted Form 15G to avoid TDS altogether [FORM_15G_INSTRUCTIONS]. However, since you have served for less than 5 years, this option is not available to you.
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

1.  Submit Form 13(R) or online transfer claim through the member interface at the unified portal to transfer your PF account to the new establishment.
2.  If you have an active UAN and Aadhaar+Bank seeded, you can also use the online transfer facility through the member interface.

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

**Warnings/Caveats:** Ensure your Date of Exit is updated in the previous account to facilitate transfer. If you have any issues with the online transfer process, you can submit a physical Form 13. [FAQ_WD_024] [FORM_13_INSTRUCTIONS] [CIRC_UAN_AUTO_TRANSFER]
```

#### dpo_beta_0.20  cites=['CIRC_UAN_AUTO_TRANSFER', 'FAQ_WD_024']  fab=[]  verdict=False
```
**Result:** Your PF account can be transferred to the new establishment on change of employment.

**Eligibility:** Eligible (conditions met: UAN active [FAQ_WD_024], KYC complete [FAQ_WD_024])

**Steps:**

1.  Submit Form 13(R) or online transfer request through the member interface at the unified portal.
2.  If you have an active UAN and Aadhaar+Bank seeded, you can also use the online transfer request feature.
3.  If you are UAN-linked with Aadhaar verification, your transfer may initiate automatically when the first month contribution is received in the new account from the new employer [CIRC_UAN_AUTO_TRANSFER].

**Warnings/Caveats:** None.
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
3.  If name mismatch is the issue, use Method 2: e-KYC Portal on EPFO website or UMANG app for self-validation without employer approval. However, if the details do not match exactly, a joint declaration is required.

**Warnings/Caveats:** For name mismatch, a joint declaration is necessary, which may require additional documentation and employer approval. Ensure you have the necessary documents before proceeding. [KYC_AADHAAR_GUIDE]
```

#### dpo_beta_0.20  cites=['FAQ_CLAIM_133', 'KYC_AADHAAR_GUIDE']  fab=[]  verdict=False
```
**Result:** KYC correction is possible, but requires specific steps.

**Eligibility:** Eligible (conditions met: member has UAN)

**Steps:**

1.  Login to EPFO UAN portal with your credentials.
2.  Update KYC by uploading necessary documents online.
3.  If name mismatch is the issue, you can use the online request for correction in name, date of birth, and gender (available on the EPFO UAN portal) [FAQ_CLAIM_133].
4.  If the name mismatch is with Aadhaar, you can use the e-KYC Portal on the EPFO website or UMANG app for self-validation, but only if the details match exactly. If there's a mismatch, a Joint Declaration is required [KYC_AADHAAR_GUIDE].

**Warnings/Caveats:** Ensure you have a UAN to update KYC online. If the name mismatch is significant, a Joint Declaration may be required.
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
2. If you have any further queries or concerns, please contact the EPFO helpline.

**Warning:** Since the basic salary is above ₹15,000, you may be eligible to contribute on your full wages voluntarily. You can submit a joint request with your employer to opt for this option. [EPF_PARA_26A]
```

#### dpo_beta_0.05  cites=['EPF_ACT_S6_CONTRIB', 'EPF_PARA_26A']  fab=[]  verdict=True
```
**Result:** EPF deduction is CORRECT.

**Eligibility:** Eligible=True

**Reasoning:** The EPF deduction of ₹3,000 matches the expected deduction of ₹3,000, which is calculated as 12% of the basic salary of ₹25,000 [EPF_ACT_S6_CONTRIB]. The statutory wage ceiling for EPF/EPS contributions is ₹15,000 per month, and the employee's basic salary is within this limit [EPF_PARA_26A].

**Next Steps:**

1.  Verify that the employer is contributing 12% of the basic salary to the EPF account.
2.  Check if the employee has voluntarily opted to contribute on their full wages if their basic salary exceeds ₹15,000.

**Warning/Caveat:** The EPF deduction is correct, but the employer's contribution may not be accurate if they are not contributing 12% of the basic salary. The employee should verify their EPF account statement to ensure the employer's contribution is correct.
```

#### dpo_beta_0.10  cites=['EPF_ACT_S6_CONTRIB', 'EPF_PARA_26A', 'TOOL_PAYSLIP_AUDIT']  fab=[]  verdict=True
```
**Result:** The EPF deduction of ₹3,000 is CORRECT.

**Reasoning:** The legal basis for this is that the EPF Act requires both the employee and employer to contribute 12% of the employee's basic wages [EPF_ACT_S6_CONTRIB]. The statutory wage ceiling for EPF/EPS contributions is ₹15,000 per month [EPF_PARA_26A], and the employee's basic salary of ₹25,000 exceeds this threshold. Therefore, the EPF deduction of ₹3,000 matches the expected amount of ₹3,000 [TOOL_PAYSLIP_AUDIT].

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

**Reasoning:** The employer is deducting ₹1800, which is less than the expected ₹2160 (12% of ₹18000) [EPF_ACT_S6_CONTRIB]. The statutory wage ceiling for EPF/EPS contributions is ₹15000 per month [EPF_PARA_26A], and the employee's basic salary is ₹18000, which is above the ceiling. However, the employee can voluntarily opt to contribute on their full wages by submitting a joint request with their employer [EPF_PARA_26A].

**Next Steps:**

1.  The employee should request their employer to increase the EPF deduction to ₹2160 per month.
2.  If the employee earns above ₹15000, they can submit a joint request with their employer to contribute on their full wages.

**Warning/Caveat:** The employee's state is not provided, so the payslip audit could not compute the Professional Tax deduction. The employee should provide their state to get an accurate PT deduction.
```

#### dpo_beta_0.05  cites=['EPF_ACT_S6_CONTRIB', 'EPF_PARA_26A']  fab=[]  verdict=True
```
**Result:** EPF under-deducted by ₹360.

**Eligibility:** eligible=True

**Reasoning:** The employer is deducting ₹1800, but the legal basis is 12% of basic ₹18000, which is ₹2160/month [EPF_ACT_S6_CONTRIB]. This is ₹360 less than the actual deduction.

**Next Steps:**

1.  Request the employer to deduct the correct EPF amount of ₹2160 per month.
2.  If the employer is unable to correct the deduction, file a grievance with the EPFO.

**Warning:** The EPF wage ceiling is ₹15000 per month [EPF_PARA_26A]. If the employee's basic salary exceeds ₹15000, they may be eligible for voluntary contributions on their full wages by submitting a joint request with their employer. However, this is not the case here.
```

#### dpo_beta_0.10  cites=['EPF_ACT_S6_CONTRIB', 'EPF_PARA_26A']  fab=[]  verdict=True
```
**Result:** EPF under-deducted by ₹360.

**Eligibility:** eligible=True

**Next Steps:**

1.  The employer should contribute 12% of the employee's basic salary to EPF, which is ₹2,160 per month [EPF_ACT_S6_CONTRIB].
2.  The statutory wage ceiling for EPF/EPS contributions is ₹15,000 per month, and the employee's basic salary is ₹18,000, so the employer should contribute on the full salary [EPF_PARA_26A].
3.  The employee should request their employer to contribute on their full wages by submitting a joint request within 6 months of joining [EPF_PARA_26A].

**Warnings/Caveats:** The employee's basic salary is ₹18,000, which is above the statutory wage ceiling of ₹15,000 per month. The employer should contribute on the full salary to avoid under-deduction.
```

#### dpo_beta_0.20  cites=['EPF_ACT_S6_CONTRIB', 'EPF_PARA_26A']  fab=[]  verdict=True
```
**Result:** EPF under-deducted by ₹360.

**Eligibility:** eligible=True

**Next Steps:**

1.  The employer should contribute 12% of the employee's basic salary to EPF, which is ₹2,160 per month [EPF_ACT_S6_CONTRIB].
2.  The statutory wage ceiling for EPF/EPS contributions is ₹15,000 per month, and the employee's basic salary is ₹18,000, so the employer should contribute on the full salary [EPF_PARA_26A].
3.  The employee should request their employer to contribute on their full wages by submitting a joint request within 6 months of joining [EPF_PARA_26A].

**Warnings/Caveats:** The employee's basic salary is ₹18,000, which is above the statutory wage ceiling of ₹15,000 per month. The employer should contribute on the full salary to avoid under-deduction.
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

#### dpo_beta_0.05  cites=['ESI_WAGE_LIMIT']  fab=[]  verdict=True
```
**Result:** ESI deduction of ₹143 is CORRECT.

**Eligibility:** Eligible (as per ESI_WAGE_LIMIT [ESI_WAGE_LIMIT])

**Reasoning:** The user's gross salary of ₹19,000 is less than the ESI wage limit of ₹21,000 [ESI_WAGE_LIMIT], making them eligible for ESI.

**Next Steps:**

1.  Verify the state to check if the Professional Tax deduction is correct.
2.  If the state is provided, re-run the payslip audit to check the Professional Tax deduction.

**Warning/Caveat:** The Professional Tax deduction cannot be computed without the state information. Please provide the state to get an accurate payslip audit result.
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

**Warning/Caveat:** Paying below the minimum wage is a criminal offence under Section 22 of the Minimum Wages Act.
```

#### dpo_beta_0.05  cites=['MIN_WAGE_MAHARASHTRA_2024']  fab=[]  verdict=False
```
**Result:** Not eligible for minimum wage

**Reason:** Your gross salary of ₹11000 is less than the statutory minimum wage of ₹14000 [MIN_WAGE_MAHARASHTRA_2024] for an unskilled worker in Maharashtra.

**Eligibility Condition:** The condition for eligibility is that the gross salary must be at least ₹14000 per month for an unskilled worker in Maharashtra.

**Next Steps:** You may file a complaint with the Labour Department of Maharashtra or the relevant authorities under the Minimum Wages Act 1948 for non-payment of minimum wages.

**Warning:** Paying below the statutory minimum wage is a criminal offence under Section 22 of the Minimum Wages Act.
```

#### dpo_beta_0.10  cites=['MIN_WAGE_MAHARASHTRA_2024']  fab=[]  verdict=False
```
**Result:** Not eligible for minimum wage

**Reason:** Your gross salary of ₹11000 is less than the statutory minimum wage of ₹14000 [MIN_WAGE_MAHARASHTRA_2024] for an unskilled worker in Maharashtra.

**Eligibility Condition:** The condition for eligibility is that the gross salary must be at least ₹14000 per month for an unskilled worker in Maharashtra.

**Next Steps:** You may consider filing a complaint with the Labour Department of Maharashtra or the relevant authorities under the Minimum Wages Act 1948 for non-payment of the statutory minimum wage.

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

#### sft_only  cites=['EPF_ACT_S6_CONTRIB', 'ESI_WAGE_LIMIT', 'PROF_TAX_KARNATAKA']  fab=[]  verdict=False
```
**Result:**
EPF deduction is correct [EPF_ACT_S6_CONTRIB], ESI deduction is correct [ESI_WAGE_LIMIT], and Professional Tax deduction is correct [PROF_TAX_KARNATAKA].

**Steps:**

1. EPF deduction of ₹2,400 is correct as it is 12% of the basic salary of ₹20,000 [EPF_ACT_S6_CONTRIB].
2. ESI deduction of ₹0 is correct as the gross salary of ₹28,000 exceeds the threshold of ₹21,000 [ESI_WAGE_LIMIT].
3. Professional Tax deduction of ₹150 is correct as the monthly salary of ₹28,000 falls within the slab of ₹15,000–29,999 in Karnataka [PROF_TAX_KARNATAKA].

**Warnings/Caveats:**
- The EPF deduction is within the legal limit of 12% of the basic salary [EPF_ACT_S6_CONTRIB].
- The ESI deduction is not applicable as the gross salary exceeds the threshold of ₹21,000 [ESI_WAGE_LIMIT].
- The Professional Tax deduction is within the legal limit of ₹150/month for salaries between ₹15,000 and ₹29,999 in Karnataka [PROF_TAX_KARNATAKA].
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
The expected Professional Tax is ₹150/month, but the actual deduction is not mentioned. According to the Karnataka Professional Tax slab, the deduction should be ₹150/month for salaries up to ₹29,999 [PROF_TAX_KARNATAKA]. However, the actual deduction is not provided in the given information.

**Eligibility Reasoning Trace:**
- EPF: Eligible (basic salary ₹20,000)
- ESI: Not eligible (gross salary ₹28,000 exceeds ₹21,000 threshold)
- Professional Tax: Eligible (salary ₹28,000 falls under ₹29,999 slab)

**Next Steps:**
1. Verify the actual Professional Tax deduction with the employer.
2. Ensure the employer is deducting the correct amount of ₹150/month as per the Karnataka Professional Tax slab.

**Warnings/Caveats:**
- The employer should ensure they are deducting the correct amount of Professional Tax.
- The employee should verify their salary slip to ensure the correct deductions are being made.
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
- The employer must deduct Professional Tax from each employee's salary and remit to the state government [PROF_TAX_KARNATAKA].
- Failure to deduct or remit Professional Tax is an offence under the state PT Act [PROF_TAX_KARNATAKA].
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
3. Ensure your employer has paid the maximum gratuity of Rs 20 Lakhs if applicable.

**Warning:** The employer must pay simple interest at 10% per annum for any delay in paying gratuity. Ensure you receive your gratuity amount within the stipulated time frame.
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
5.  File a claim with your employer for gratuity within 30 days of becoming due.

**Warning:** If your employer delays paying gratuity, you can claim simple interest at 10% per annum on the amount due.
```

#### dpo_beta_0.10  cites=['GRATUITY_ACT_S4_ELIG']  fab=[]  verdict=True
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

#### sft_only  cites=['MATERNITY_BENEFIT_ACT_2017']  fab=[]  verdict=True
```
**Result:** You are eligible for 26 weeks of paid maternity leave.

**Eligibility Reasoning:**
- You are pregnant [MATERNITY_BENEFIT_ACT_2017].
- You have been working for 3 years, which meets the eligibility criteria [MATERNITY_BENEFIT_ACT_2017].
- You are employed in a private firm, which is covered under the Maternity Benefit Act 2017 [MATERNITY_BENEFIT_ACT_2017].

**Next Steps:**
1. Confirm your expected delivery date and calculate the 12-month period preceding it to ensure you have 80 days of actual work.
2. Discuss your entitlement with your HR or manager to ensure they are aware of your rights under the Maternity Benefit Act 2017.
3. If your employer has 50 or more employees, inquire about the availability of creche facilities.

**Warning/Caveat:** Be aware that your employer may have a more generous maternity leave policy than the minimum required by law. It's essential to review your employee handbook or contract to understand your company's specific policies. [MATERNITY_BENEFIT_ACT_2017]
```

#### dpo_beta_0.05  cites=['MATERNITY_BENEFIT_ACT_2017']  fab=[]  verdict=True
```
**Result:** Eligible for 26 weeks of paid maternity leave.

**Eligibility Reasoning:**
- The user is pregnant [MATERNITY_BENEFIT_ACT_2017].
- She has completed 3 years of employment [MATERNITY_BENEFIT_ACT_2017].
- The employer type is private [MATERNITY_BENEFIT_ACT_2017].
- The user is eligible for 26 weeks of paid maternity leave for the first two live births [MATERNITY_BENEFIT_ACT_2017].

**Next Steps:**
1.  The user should inform her employer about her pregnancy and provide necessary documents.
2.  The employer must provide 26 weeks of paid maternity leave as per the Maternity Benefit (Amendment) Act 2017.

**Warnings/Caveats:**
- The user must have worked for at least 80 days in the 12 months preceding the expected delivery to be eligible for the full 26 weeks of paid maternity leave [MATERNITY_BENEFIT_ACT_2017].
- Employers with 50 or more employees must provide creche facilities [MATERNITY_BENEFIT_ACT_2017]. However, this is not directly related to the user's maternity leave entitlement.
```

#### dpo_beta_0.10  cites=['MATERNITY_BENEFIT_ACT_2017']  fab=[]  verdict=False
```
**Result:** Eligible for 26 weeks of paid maternity leave.

**Eligibility Reasoning:**
- The user is pregnant [MATERNITY_BENEFIT_ACT_2017].
- She has been working for 3 years, which meets the 80 days of actual work in the 12 months preceding the expected delivery [MATERNITY_BENEFIT_ACT_2017].
- She is employed in a private firm, which is covered by the Maternity Benefit Act 2017 [MATERNITY_BENEFIT_ACT_2017].
- This is her first two live births, so she is entitled to 26 weeks of paid maternity leave [MATERNITY_BENEFIT_ACT_2017].

**Next Steps:**
1.  Provide your employer with a copy of the Maternity Benefit (Amendment) Act 2017 to inform them of your entitlement.
2.  Ensure you have completed 80 days of actual work in the 12 months preceding your expected delivery to maintain eligibility.
3.  If your employer is unwilling to provide the full 26 weeks of paid leave, file a complaint with the Labour Department or the relevant grievance portal.

**Warning/Caveat:** Employers with 50 or more employees must provide creche facilities, but this is not directly relevant to your maternity leave entitlement.
```

#### dpo_beta_0.20  cites=['MATERNITY_BENEFIT_ACT_2017']  fab=[]  verdict=False
```
**Result:** Eligible for 26 weeks of paid maternity leave.

**Eligibility Reasoning:**
- The user is pregnant [MATERNITY_BENEFIT_ACT_2017].
- She has been working for 3 years, which meets the 80 days of actual work in the 12 months preceding the expected delivery [MATERNITY_BENEFIT_ACT_2017].
- She is employed in a private firm, which is covered by the Maternity Benefit Act 2017 [MATERNITY_BENEFIT_ACT_2017].

**Next Steps:**
1.  The user is entitled to 26 weeks of paid maternity leave for her first two live births [MATERNITY_BENEFIT_ACT_2017].
2.  She should inform her employer about her pregnancy and expected delivery to initiate the leave process.
3.  The employer must provide paid maternity leave for the eligible period.

**Warnings/Caveats:** 
- The user should check her employer's policies for any additional benefits or requirements.
- She should keep records of her employment and pregnancy to support her claim in case of any disputes.
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

**Warning:** You may be required to serve the full 90-day notice period or face pay deduction for the shortfall. If you wish to resign immediately, you may need to negotiate with your employer to agree on a settlement or pursue civil proceedings.

**Next Steps:** We recommend discussing your situation with your employer to explore possible settlement options or seeking advice from a labor expert. If you decide to pursue civil proceedings, you may need to file a complaint with the relevant authorities.
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

**Reason:** According to the Industrial Employment (Standing Orders) Act 1946 [STANDING_ORDERS_ACT_NOTICE_PERIOD], if the contract specifies a longer notice period (e.g., 60 or 90 days), that contractual period applies. In your case, the contract requires a 90-day notice period.

**Condition Trace:** 
- The notice period specified in the contract is 90 days.
- The employee is resigning, which means they are terminating their employment.

**Next Steps:** You can try negotiating with your employer to allow a notice buy-out, but they cannot withhold the full and final settlement solely because of a notice period dispute. If an agreement cannot be reached, the employer may recover the shortfall through civil proceedings or agreed deduction from the final settlement.

**Warning:** An employee cannot be forced to serve the notice period against their will — specific performance of a service contract is barred under Section 14 of the Specific Relief Act 1963 [NOTICE_PERIOD_BUYOUT_RULE].
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

1.  File a complaint under the Industrial Disputes Act within 3 years of the wrongful termination [WRONGFUL_TERMINATION_REMEDIES].
2.  Approach the Labour Commissioner or the Labour Court to seek reinstatement with back wages [WRONGFUL_TERMINATION_REMEDIES].
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
*   Withholding a relieving letter can be challenged, but there is no central statute mandating its issuance [RELIEVING_LETTER_LEGAL_OBLIGATION].
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
3.  Review your employment contract or company policies to understand the process for gratuity payment.

**Warning/Caveat:** The maximum gratuity payable is ₹20 Lakhs [GRATUITY_ACT_S4_ELIG]. If your gratuity amount exceeds this limit, you may need to consider other factors, such as tax implications.
```

#### dpo_beta_0.05  cites=['GRATUITY_COURT_RULING_4Y8M']  fab=[]  verdict=True
```
**Result:** Eligible for gratuity

**Reasoning:** The user has completed 4 years and 245 days of service, which is more than the practical threshold of 4 years and 240 days (approximately 4 years and 8 months) as per the Madras High Court ruling [GRATUITY_COURT_RULING_4Y8M].

**Eligibility Condition:** The user meets the condition of completing 4 years and 240 days of service, as per the Madras High Court ruling.

**Next Steps:**

1.  Calculate the gratuity amount using the formula: (Last Drawn Monthly Salary × 15 × Years of Service) ÷ 26.
2.  Ensure the employer pays gratuity within 30 days of becoming due and pays simple interest at 10% per annum for any delay.

**Warning/Caveat:** The employer must operate 6 days a week for the user to qualify with 240 days in the fifth year. If the employer operates 5 days a week, the user may not qualify with 245 days.
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

**Warning/Caveat:** The employer must operate 6 days a week for the 240-day threshold to apply. If the employer operates 5 days a week, the threshold is 190 days in the fifth year.
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

**Warning/Caveat:** The maximum gratuity payable is ₹20 Lakhs [GRATUITY_ACT_S4_ELIG]. If the calculated gratuity exceeds this amount, it will be subject to the maximum limit.
```

### tax_01 — tax/deductions_80c
**Query:** Chose new tax regime this FY. Invested 1.5 lakh in PPF. Can I claim 80C deduction?

**Expected verdict:** not applicable
**Expected cites:** ['ITA_SECTION_80C', 'FINANCE_ACT_2023_NEW_REGIME']

#### sft_only  cites=['FINANCE_ACT_2023_NEW_REGIME', 'ITA_SECTION_80C']  fab=[]  verdict=False
```
**Result:** Not eligible for 80C deduction

**Reason:** You have chosen the new tax regime, which does not allow the 80C deduction [ITA_SECTION_80C].

**Eligibility Condition:** The new tax regime, introduced by the Finance Act 2023, is the default for individuals from FY 2023-24 onward [FINANCE_ACT_2023_NEW_REGIME]. Under this regime, the 80C deduction is not available.

**Next Steps:** You can consider other tax-saving options available under the new tax regime, such as the standard deduction of ₹50,000 or the tax rebate of up to ₹25,000 under Section 87A if your total income does not exceed ₹7 lakh. Consult a tax professional for personalized advice.

**Warning:** The new tax regime has different tax slabs and deductions compared to the old regime. It's essential to understand the changes and plan your investments accordingly.
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

**Next Steps:** Consider exploring other tax deductions available under the new tax regime, such as the standard deduction of ₹50,000 or the tax rebate under Section 87A. However, these deductions may have different eligibility conditions and limits.

**Warning:** It's essential to review the tax slabs and deductions available under the new tax regime to optimize your tax savings. Consult a tax professional if you have further questions or concerns.
```

#### dpo_beta_0.20  cites=['FINANCE_ACT_2023_NEW_REGIME', 'ITA_SECTION_80C']  fab=[]  verdict=False
```
**Result:** Not eligible for 80C deduction

**Reason:** You have chosen the new tax regime, which does not allow 80C deductions [ITA_SECTION_80C].

**Eligibility Condition:** The new tax regime is the default for individuals from FY 2023-24 onward, and 80C deductions are not available under this regime [FINANCE_ACT_2023_NEW_REGIME].

**Next Steps:** Consider exploring other tax deductions available under the new tax regime, such as the standard deduction of ₹50,000 or the tax rebate of up to ₹25,000 under Section 87A if your total income does not exceed ₹7 lakh.

**Warning/Caveat:** Be aware that the new tax regime has different tax slabs and deductions compared to the old regime. It's recommended to consult a tax professional for personalized advice.
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

**Expected verdict:** informational
**Expected cites:** ['ITR_REFUND_DELAY_GRIEVANCE']

#### sft_only  cites=['ITR_REFUND_DELAY_GRIEVANCE', 'ITR_REFUND_STATUS']  fab=[]  verdict=True
```
**Result:** Your ITR refund is likely delayed due to a common issue.

**Eligibility:** Eligible for refund re-issue and grievance escalation.

**Reasoning Trace:** Since you have no outstanding demand, the refund is not being held back due to any tax liability. However, the refund has been processed but not credited to your account.

**Steps to resolve:**

1.  Check the refund status on the NSDL portal at tin.tin.nsdl.com or the e-filing portal at incometax.gov.in.
2.  Verify that your bank account is pre-validated on the IT portal under 'My Profile > Bank Account'. If not, pre-validate your account to resolve the issue.
3.  If the bank account was not pre-validated or account details were wrong, raise a refund re-issue request on the e-filing portal under 'Services > Refund Reissue'.
4.  If the refund is still not credited after 45 days, file a grievance on the e-filing portal under 'e-Nivaran / Grievance' with the processing reference number.

**Warnings/Caveats:** Refunds are typically credited within 20–45 days of ITR processing [ITR_REFUND_STATUS]. If the refund is not credited within 45 days, you can escalate through the steps mentioned above [ITR_REFUND_DELAY_GRIEVANCE]. Refund interest under Section 244A accrues at 0.5% per month from April 1 of the assessment year (or from the date of filing if filed after April 1) until the date the refund is granted [ITR_REFUND_DELAY_GRIEVANCE].
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

**Reasoning Trace:**
- The refund processing time is typically 20-45 days [ITR_REFUND_STATUS].
- If the refund is not credited within 45 days, you can escalate through specific steps [ITR_REFUND_DELAY_GRIEVANCE].
- However, since you mentioned your refund is delayed by over 4 months, it's possible that there's an outstanding tax demand [ITR_REFUND_OUTSTANDING_DEMAND].

**Next Steps:**

1.  Check your bank account details on the IT portal to ensure they are correct and pre-validated.
2.  If your bank account was not pre-validated or account details were wrong, raise a refund re-issue request on the e-filing portal under 'Services > Refund Reissue'.
3.  If you have an outstanding tax demand, respond to the notice within 30 days by logging in to the e-filing portal > Pending Actions > Response to Outstanding Demand.
4.  If the demand is incorrect, upload documentary evidence to dispute it.

**Warning/Caveat:** Failure to respond to the outstanding demand notice may result in your refund being automatically adjusted [ITR_REFUND_OUTSTANDING_DEMAND]. Ensure you address this issue promptly to avoid any further complications.
```

#### dpo_beta_0.20  cites=['ITR_REFUND_DELAY_GRIEVANCE', 'ITR_REFUND_STATUS']  fab=[]  verdict=True
```
**Result:** Your ITR refund is likely delayed due to a common issue.

**Eligibility:** Eligible for refund re-issue (if bank account was not pre-validated or account details were wrong) or grievance escalation.

**Reasoning Trace:** Since you mentioned your refund is delayed by over 4 months and there is no outstanding demand, we can consider the following:

1. Check if your bank account was pre-validated on the IT portal [ITR_REFUND_STATUS].
2. If not pre-validated, pre-validate your bank account on the IT portal under 'My Profile > Bank Account' [ITR_REFUND_STATUS].
3. If the bank account was not pre-validated or account details were wrong, raise a refund re-issue request on the e-filing portal under 'Services > Refund Reissue' [ITR_REFUND_DELAY_GRIEVANCE].
4. If the above steps do not resolve the issue, file a grievance on the e-filing portal under 'e-Nivaran / Grievance' with the processing reference number [ITR_REFUND_DELAY_GRIEVANCE].
5. If your ITR was processed by CPC Bengaluru, use the CPC helpline at 1800-103-0025 [ITR_REFUND_DELAY_GRIEVANCE].

**Warnings/Caveats:** Refunds are typically credited within 20–45 days of ITR processing [ITR_REFUND_STATUS]. If your refund is not credited within 45 days, you can escalate through the above steps. Refund interest under Section 244A accrues at 0.5% per month from April 1 of the assessment year (or from the date of filing if filed after April 1) until the date the refund is granted [ITR_REFUND_DELAY_GRIEVANCE].
```

### tax_04 — tax/tds_on_pf
**Query:** Withdrawing total 4 lakhs from PF after 3.5 years of service. PAN card is updated in UAN. What is the exact TDS percentage?

**Expected verdict:** informational
**Expected cites:** ['ITA_SECTION_192A_TDS_PF']

#### sft_only  cites=['CIRC_2024_TDS', 'ITA_SECTION_192A_TDS_PF']  fab=[]  verdict=True
```
**Result**
You are eligible for TDS on PF withdrawal.

**TDS Percentage**
The TDS percentage for your PF withdrawal is 10% [ITA_SECTION_192A_TDS_PF].

**Eligibility Reasoning**
You have less than 5 years of service [ITA_SECTION_192A_TDS_PF] and the withdrawal amount exceeds ₹50,000 [ITA_SECTION_192A_TDS_PF]. You have also updated your PAN card in UAN [ITA_SECTION_192A_TDS_PF], which is a valid condition for the 10% TDS rate.

**Next Steps**
1. Submit Form 15G/15H if eligible to avoid TDS.
2. Ensure the PF withdrawal amount is correctly processed with the 10% TDS deduction.

**Warning/Caveat**
Note that if your service had been 5 years or more, or if the withdrawal amount was ₹50,000 or less, no TDS would have been applicable [ITA_SECTION_192A_TDS_PF]. Additionally, if you were a non-resident, the TDS rate would have been 30% plus 4% cess [CIRC_2024_TDS].
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
- Form 16 is typically issued by 15 June of the assessment year.
- Since the user resigned in September, the assessment year has not yet begun.

**Answer:** The employer's decision to provide Form 16 only in June of the next year is **allowed** [FORM_16_OVERVIEW]. However, the user may still file their Income Tax Return (ITR) using Form 26AS, pay slips, and bank statements.

**Steps:**

1.  The user can file their ITR using Form 26AS, pay slips, and bank statements.
2.  The user should keep a record of their pay slips and bank statements for the period they worked.
3.  If the employer fails to issue Form 16, they may be penalised under Section 272A [FORM_16_OVERVIEW].

**Warning/Caveat:** The user should ensure they have all necessary documents to file their ITR correctly. If they face any issues, they can contact the Income Tax Department for assistance.
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

**Reason:** Form 16 is issued by the employer by 15 June of the assessment year, but it covers the entire assessment year, not part-year salaries.

**Eligibility Condition:** Form 16 is issued for the entire assessment year, not for part-year salaries [FORM_16_OVERVIEW].

**Next Steps:** You can still file your Income Tax Return (ITR-1 or ITR-2) using Form 26AS (tax credit statement), pay slips, and bank statements.

**Warning/Caveat:** If your employer fails to issue Form 16, they may be penalised under Section 272A [FORM_16_OVERVIEW]. Consider reaching out to your employer to provide the necessary documents for your tax filing.
```
