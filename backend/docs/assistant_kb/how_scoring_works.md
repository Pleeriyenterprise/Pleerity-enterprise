# How compliance scoring works (internal)

Compliance Vault Pro calculates a compliance score from the requirements and evidence held in the portal.

- Each requirement has a status (e.g. COMPLIANT, OVERDUE, EXPIRING_SOON, PENDING) based on whether there is valid evidence and whether any due or expiry date has passed.
- The system selects the best evidence per requirement (e.g. the document with the furthest future expiry where applicable).
- A property-level or portfolio-level score is derived from the proportion of requirements that are satisfied and, where configured, from weights assigned to requirement types.

The score reflects what the portal currently shows: it is not a legal opinion. For legal compliance you should seek independent advice.
