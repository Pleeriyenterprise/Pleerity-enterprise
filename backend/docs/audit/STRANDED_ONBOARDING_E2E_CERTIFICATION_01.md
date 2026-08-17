# Stranded onboarding — E2E certification 01

**Verdict:** `STRANDED_ONBOARDING_INCOMPLETE`

Unit/orchestration tests on `develop` cover diagnosis, uniqueness skip for released identity, release guards, and release vacating email. Frontend classification/mode labels pass.

Staging runtime matrix (Stripe session, Postmark, customer-observable checkout, fresh registration after release) was **not** executed in this session. Production was not used.

| Recovery case | Diagnosis | Admin action | API | DB | Stripe | Promo | Email | Identity | Customer continuation | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Expired checkout/no promo | `EXPIRED_CHECKOUT` | regenerate + `none` | implemented | implemented | expire+create (unit, not staging) | none | existing path | unchanged | not staging-proven | INCOMPLETE |
| Expired checkout/validated promo | `EXPIRED_CHECKOUT` / preserve | regenerate + `preserve_existing` | implemented | implemented | discounts | server-applied | existing path | unchanged | not staging-proven | INCOMPLETE |
| Email reserved/no payment | `EMAIL_RESERVED_NO_CHECKOUT` | release_and_restart | implemented | unit-proven | expire if present | n/a | not sent | reservation released | re-register not staging-proven | INCOMPLETE |
| Paid/provisioning pending | `PARTIAL_PROVISIONING` | escalate; release rejected | implemented | n/a | n/a | n/a | n/a | protected | n/a | PASS (guard) |
| Password setup pending | `ACTIVATION_INCOMPLETE` | resend_activation | existing | existing | n/a | n/a | existing | no release | not re-run | INCOMPLETE |
| Promo exception | apply_selected | regenerate | implemented | n/a | discounts | approved list | existing | unchanged | not staging-proven | INCOMPLETE |
| Unknown inconsistent | `UNKNOWN_RECOVERY_STATE` | escalate or release if unpaid | implemented | n/a | n/a | n/a | n/a | guarded | n/a | PASS_WITH_CONDITION |
| Customer-entered promo | n/a | n/a | not implemented | n/a | `allow_promotion_codes` unused | n/a | n/a | n/a | n/a | NOT_APPLICABLE |

Customer-entered Stripe promo codes remain out of scope (Scenario C).
