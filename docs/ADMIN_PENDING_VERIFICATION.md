# Admin Pending Verification (Operational Safeguards)

This document describes the admin-only pending verification workflow: the query used to list documents awaiting verification and the database indexes that support it.

## Purpose

Documents with status `UPLOADED` require admin verification before they affect compliance. To avoid documents staying in `UPLOADED` indefinitely, we expose:

- **Admin list:** `GET /api/admin/documents/pending-verification` — documents with `status: UPLOADED` and `uploaded_at` older than a given number of hours, optionally filtered by `client_id`, paginated.
- **Dashboard badge:** `unverified_documents_count` in the admin dashboard (count of all `UPLOADED` documents).
- **Daily digest:** Email to OWNER/ADMIN with counts only (no PII), plus audit log.

## Query

The pending-verification list endpoint runs:

1. **Count:** `db.documents.count_documents(query)` for `total`.
2. **List:** `db.documents.find(query).sort("uploaded_at", 1).skip(skip).limit(limit)` for the page.

Where:

- `query = { "status": "UPLOADED", "uploaded_at": { "$lte": cutoff_iso } }`, and optionally `query["client_id"] = client_id`.
- `cutoff_iso` is `(now_utc - timedelta(hours=hours)).isoformat()`.
- **Sort:** `uploaded_at` ascending (oldest first), so the longest-waiting documents appear first.

## Indexes

Two indexes on the `documents` collection support this:

| Index | Keys | Use case |
|-------|------|----------|
| General list | `{ status: 1, uploaded_at: 1 }` | Query without `client_id`; supports filter on status and range on `uploaded_at`, and sort by `uploaded_at`. |
| By client | `{ client_id: 1, status: 1, uploaded_at: 1 }` | Query with `client_id`; supports equality on client_id and status, range on `uploaded_at`, and sort by `uploaded_at`. |

Both are created at application startup in `database._create_indexes()`.

## RBAC and pagination

- **RBAC:** Both the dashboard and the pending-verification list require OWNER or ADMIN (`require_owner_or_admin`).
- **Pagination:** List supports `limit` (default 50, max 200) and `skip` (default 0). Response includes `total`, `returned`, and `has_more`.
