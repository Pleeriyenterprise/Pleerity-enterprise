---
title: Admin Console Overview
slug: admin-console-overview
audience: ADMIN
category_id: admin-console
module: Admin Console
excerpt: Where to find everything in the admin application: main sections, key pages, and how to reach clients, billing, automation, and content.
tags: admin, console, navigation, dashboard, sections
status: draft
---

# Admin Console Overview

**Audience:** ADMIN (internal staff)  
**Category:** Admin Console  
**Module:** Admin Console  
**Summary:** Where to find everything in the admin application: main sections, key pages, and how to reach clients, billing, automation, and content.

---

## Purpose

The Admin Console is the internal application for managing clients, services, operations, and system health. This guide maps the sidebar sections to the tasks you need (e.g. find a client, check onboarding, monitor reminder jobs, edit help content) so you can get to the right page quickly.

---

## When to use this guide

- You are new to the admin application.
- You need to find where to do a specific task (e.g. “Where do I check onboarding status?” or “Where do I see reminder job health?”).
- You want a single reference for the main menu structure.

---

## Steps

1. **Log in** as admin (e.g. **Login → Admin** or `/login/admin`). You should land on the Admin Dashboard or Overview.
2. **Use the sidebar** — Main sections are: **Dashboard**, **Customers**, **Products & Services**, **Operations & Compliance**, **ClearForm**, **Content Management**, **Support**, **Settings & System**. Some items are owner/admin-only (e.g. Analytics, Operations).
3. **Find a client** — Go to **Customers → Clients** (or **Dashboard**, then open the **Clients** tab). Use the **global search** (top) or browse the list. Search by name or email; click a result to open that client.
4. **Check onboarding / provisioning** — When viewing a client or their record, look for onboarding or setup status. Post-payment setup status can also be checked via the portal setup-status flow (support/ops procedure).
5. **Manage billing and plans** — **Products & Services → Pricing & Billing** (or **Pending Payments**). Use this to see or change plans and pending payments.
6. **Monitor automation and reminders** — **Settings & System → Automation Control Centre** (or **System Health**). Here you see scheduled jobs (e.g. **daily_reminders**), last run, next run, and status. Use **Run Now** only for recovery or testing.
7. **Check email / notification health** — **Settings & System → Notification Health** (or the **Email delivery** tab on the main dashboard). Use this to see delivery issues or message logs.
8. **Edit help content** — **Content Management → Knowledge Centre**. Create or edit articles; set audience (USER / ADMIN / STAFF) and category. Keep internal docs as ADMIN or STAFF so they do not appear in the client Help Centre.
9. **View incidents** — **Settings & System → Incidents**. Open incidents for missed jobs, stale heartbeat, or delivery issues; acknowledge or resolve as appropriate.

---

## What happens next

- From the client search or list you can perform client-specific actions (e.g. resend invite, view in portal) depending on your role and the UI.
- **Automation Control Centre** shows job states (healthy, degraded, never ran). Do not rely on “Run Now” for routine operation; reminders and other jobs run on schedule.
- Knowledge Centre articles with **audience = USER** appear in the client **Help Centre** (`/help`); ADMIN/STAFF articles stay in the admin Knowledge Centre only.

---

## Common mistakes / troubleshooting

- **Wrong portal:** Ensure you are on the Admin login, not the Client portal.
- **Missing menu items:** Some sections (e.g. Analytics, Operations & Compliance) may be restricted to owner or admin roles.
- **Run Now overuse:** “Run Now” in **Automation Control Centre** is for recovery or testing only. Do not run reminder jobs manually on a daily basis.

---

## Related guides

- Reviewing Onboarding Status  
- How Provisioning Works  
- How to Monitor Reminder Jobs  
- How to Review Email Failures  
- Failed Provisioning Recovery (playbook)  

---

**Verification status:** Draft. Needs product review (e.g. exact tab names on Admin Dashboard and which items are owner-only).
