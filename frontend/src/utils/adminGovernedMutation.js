import { adminAPI } from '../api/client';
import { getAdminActionPolicy } from './adminActionGovernance';

const CONFIRMATION_HEADER = 'X-Admin-Confirmation-Token';

/**
 * Issue confirmation token then run governed admin mutation with audit headers.
 */
export async function runGovernedAdminMutation({
  actionId,
  reason,
  resourceKey,
  mutate,
}) {
  const policy = getAdminActionPolicy(actionId);
  if (policy?.requires_reason && String(reason || '').trim().length < 10) {
    throw new Error('A support reason of at least 10 characters is required.');
  }
  let headers = {};
  if (policy?.requires_confirmation) {
    const tokenRes = await adminAPI.issueConfirmationToken({
      action_id: actionId,
      reason: reason?.trim(),
      resource_key: resourceKey || undefined,
    });
    const token = tokenRes.data?.token;
    if (!token) throw new Error('Failed to obtain confirmation token');
    headers = { [CONFIRMATION_HEADER]: token };
  }
  return mutate(headers);
}

export { CONFIRMATION_HEADER };
