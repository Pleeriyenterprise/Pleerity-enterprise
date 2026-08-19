# Rendered content 02 (before / after)

Audit 01 history is not rewritten. Examples below are post-remediation.

## Compliance — overdue HMO fire evidence (live)

**Before (Audit 01 shape):** certificate/renewal framing; sibling requirements in the same body; CTA to generic overdue list.

**After (staging DELIVERED):**

```text
Subject: HMO fire safety management evidence (log book, tests, compartmentation) is overdue
CTA: Upload HMO fire safety evidence
Link: /properties/0a6f0874-…?requirement_id=68622908-…
```

No Gas Safety / EICR in this message. Status: Postmark **DELIVERED** (not merely accepted).

## Compliance — overdue Gas Safety (live, sibling of the above, same day)

```text
Subject: Gas Safety Certificate is overdue
CTA: Review Gas Safety Certificate
Idempotency fingerprint: d65c8d329ac60a25 (distinct from HMO 27e4bb733f01ce4a)
```

## Compliance — upcoming EICR (live)

```text
Subject: Your Electrical Installation Condition Report (EICR) expires in 4 days
```

Not “about 7 days”. Body timing matches the subject window.

## Scottish landlord (unit; not on Nancy runtime surface)

```text
Subject: Scottish landlord registration is overdue
Body contains only that requirement; “HMO fire” absent; “registration registration” absent; not “before expiry”.
```

## PAYMENT_FAILED (unit / code-built)

States payment was unsuccessful; plan line when present; “access has not been suspended” unless DISABLED; retry date only if provided and labelled as Stripe retry, not grace-period end. Never “You have a new notification from Pleerity.”

## SUBSCRIPTION_CANCELED (unit)

Cancel-at-period-end uses Stripe period-end date, not webhook now. Missing period: “cannot confirm a precise access-end date”.

## Onboarding Day 1 (live)

```text
Subject: Review your property in Compliance Vault Pro
Recipient: elena@yopmail.com (already has properties)
Status: DELIVERED
```

## Monthly digest

Still aggregate/summary-shaped in unit HTML. Not passed through the single-requirement reminder renderer.
