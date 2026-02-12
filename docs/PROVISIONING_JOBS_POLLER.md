# Provisioning jobs poller (production)

The webhook only persists state and returns 200 quickly. A **poller** is the reliable dispatch that processes `PAYMENT_CONFIRMED` (and other runnable) jobs.

## How it works

- **Webhook** (`checkout.session.completed`): upserts `provisioning_jobs` with `status=PAYMENT_CONFIRMED`, sets `needs_run=True`. If a job already exists for that `checkout_session_id` with status `PAYMENT_CONFIRMED` or `FAILED`, the webhook sets `needs_run=True` so the poller can recover stuck jobs. No in-process runner is started.
- **Poller** (`scripts/run_provisioning_poller.py`): finds jobs where `needs_run=True` and the job is not currently locked (or lock expired), then calls the runner for each. The runner acquires a job-level lock (`locked_until` + `lock_owner`) atomically before work; a second runner on the same job will skip.

## Running the poller in production (cron)

Run the script on a schedule so jobs are processed within a few minutes of payment.

**Example (every 2 minutes, from backend directory):**

```bash
*/2 * * * * cd /app/backend && python -m scripts.run_provisioning_poller --max-jobs 10
```

Adjust `--max-jobs` and the schedule to your volume. Ensure the cron environment has `MONGO_URL`, `DB_NAME`, and any env vars required by the runner (e.g. email, Stripe).

**One-off run (e.g. from backend/):**

```bash
python -m scripts.run_provisioning_poller --max-jobs 20
```

## Concurrency

- Each job has `locked_until` and `lock_owner`. The runner acquires the lock atomically (only one process can acquire). Lock duration is 5 minutes; if the runner crashes, the lock expires and the next poller run can retry.
- Multiple poller processes (e.g. multiple cron hosts) are safe: they will each pick different jobs (or the same job only after the lock expires).
