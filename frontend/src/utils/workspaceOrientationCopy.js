/**
 * Workspace orientation — customer mental model (portfolio vs inbox vs evidence).
 * Presentation only; does not change APIs, authority, or scoring semantics.
 * @see docs/governance/PRESENTATION_LANGUAGE_GOVERNANCE.md (operational orientation)
 */

/** @param {string | null | undefined} fullName */
export function workspaceDashboardWelcomeLead(fullName) {
  const who = fullName && String(fullName).trim() ? String(fullName).trim() : 'there';
  return `Welcome, ${who}. Portfolio-wide health, attention counts, and trends — overview and KPIs only, not your full task list.`;
}

export const WORKSPACE_TODAY_PRIMARY =
  'Your operational inbox: prioritised deadlines and next actions. Each card opens the linked workspace (requirements, jobs, documents, approvals, issues). Primary actions move real work forward; options under More only change what appears on Today.';

export const WORKSPACE_TODAY_VS_DASHBOARD =
  'Different from Dashboard: Today is for doing the next task; Dashboard is the portfolio snapshot and score trend context.';

export const WORKSPACE_COMMAND_CENTER_PRIMARY =
  'Single-screen portfolio triage — verdict, drivers, and ranked next steps. Execution stays in Today, Requirements, Documents, and Jobs.';

export const WORKSPACE_DOCUMENTS_SUBTITLE =
  'Evidence vault — files are stored here first. Linked requirements and your compliance score update after you confirm extracted details (when applicable) and after any propagation or score recalculation catches up.';

export const WORKSPACE_DOCUMENTS_EMPTY_DESCRIPTION =
  'Upload certificates or proof here first. Linked requirements and your score update after you confirm extracted dates and the system applies them — not the instant the file lands.';

export const WORKSPACE_REQUIREMENTS_DESCRIPTION_DEFAULT =
  'Tracked legal and safety obligations per property. Dates and evidence here feed overdue counts and scoring rules; upload files on Documents, then confirm status here.';

export const WORKSPACE_REQUIREMENTS_DESCRIPTION_DUE_SOON =
  'Tracked items expiring soon that need attention before they become overdue.';

export const WORKSPACE_REQUIREMENTS_DESCRIPTION_OVERDUE_OR_MISSING =
  'Overdue or missing tracked items — upload or renew on Documents, confirm details when prompted, then allow time for scoring and Command Center to refresh.';

/** @param {string | number} windowDays */
export function workspaceRequirementsDescriptionWindow(windowDays) {
  return `Tracked items with deadlines within the next ${windowDays} days.`;
}

export const WORKSPACE_REQUIREMENTS_EMPTY_DESCRIPTION =
  'No tracked items match this filter. Try “All requirements”, clear the search, or upload evidence on Documents and refresh.';

export const WORKSPACE_COMMAND_CENTER_ALL_CLEAR_SECONDARY =
  'This snapshot is intentionally calm. Open Today for the next actionable item, or Dashboard for portfolio trends.';

export const WORKSPACE_PROPERTY_SCORE_STRIP_FOOTNOTE =
  'This headline is the stored property score. Uploads and requirement edits reach it after evidence is confirmed and any recalculation runs — scores are not live tickers.';
