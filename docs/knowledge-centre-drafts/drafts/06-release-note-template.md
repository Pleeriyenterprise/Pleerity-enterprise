---
title: Release Note (Template)
slug: release-note-template
audience: ADMIN
category_id: release-notes
module: Release Notes
article_type: release_notes
excerpt: Template for version release notes. Use this structure when publishing a new version; do not publish this template as a real release note.
tags: release notes, template, version, changelog
status: draft
---

# Release Note (Template)

**Audience:** USER or ADMIN (choose per release)  
**Category:** Release Notes  
**Module:** Release Notes  
**Summary:** Template for version release notes. Use this structure when publishing a new version; fill in version, date, changes, and affected modules. Do not publish this template as a real release note.

---

## Purpose

Release notes inform users and staff what changed in a given version: new features, improvements, and bug fixes. This template ensures a consistent format and helps authors include version, date, and affected areas.

---

## When to use this guide

- You are publishing a new product version (e.g. 1.3, 1.4).
- You need a standard structure for “What’s new” or “Changelog” in the Knowledge Centre.
- You want to record **release_version**, **release_date**, **changes** (list), and **affected_modules** for the article (if your Knowledge Centre supports release note fields).

---

## Template structure

**Version:** [e.g. 1.3]  
**Release date:** [e.g. 2025-03-15]  

**Changes:**
- [e.g. Added Compliance Score Trend chart]
- [e.g. Improved evidence upload flow]
- [e.g. Fixed reminder scheduling bug]

**Affected modules:** [e.g. Compliance Score, Evidence Upload, Reminders]

---

## Steps (for authors)

1. Create a new Knowledge Centre article (or duplicate this template).
2. Set **Article type** to **Release Notes** (if your system has this type).
3. Fill **Release version** and **Release date**.
4. In **Content**, write a short paragraph and a bullet list of changes. In **Changes** (if the article model has it), add each change as a list item. In **Affected modules**, list the product areas (e.g. Dashboard, Compliance, Reminders).
5. Set **Audience** to USER (for client-facing releases) or ADMIN (for internal-only releases).
6. Set **Status** to **Draft** until reviewed; then **Publish** when the release is live.
7. Do not publish this template article itself; it is for reference only.

---

## What happens next

- Published release notes appear in the Knowledge Centre (and optionally in Help Centre if audience is USER). Users can search for “release” or the version number.
- Keeping release notes over time gives a clear history of product changes and helps support answer “when did X change?”

---

## Common mistakes / troubleshooting

- **Publishing the template:** Ensure you create a *new* article for each version and do not publish the “Release Note (Template)” article.
- **Wrong audience:** If the release is only for admin/internal, set audience to ADMIN so it does not appear in the client Help Centre.

---

## Related guides

- Admin Console Overview  
- Knowledge Centre (how to create and publish articles)  

---

**Verification status:** Draft. This is a template only; no product behaviour to verify. Confirm that your Knowledge Centre supports article_type “release_notes” and the fields release_version, release_date, changes, affected_modules before using. Product name (e.g. Compliance Vault Pro) may vary by deployment.
