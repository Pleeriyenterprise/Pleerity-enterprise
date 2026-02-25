# Restore Services (AI & Automation, Market Research, Document Packs, Compliance Audits)

This restores the four service category pages and their service detail pages so `/services/ai-automation`, `/services/market-research`, `/services/document-packs`, and `/services/compliance-audits` show content and link to the order intake.

## What it does

1. **Seed service catalogue V2** — Inserts all service definitions (AI, Market Research, Compliance, Document Packs, etc.) into the `service_catalogue_v2` collection if not already present. Idempotent.
2. **Seed CMS pages** — Creates the Services Hub page, the four category pages, and one CMS service page per catalogue entry (linked by `service_code`). All are created as **published**. Idempotent (skips existing).

## How to run

**Prerequisites:** MongoDB reachable; `MONGO_URL` and `DB_NAME` set (e.g. in `.env` in the backend directory).

From the **backend** directory:

```bash
python scripts/restore_services.py
```

Or seed only CMS pages (if the catalogue is already populated, e.g. after the app has started at least once):

```bash
python scripts/seed_cms_pages.py
```

**In Docker / production:** Run the same command in the backend container or in a one-off job that has access to the same MongoDB and env.

## After running

- **Hub:** `/services` — lists the four categories.
- **Category pages:** `/services/ai-automation`, `/services/market-research`, `/services/document-packs`, `/services/compliance-audits` — each lists that category’s services with pricing.
- **Service pages:** e.g. `/services/document-packs/essential-landlord-document-pack` — detail + “Start Now” CTA to `/order/intake?service=DOC_PACK_ESSENTIAL`.

No CVP code or provisioning is changed; see `docs/SERVICES_AI_MARKETRESEARCH_DOCPACKS_AUDIT.md` (Impact on CVP).
