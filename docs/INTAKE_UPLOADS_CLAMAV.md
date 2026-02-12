# Intake Uploads & ClamAV

## Overview

The **Preferences & Consents** step of the intake flow allows users to either **Upload Here** (multi-file) or **Email to Pleerity**. Uploaded files are stored as **IntakeUploads** (temporary), scanned with **ClamAV**, and after successful payment and provisioning, **CLEAN** files are migrated into the client's document vault.

## Running ClamAV locally

### Option 1: clamscan (CLI, no daemon)

1. **Install ClamAV** (e.g. on Ubuntu/Debian):
   ```bash
   sudo apt-get update && sudo apt-get install clamav clamav-daemon
   # Optional: freshclam to update virus definitions
   sudo freshclam
   ```
2. **Verify**:
   ```bash
   clamscan --version
   ```
3. The backend uses `clamscan` by default when no daemon socket is configured. No env vars required.

### Option 2: clamd (daemon, recommended for production)

1. Install and start the daemon:
   ```bash
   sudo apt-get install clamav clamav-daemon
   sudo systemctl start clamav-daemon
   sudo freshclam  # update definitions
   ```
2. **Socket path**: typically `/var/run/clamav/clamd.ctl` (or `clamd.sock`).
3. Set the backend env var so the app uses the daemon:
   ```bash
   export CLAMAV_SOCKET=/var/run/clamav/clamd.ctl
   ```
   If the socket path differs on your system, set `CLAMAV_SOCKET` to that path.

### Docker / dev without ClamAV

If ClamAV is **not** installed or not on `PATH`, the scanner treats the file as **QUARANTINED** (safe default). So in dev you can run without ClamAV; uploads will be marked QUARANTINED and will **not** be migrated to the vault until you install ClamAV and re-upload (or change behaviour for dev).

## Environment / config

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAMAV_SOCKET` | Path to clamd socket (if set and exists, clamdscan is used) | (none) |
| `INTAKE_UPLOAD_DIR` | Directory for intake upload files | `/app/uploads/intake` |
| `INTAKE_QUARANTINE_DIR` | Directory for quarantined files | `/app/uploads/intake_quarantine` |
| `DOCUMENT_STORAGE_PATH` | Vault path for migrated documents | `/app/data/documents` |

## File limits (authoritative on server)

- **Allowed types**: PDF, JPG, PNG, DOCX.
- **Max per file**: 20MB.
- **Max per intake session**: 200MB total.

## Status flow

- **UPLOADED** → **SCANNING** → **CLEAN** or **QUARANTINED** (or **FAILED**).
- Only **CLEAN** uploads are migrated after provisioning.
- **QUARANTINED** files are moved to `INTAKE_QUARANTINE_DIR` and are not migrated; they can be deleted by the user from the list.

## Migration

- Triggered in **provisioning** (after payment and successful portal provisioning).
- Idempotent: only uploads with status CLEAN and no `migrated_to_document_id` are processed.
- Quarantined uploads are never migrated.
