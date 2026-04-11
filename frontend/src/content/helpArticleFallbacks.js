/**
 * Client-side fallback copy when Help API has no matching published article yet.
 * Keep in sync with `backend/scripts/seed_kb_articles.py` entry for the same slug.
 */

export const HELP_ARTICLE_SLUG_INBOX_VISIBILITY_TODAY = 'how-inbox-visibility-works-today';

const INBOX_VISIBILITY_TODAY = {
  title: 'How inbox visibility works in Today',
  content: `## What Today is for

**Today** is your decision queue: it surfaces requirements, jobs, approvals, and issues that need attention. Each card links to the right place to act. Today helps you prioritise—it is not a replacement for completing work in Documents, Requirements, Jobs, or Issues.

## Mark reviewed in Today

**Mark reviewed in Today** removes the card from your open Today lists and records that you saw it there. It does **not** upload a document, satisfy a requirement, close a job, resolve an issue, or approve an invoice. Use the **primary action** on the card (for example **Upload certificate** or **View requirement**) to complete real work.

## Hide from Today (snooze)

**Hide from Today** for 1 or 7 days (shown as snooze on the card) temporarily removes the card from Today. When the period ends, the card can return if the item still needs attention. This only changes **Today visibility**—it does not change due dates, requirement status, jobs, issues, or documents.

## Hide from Today (dismiss)

**Hide from Today** with a reason (required, audited) removes the card until you **Show in Today again** from Hidden. It does **not** cancel obligations, delete evidence, complete a job, resolve an issue, or change compliance scores.

## What these actions do **not** change

Mark reviewed in Today, snooze, and dismiss do **not**:

- change requirement or document status in your portfolio record
- renew certificates or replace missing evidence
- progress or close a **job**
- fix or close an **issue**
- approve invoices (use Approvals and the card’s primary action instead)

## What actually resolves an item

An item clears from Today because the **underlying work** is done (or no longer applies)—for example a valid document is uploaded and accepted, a **requirement** is satisfied, a **job** reaches the right milestone, or an **issue** is handled in Operations. Follow the **primary action** on the card to get to the right screen and complete that work.

## Examples (click by click)

**Certificate / document item**

1. Open **Today** and find the requirement card (for example gas safety or EICR).
2. Use **Upload certificate** or **Upload document** (or the main button shown)—you are taken to **Documents** (or the upload flow) for that **requirement**.
3. Upload the file and complete any dates or fields. That updates your **document** and **requirement** record—not “Mark reviewed in Today” alone.

**Job item**

1. Open the **job** card on **Today**.
2. Use the main action (for example **Review job** or the next step shown). You go to the **job** detail in Operations.
3. Complete the step there (assign contractor, confirm visit, upload proof, etc.). The **job** record updates; inbox triage does not move the **job** forward.

**Issue item**

1. Open the **issue** card on **Today**.
2. Use **Log maintenance issue**, **View issue**, or the main action shown—you open the **issue** in Operations.
3. Work the **issue** there. Hiding or snoozing on Today only changes visibility; it does not fix the **issue**.

---

If you snoozed or hid something and want the card back, use **Show in Today again** from **Snoozed** or **Hidden** on **Today**.`,
};

const BY_SLUG = {
  [HELP_ARTICLE_SLUG_INBOX_VISIBILITY_TODAY]: INBOX_VISIBILITY_TODAY,
};

/**
 * @param {string|null|undefined} slug
 * @returns {{ title: string, content: string } | null}
 */
export function getHelpArticleFallback(slug) {
  if (!slug || typeof slug !== 'string') return null;
  return BY_SLUG[slug] || null;
}
