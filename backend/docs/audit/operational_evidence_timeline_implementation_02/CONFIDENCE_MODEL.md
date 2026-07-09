# Confidence Model

Confidence communicates **certainty** — it does not replace authority.

| Score | Label | When to use |
|---|---|---|
| 100 | runtime_confirmed | Direct emit at instrumentation boundary with authoritative pointer |
| 95 | multi_source_agreement | Two+ authoritative sources agree (future: job_run + message_log) |
| 80 | indirect_runtime_confirmation | Derived from authoritative record read at emit time |
| 60 | provider_acknowledgement_pending | Notification accepted but delivery unconfirmed |
| 40 | inference_only | Backfill or heuristic linkage (must set `metadata.backfill: true`) |

## Structure

```json
{
  "score": 100,
  "label": "runtime_confirmed",
  "reason": "Direct instrumentation at job_runner.run_instrumented"
}
```

## Governance

- Phase 1 producers default to **100**
- Backfill worker (Phase 4) must use **≤80** with explicit backfill flag
- Never use confidence to override authoritative source on conflict — source wins
