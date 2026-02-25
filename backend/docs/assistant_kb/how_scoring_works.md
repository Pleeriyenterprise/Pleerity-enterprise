# How compliance scoring works

Compliance Vault Pro calculates a **compliance score** (0–100) for each property and for your portfolio. The score reflects what the portal is tracking based on requirements and evidence—it is **not a legal opinion**. For legal compliance you should seek independent advice.

## What the score is based on

The system uses five components, each contributing to the final score:

1. **Requirement status (about 35%)**  
   Each requirement has a status (e.g. COMPLIANT, PENDING, EXPIRING_SOON, OVERDUE) based on whether there is valid evidence and whether any due or expiry date has passed. The system selects the best evidence per requirement (e.g. the document with the furthest future expiry where applicable). This component reflects the proportion of requirements that are satisfied, with more weight on critical types (e.g. Gas Safety, EICR, HMO Licence) than on others (e.g. EPC, inventory).

2. **Expiry timeline (about 25%)**  
   How soon certificates or checks expire. Items that are expiring soon or past due reduce this part of the score.

3. **Document coverage (about 15%)**  
   Whether the right documents are uploaded and, where applicable, verified. Only verified documents count fully toward coverage.

4. **Overdue penalty (about 15%)**  
   Overdue or expired items are penalised. Resolving overdue items (e.g. by uploading a new certificate) improves the score.

5. **Risk factor (about 10%)**  
   Property-specific factors, including whether the property is an HMO. HMO properties are scored more strictly (stricter compliance requirements).

## How the property score is combined

- Each **property** has its own score (0–100) and breakdown (status, expiry, document, overdue penalty, risk).
- The **portfolio** score is the average of all property scores (or the single property score if there is only one).

## Important points

- The score updates when requirements, documents, or due/expiry dates change (e.g. after uploads, recalculations, or data updates).
- Requirement types are weighted: for example Gas Safety, EICR, and HMO Licence have higher weight than EPC or inventory.
- The score reflects what the portal currently shows; it does not guarantee legal compliance.

When explaining a score to a user, use the portal context (including any **score_explanation** with per-property key reasons and trend) to describe *why* the score is what it is—e.g. “Some requirements are not yet compliant”, “Upcoming or past expiries are affecting the score”, “Overdue items are reducing the score”, “Document coverage is below 100%”.
