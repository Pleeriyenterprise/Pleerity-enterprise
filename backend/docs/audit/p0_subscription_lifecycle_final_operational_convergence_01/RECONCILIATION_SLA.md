# Reconciliation SLA

- **Scheduled batch:** stripe_subscription_reconcile every 6h (00:45,06:45,12:45,18:45 UTC)
- **Worst case (passive):** 360 minutes
- **Read-path stale cooldown:** 5 minutes
- **Documented guarantee:** Passive: up to 6h via batch; active portal load: up to 5m cooldown between stale pulls