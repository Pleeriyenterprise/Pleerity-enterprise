# Stage Y — Real Twin Capture Run Report

**Authority:** STAGE-Y-WEBHOOK-REGISTRATION-AND-REAL-EVENT-CAPTURE-02
**Generated:** 2026-06-19T11:16:07.276196Z
**Overall:** BLOCKED
**Success criteria met:** False

## Required fields

1. Webhook registration status: **BLOCKED**
2. webhook_id: `None`
3. signing_secret stored: secret_present=False length=0 masked=None
4. deployed run_id: `None`
5. run status: `None`
6. webhook receipt status: `None`
7. event capture status: `None`
8. finished event located: **False**
9. final output JSON path: `None`
10. record count: **0**
11. sample record shape: see JSON analysis file
12. extraction readiness: **RED**

## Staging connector

- CVP base: `https://pleerity-enterprise.onrender.com`
- Health HTTP status: `404`
- Connector reachable: **False**
- Note: 404 — set DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED=true on staging Render and redeploy before Twin can POST webhooks

## Blockers
- 404 — set DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED=true on staging Render and redeploy before Twin can POST webhooks
- TWIN_API_KEY missing

## Ops rerun (STAGE-Y-02)

Create `backend/.env.twin.staging` from `docs/audit/discovery_phase_1_launch_01/twin_workspace/env.twin.staging.example` (gitignored):

```bash
DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED=true
DISCOVERY_TWIN_EVENT_CAPTURE_ONLY=true
TWIN_API_KEY=<Twin dashboard>
TWIN_DISCOVERY_AGENT_ID=019edece-894a-7836-aecd-2b6eedbe443f
STAGE_Y_CVP_BASE_URL=https://pleerity-enterprise.onrender.com
```

Register webhook + trigger deployed run + wait for receipt:

```bash
cd backend
python scripts/discovery_stage_y_webhook_capture_02.py \
  --register-webhook --trigger-run --wait-webhook
```

Or after manual Twin run:

```bash
python scripts/discovery_stage_y_webhook_capture_02.py \
  --register-webhook --run-id <deployed_run_id> --wait-webhook
```

Endpoint test only (stopped build run):

```bash
python scripts/discovery_stage_y_webhook_capture_02.py --test-build-run
```
