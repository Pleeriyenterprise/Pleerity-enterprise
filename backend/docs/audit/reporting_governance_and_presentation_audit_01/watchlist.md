# Watchlist — post PHASE-03 (2026-06-04)

## VERIFIED_OPERATIONALLY

### Done
- Immutable PDF storage + deterministic re-download
- Lineage metadata + tenant-scoped artifact access
- Live vs immutable terminology in API headers and PDF

### P1
- [ ] Retention / archive policy for governed_report_pdf_artifacts GridFS growth
- [ ] Admin artifact listing UI with artifact_id re-download
- [ ] Backfill legacy reports rows without gridfs_id (optional one-time migration)

### P2
- [ ] Signed URL time-limited artifact download
- [ ] Manifest sidecar JSON per PDF artifact (checksum already in mongo)
