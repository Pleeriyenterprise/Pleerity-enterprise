import React from 'react';
import { Link } from 'react-router-dom';
import { redemptionStatusBadgeClass } from '../../../utils/pilotRedemptionAdmin';

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-GB');
  } catch {
    return String(iso);
  }
}

function SummaryRow({ label, value, testId }) {
  return (
    <div className="flex justify-between gap-3 py-1.5 border-b border-slate-100 last:border-0 text-xs">
      <span className="text-gray-600 shrink-0">{label}</span>
      <span className="font-medium text-gray-900 text-right" data-testid={testId}>
        {value ?? '—'}
      </span>
    </div>
  );
}

/**
 * Read-only promo/onboarding state from API (no client-side eligibility logic).
 */
export default function PromoRecoveryStateSummary({
  inviteMetadata = {},
  indicators = {},
  latestRedemption,
  accountHints = {},
  inviteCode,
}) {
  const meta = inviteMetadata || {};
  const code = inviteCode || meta.pilot_invite_code;
  const onboarding = accountHints.onboarding_stage || meta.onboarding_status;
  const subscription = accountHints.subscription_status || meta.subscription_status;
  const billingLc = accountHints.billing_lifecycle_state || meta.billing_lifecycle_state;
  const provisioning = accountHints.provisioning_status || meta.provisioning_status;

  const latestStatus = latestRedemption?.status;
  const retryLabel =
    latestRedemption == null
      ? '—'
      : latestRedemption.retry_eligible
        ? 'Eligible to retry'
        : 'Blocked — release or override required';

  return (
    <div
      className="rounded-lg border border-slate-200 bg-slate-50/80 p-3 space-y-0"
      data-testid="promo-recovery-state-summary"
    >
      <p className="text-xs font-semibold text-slate-700 uppercase tracking-wide mb-2">Current state</p>
      <SummaryRow
        label="Invite / promo code"
        testId="summary-invite-code"
        value={
          code ? (
            <Link className="text-teal-700 hover:underline" to={`/admin/pilot-invites/${encodeURIComponent(code)}`}>
              {code}
            </Link>
          ) : (
            '—'
          )
        }
      />
      <SummaryRow label="Campaign" value={meta.campaign_name || '—'} />
      <SummaryRow label="Code type" value={meta.pilot_code_type || '—'} />
      <SummaryRow
        label="Latest redemption status"
        testId="summary-redemption-status"
        value={
          latestStatus ? (
            <span className={`px-1.5 py-0.5 rounded ${redemptionStatusBadgeClass(latestStatus)}`}>
              {latestStatus}
            </span>
          ) : (
            'No attempts'
          )
        }
      />
      <SummaryRow label="Retry eligibility" testId="summary-retry-eligibility" value={retryLabel} />
      <SummaryRow label="Onboarding status" testId="summary-onboarding-status" value={onboarding} />
      <SummaryRow label="Provisioning" value={provisioning} />
      <SummaryRow label="Subscription" value={subscription} />
      <SummaryRow label="Billing lifecycle" value={billingLc} />
      <SummaryRow
        label="Onboarding fee policy"
        value={meta.onboarding_fee_policy || (meta.onboarding_fee_waived ? 'waived' : '—')}
      />
      {latestRedemption?.failure_reason && (
        <SummaryRow label="Failure reason" testId="summary-failure-reason" value={latestRedemption.failure_reason} />
      )}
      {latestRedemption?.created_at && (
        <SummaryRow label="Last attempt" value={formatDate(latestRedemption.created_at)} />
      )}
      {indicators.first_time_bypass_active && (
        <p className="text-xs text-indigo-800 mt-2 font-medium" data-testid="summary-first-time-bypass">
          Active first-time bypass override
        </p>
      )}
      {indicators.waiver_active && (
        <p className="text-xs text-indigo-800 mt-1 font-medium" data-testid="summary-waiver-active">
          Active onboarding waiver override
        </p>
      )}
    </div>
  );
}
