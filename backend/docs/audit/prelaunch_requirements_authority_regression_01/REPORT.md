# PRELAUNCH-REQUIREMENTS-AUTHORITY-REGRESSION-01

Classification: **PARTIAL**

Root cause: main Requirements page used `projection=list` which sets `enrichment_deferred: true` and skips `enrich_requirements_for_client` (take_action, why_it_matters, operational_cognition).

Fix: RequirementsPage requests `projection=full` via dedicated operational cache key.

Blockers: generic_upload_document_drift
