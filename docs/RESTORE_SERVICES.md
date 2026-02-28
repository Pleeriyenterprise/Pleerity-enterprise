# Restore Services (AI & Automation, Market Research, Document Packs, Compliance Audits)

This restores the four service category pages and their service detail pages so `/services/ai-automation`, `/services/market-research`, `/services/document-packs`, and `/services/compliance-audits` show content and link to the order intake.

## Automatic seeding (no intervention required)

**On every backend startup**, the server runs:

1. **Service catalogue V2** — seeded from code (idempotent).
2. **CMS pages** — hub, four category pages, and one SERVICE page per catalogue entry (idempotent; skips existing).

So after you **deploy or restart the backend**, the live site will get the catalogue and CMS pages without running any script manually. First deploy or an empty DB will create everything; later restarts just skip existing records.

## Manual run (optional)

If you need to run the seed without restarting the server (e.g. to fix a missing page), from the **backend** directory:

```bash
python scripts/restore_services.py
```

Or seed only CMS pages (if the catalogue is already populated):

```bash
python scripts/seed_cms_pages.py
```

**Prerequisites:** MongoDB reachable; `MONGO_URL` and `DB_NAME` set (e.g. in `.env` in the backend directory).

**In Docker / production:** Run the same command in the backend container or in a one-off job that has access to the same MongoDB and env.

## After running

- **Hub:** `/services` — lists the four categories.
- **Category pages:** `/services/ai-automation`, `/services/market-research`, `/services/document-packs`, `/services/compliance-audits` — each lists that category’s services with pricing.
- **Service pages:** e.g. `/services/document-packs/essential-landlord-document-pack` — detail + “Start Now” CTA to `/order/intake?service=DOC_PACK_ESSENTIAL`.

No CVP code or provisioning is changed; see `docs/SERVICES_AI_MARKETRESEARCH_DOCPACKS_AUDIT.md` (Impact on CVP).
