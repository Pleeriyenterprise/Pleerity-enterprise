# customer_reference Verification Report

## 1) Every place customer_reference is SET (file + line)

| File | Line | Action |
|------|------|--------|
| `backend/routes/intake.py` | 746 | **SET**: `Client(customer_reference=None)` when creating client at intake submit |
| `backend/routes/intake.py` | 886 | **SET**: Response body `"customer_reference": None` returned from POST /api/intake/submit |
| `backend/services/crn_service.py` | 69 | **SET**: `db.clients.update_one(..., {"$set": {"customer_reference": crn}})` in `ensure_client_crn()` |

No other assignments: the field is only written in intake (client creation) and in `crn_service` (update after payment).

---

## 2) First place customer_reference is created during POST /api/intake/submit

- **First (and only) assignment during submit**: `backend/routes/intake.py` line **746**  
  `Client(customer_reference=None)` when building the new client document before `insert_one`.

- **Why it can be null**: By design, CRN was assigned only on **payment confirmation** (Stripe `checkout.session.completed`). The flow was: intake creates client with `customer_reference=None` → user goes to checkout → on successful payment the webhook calls `ensure_client_crn(client_id)` which generates a CRN and updates the client. So between submit and payment, `customer_reference` is null.

- **Code path**: Submit handler creates `Client(..., customer_reference=None)`, dumps to `client_doc`, `insert_one(client_doc)`, then returns `"customer_reference": None`. No CRN is generated or set in this path.

---

## 3) Exact format/spec of customer_reference

- **Format**: `PLE-CVP-{year}-{seq:06d}`  
  Defined in `backend/services/crn_service.py`: `CRN_FORMAT = "PLE-CVP-{year}-{seq:06d}"`.

- **Examples**:
  - `PLE-CVP-2026-000001`
  - `PLE-CVP-2026-000002`
  - `PLE-CVP-2027-000001` (first of next year)

- **Rules**:
  - **Prefix**: `PLE-CVP`
  - **Year**: 4-digit UTC year from `datetime.now(timezone.utc).year`
  - **Sequence**: 6-digit zero-padded integer, per-year atomic counter in MongoDB `counters` collection, document `_id`: `crn_seq_YYYY`, field `seq` incremented with `$inc`
  - **Padding**: Exactly 6 digits (`:06d`)
  - **Randomness**: None; purely sequential per year. Concurrency-safe via `find_one_and_update` with `$inc`.

- **Customer-facing CRN**: Yes. Stored in `clients.customer_reference` and exposed as CRN in admin, billing, and support APIs.

---

## 4) Database constraints

- **Where defined**: `backend/database.py` in `_create_indexes()` (around line 46):

  ```python
  await self.db.clients.create_index("customer_reference", unique=True, sparse=True)
  ```

- **Sparse**: Yes. `sparse=True` means only documents that **have** the `customer_reference` field are included in the index; documents without the field (or with null) are not. So multiple clients can have null/missing `customer_reference` without violating uniqueness.

- **Recommendation**: After the fix that sets `customer_reference` before insert, every client will have a CRN. Keeping `unique=True, sparse=True` is still correct: it allows the index to ignore any legacy or edge-case docs without the field and enforces uniqueness for all set values. No change required. If you later enforce non-null at the application layer and backfill all nulls, you could switch to a non-sparse unique index; until then, sparse is appropriate.

---

## 5) Fix: customer_reference never null

**Approach**: Assign CRN at intake **before** insert using the existing concurrency-safe `get_next_crn()`, set it on the client document, and return it in the response. Payment webhook continues to call `ensure_client_crn()`; it remains idempotent (if CRN already set, returns it).

**Code changes** (see patch below):

1. **Intake** (`backend/routes/intake.py`): Before creating the client, call `get_next_crn()`, then pass that value into `Client(customer_reference=crn)` and return it in the JSON response instead of `None`.
2. **Model** (`backend/models/core.py`): Keep `customer_reference: Optional[str] = None` for backward compatibility with any code that still reads the field before assignment; at intake we now always pass a value.
3. **CRN service**: No change; `ensure_client_crn()` already returns existing CRN if present.
4. **Tests**: Expect non-null `customer_reference` in submit response; assert format `PLE-CVP-YYYY-NNNNNN` (6-digit suffix). Fix test that expected 5-digit suffix and "0" not in suffix to match real format.

**Concurrency**: `get_next_crn()` uses `find_one_and_update` with `$inc` on the counter document, so each call gets a unique sequence number; safe under concurrent intake submissions.

---

*Implementation applied in the same change set as this document.*
