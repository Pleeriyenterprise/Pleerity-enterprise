# Compliance Score + Requirement Status Update – Audit

## A) Repo audit (code paths, no assumptions)

### 1) Single production scoring function

- **File:** `backend/services/compliance_score.py`
- **Function:** `calculate_compliance_score(client_id: str) -> Dict[str, Any]`
- **Only caller:** This function is the single place that computes the 0–100 score. All score display and history use it or stored results of it.

---

### 2) Endpoints that return compliance score

| Endpoint | Recompute on request? | Reads stored score? | Proof (file:line) |
|----------|------------------------|----------------------|-------------------|
| `GET /api/client/compliance-score` | **Yes** | No | `routes/client.py`: `score_data = await calculate_compliance_score(user["client_id"])` on every request |
| `GET /api/client/compliance-score/trend` | No (trend is historical) | Yes | `compliance_trending.get_score_trend()` reads `compliance_score_history` |
| `GET /api/client/compliance-score/explanation` | No | Yes | `compliance_trending.get_score_change_explanation()` reads `compliance_score_history` |
| `POST /api/client/compliance-score/snapshot` | Yes (then stores) | No | Calls `capture_daily_snapshot()` → `calculate_compliance_score(client_id)` then writes to `compliance_score_history` |

So: the **current score** is always **recomputed on fetch** when the client (or frontend) calls `GET /api/client/compliance-score`. There is no caching of the live score; trend/explanation use stored snapshots only.

---

### 3) Document upload and delete endpoints

**Upload (client):**

- **Endpoint:** `POST /api/documents/upload` (`routes/documents.py` ~604)
- **Guard:** `client_route_guard`
- **Requirement update:** **Yes.** After inserting the document (status `UPLOADED`), it calls `regenerate_requirement_due_date(requirement_id, client_id)` (~668), which:
  - Sets `requirements.status` = `COMPLIANT`
  - Sets `requirements.due_date` = now + frequency_days
- **Score recompute:** **No.** No call to `calculate_compliance_score` or to `_update_property_compliance`.
- **Property compliance_status:** **No.** `_update_property_compliance(property_id)` is **not** called. Property stays RED/AMBER until the next run of `check_compliance_status_changes` (see §4) or until an admin **verifies** the document (verify path does call it).

**Upload (admin):**

- **Endpoint:** `POST /api/documents/admin/upload` (`routes/documents.py` ~701)
- **Guard:** `admin_route_guard`
- **Requirement update:** **Yes.** Same as client: `regenerate_requirement_due_date(requirement_id, client_id)` (~767).
- **Score recompute:** **No.**
- **Property compliance_status:** **No.** Same gap as client upload.

**Delete (client):**

- **Endpoint:** **None.** There is no `DELETE /api/documents/{id}` (or similar) in `routes/documents.py`. Document delete for the main vault does not exist.

**Delete (admin):**

- **Endpoint:** **None.** No admin document-delete endpoint in the audited routes.

So: **upload** updates requirement status (and due date); **delete** is not implemented, so there is no “delete → requirement revert” path. Score and property compliance are not refreshed at upload time; score is refreshed on next `GET /api/client/compliance-score`, and property compliance is refreshed by jobs or by the verify flow.

---

### 4) Background jobs (score snapshots + overdue/expiring)

| Job | What it does | Where scheduled | How it runs |
|-----|----------------|-----------------|-------------|
| **Compliance score snapshots** | For each client, calls `calculate_compliance_score(client_id)` and stores result in `compliance_score_history` (by `date_key`). | `server.py` ~482: `CronTrigger(hour=2, minute=0)` (02:00 UTC daily) | `run_compliance_score_snapshots()` → `capture_all_client_snapshots()` in `compliance_trending.py` |
| **Overdue / expiring requirement transitions** | For each active client, loads requirements; if due date is past → sets `status` = `OVERDUE`; if within reminder_days → sets `status` = `EXPIRING_SOON`. Sends reminder emails. | `server.py`: daily reminders at 09:00 UTC | `run_daily_reminders()` → `JobScheduler.send_daily_reminders()` in `services/jobs.py` (~84–126) |
| **Property compliance_status sync** | For each property, recomputes status from requirements (RED if any OVERDUE, else AMBER if any EXPIRING_SOON, else GREEN) and updates `properties.compliance_status`; sends alerts on degradation. | `server.py` ~455–469: `run_compliance_status_check` at 08:00 and 18:00 UTC | `run_compliance_status_check()` → `JobScheduler.check_compliance_status_changes()` in `services/jobs.py` (~323) |

Score is **not** computed during provisioning. Provisioning creates requirements and calls `_update_property_compliance` per property after creating requirements; it does **not** call `calculate_compliance_score`.

---

### 5) Truth table

| Question | Answer | Where (evidence) |
|----------|--------|-------------------|
| Upload triggers requirement update? | **Yes** | Client + admin upload both call `regenerate_requirement_due_date()` → `requirements.update_one(..., status=COMPLIANT, due_date=...)` (`documents.py` ~668, ~767, ~941) |
| Upload triggers score update? | **No** (no direct call) | Score updates only when something calls `calculate_compliance_score` (e.g. next `GET /api/client/compliance-score` or daily snapshot). Upload does not call it. |
| Upload triggers property compliance update? | **Yes** (after implementation) | After `regenerate_requirement_due_date`, both client and admin upload call `provisioning_service._update_property_compliance(property_id)` so `properties.compliance_status` is in sync. |
| Delete triggers requirement update? | **Yes** (after implementation) | `DELETE /api/documents/{id}` and `DELETE /api/documents/admin/{id}`: if the deleted doc was VERIFIED and no other VERIFIED doc exists for that requirement, requirement is set to PENDING and property compliance is updated. |
| Delete triggers score update? | **No** (no direct call) | Score updates on next `GET /api/client/compliance-score` (recompute from DB). |
| Dashboard recomputes on fetch? | **Yes for score** | Dashboard data comes from `GET /api/client/dashboard` (counts only). The **0–100 score** is returned by `GET /api/client/compliance-score`, which calls `calculate_compliance_score(user["client_id"])` on every request (`client.py` ~18). So “dashboard load” typically means the frontend also calls compliance-score, and that path **recomputes from DB** every time. |
| Any caching of live score? | **No** | No in-memory or response cache for `GET /api/client/compliance-score`. `compliance_score_history` is used only for trend/explanation, not for serving the “current” score. |

---

### 6) Verification pipeline

- **What sets `documents.status` to VERIFIED?**  
  Only `POST /api/documents/verify/{document_id}` (`routes/documents.py` ~801). It does:
  - `documents.update_one(..., {"$set": {"status": DocumentStatus.VERIFIED.value}})`
  - `requirements.update_one(..., {"$set": {"status": RequirementStatus.COMPLIANT.value}})`
  - If `document.property_id` is set, calls `provisioning_service._update_property_compliance(property_id)`.

- **Verification is admin-only.** The verify handler uses `admin_route_guard`. There is no client-side “self-verify” or automated verification in the audited code.

- **Can documents stay UPLOADED/PENDING forever?**  
  Yes. Until an admin calls verify (or reject), the document remains `UPLOADED` (client/admin upload sets `DocumentStatus.UPLOADED`). The app does not auto-verify. Surfaces: requirements and documents are shown in admin and client UIs with status; “awaiting verification” is implied by status not being VERIFIED. No separate “pending verification” flag was audited; the single source of truth is `documents.status`.

---

### 7) End-to-end proof scenario (minimal reproducible path)

**Scenario 1: Upload → verify → requirement status and score change**

1. **Upload doc (client or admin)**  
   - `POST /api/documents/upload` (or admin variant) with `property_id`, `requirement_id`, file.  
   - Code path: insert into `documents` (status `UPLOADED`), then `regenerate_requirement_due_date(requirement_id, client_id)` → requirement `status` = `COMPLIANT`, `due_date` advanced.  
   - **Requirement status:** PENDING → COMPLIANT.  
   - **Score:** Not recomputed in this request. Next `GET /api/client/compliance-score` will read DB (requirement COMPLIANT, document UPLOADED); only VERIFIED docs count toward document coverage, so document component does not yet count.

2. **Verify doc (admin)**  
   - `POST /api/documents/verify/{document_id}`.  
   - Code path: `documents.update_one` → status `VERIFIED`; `requirements.update_one` → status `COMPLIANT` (already COMPLIANT from upload); `_update_property_compliance(property_id)` → recomputes property from requirements and updates `properties.compliance_status`.  
   - **Requirement status:** remains COMPLIANT. **Document:** UPLOADED → VERIFIED. **Property:** compliance_status updated.

3. **Score change**  
   - Client calls `GET /api/client/compliance-score`.  
   - `calculate_compliance_score(client_id)` reads requirements (COMPLIANT), documents (one VERIFIED linked to requirement), properties. Document coverage and status components both reflect the verified doc.  
   - So: **upload + verify → requirement and document state updated in DB → score changes on next fetch** (recomputed from that state).

**Scenario 2: Delete doc → requirement revert → score revert**

- **Implemented:** `DELETE /api/documents/{document_id}` (client) and `DELETE /api/documents/admin/{document_id}` (admin). After delete, if the document was VERIFIED and no other VERIFIED doc exists for that requirement, `_revert_requirement_if_no_verified_docs` sets requirement to PENDING and calls `_update_property_compliance(property_id)`. Score changes on next `GET /api/client/compliance-score` (recomputed from DB).

---

## B) Gaps and implementation choices

- **Upload:** **Done.** After `regenerate_requirement_due_date`, both client and admin upload call `_update_property_compliance(property_id)`.

- **Delete:** **Done.** `DELETE /api/documents/{document_id}` (client) and `DELETE /api/documents/admin/{document_id}` (admin). On delete, if doc was VERIFIED and no other VERIFIED doc for that requirement, requirement set to PENDING and `_update_property_compliance(property_id)` called.

- **Reject:** **Done.** After setting document to REJECTED, if document has `requirement_id`, `_revert_requirement_if_no_verified_docs(db, requirement_id, property_id)` is called so requirement reverts to PENDING when no other verified doc exists, and property compliance is synced.

- **Score refresh:** Already recompute-on-fetch; no second truth source (needs_recalc + poller) added. No caching of live score.

Tests in `backend/tests/test_compliance_score_document_flows.py` cover upload (requirement + property compliance), delete (requirement revert), and admin upload (same as client).
