/**
 * Issue lifecycle authority — shared open/terminal semantics for Issues UI.
 * Aligns with backend document_linkage_lifecycle_authority + maintenance_issues_service.
 */

export const TERMINAL_ISSUE_STATUSES = new Set(['resolved', 'closed', 'cancelled']);

export const OPEN_ISSUE_STATUSES = new Set([
  'open',
  'new',
  'triaged',
  'monitoring',
  'investigating',
  'ready_for_work_order',
  'in_progress',
]);

export function isTerminalIssueStatus(status) {
  return TERMINAL_ISSUE_STATUSES.has(String(status || '').toLowerCase());
}

export function isOpenIssueStatus(status) {
  return OPEN_ISSUE_STATUSES.has(String(status || '').toLowerCase());
}

/**
 * Resolved linkage/compliance issue — prefer evidence destination over empty document queue.
 */
export function resolvedIssueEvidenceUrl(issue) {
  const rid = issue?.resolution_linked_requirement_id;
  const pid = issue?.resolution_linked_property_id || issue?.property_id;
  if (rid && pid) {
    return `/documents?property_id=${encodeURIComponent(pid)}&requirement_id=${encodeURIComponent(rid)}`;
  }
  const cog = issue?.operational_cognition?.primary_action;
  if (cog?.url && isTerminalIssueStatus(issue?.status)) return cog.url;
  return null;
}
