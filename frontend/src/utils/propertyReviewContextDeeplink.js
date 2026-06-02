/**
 * Parse property-page query params for compliance review context convergence.
 * Queue deeplinks use `resolve_requirement` (see review_queue_service.build_queue_row_payload).
 */
export function parsePropertyReviewContextDeeplink(search) {
  const q = new URLSearchParams(search || '');
  const resolveRid = (q.get('resolve_requirement') || '').trim();
  if (resolveRid) {
    return {
      kind: 'review_context',
      requirementId: resolveRid,
      focusSubmission: true,
    };
  }
  return null;
}
