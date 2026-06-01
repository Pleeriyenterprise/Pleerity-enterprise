import React, { useState } from 'react';
import { AlertTriangle, Info } from 'lucide-react';
import { toast } from 'sonner';
import { adminAPI } from '../../../api/client';
import { useStepUpApi } from '../../../hooks/useStepUpApi';
import { runGovernedAdminMutation } from '../../../utils/adminGovernedMutation';
import { formatDisplayValue } from '../../../utils/apiErrorMessage';
import {
  classificationDescription,
  classificationLabel,
  recoveryModeLabel,
  RECOVERY_RISK_BADGE_CLASS,
} from '../../../utils/onboardingRecoveryAdmin';
import OnboardingRecoveryExecuteDialog from './OnboardingRecoveryExecuteDialog';

function SummaryRow({ label, value, testId }) {
  return (
    <div className="flex justify-between gap-3 py-1.5 border-b border-slate-100 last:border-0 text-xs">
      <span className="text-gray-600 shrink-0">{label}</span>
      <span className="font-medium text-gray-900 text-right" data-testid={testId}>
        {formatDisplayValue(value)}
      </span>
    </div>
  );
}

/**
 * Onboarding recovery assessment with governed Phase 2 execution when eligible.
 */
export default function OnboardingRecoveryAssessmentPanel({
  assessment,
  loading,
  error,
  clientId,
  onExecuted,
}) {
  const [executeMode, setExecuteMode] = useState(null);
  const stepUp = useStepUpApi();

  if (loading) {
    return (
      <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-3 text-sm text-blue-900" data-testid="onboarding-recovery-assessment-loading">
        Loading onboarding recovery assessment…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900" data-testid="onboarding-recovery-assessment-error">
        {formatDisplayValue(error, 'Failed to load recovery assessment')}
      </div>
    );
  }

  if (!assessment?.found) return null;

  const classification = assessment.classification;
  const recommendation = assessment.recommendation || {};
  const strategy = assessment.strategy || {};
  const state = assessment.state_summary || {};
  const risk = assessment.risk || 'low';
  const riskClass = RECOVERY_RISK_BADGE_CLASS[risk] || RECOVERY_RISK_BADGE_CLASS.medium;
  const executableModes = strategy.executable_modes || [];
  const canExecute = Boolean(assessment.execution_available && executableModes.length && clientId);

  const handleExecute = async (body) => {
    await stepUp.request(async (stepHeaders) => {
      await runGovernedAdminMutation({
        actionId: 'onboarding_recovery_execute',
        reason: body.reason,
        resourceKey: clientId,
        mutate: async (govHeaders) => {
          const res = await adminAPI.executeOnboardingRecovery(clientId, body, {
            headers: { ...stepHeaders, ...govHeaders },
          });
          const delivered = res.data?.execution?.continuation_delivered;
          if (delivered) {
            toast.success('Recovery executed — customer continuation path delivered');
          } else {
            toast.warning('Recovery executed — verify customer email delivery');
          }
          if (onExecuted) await onExecuted(res.data?.assessment);
          return res;
        },
      });
    });
  };

  return (
    <>
      <div
        className="rounded-lg border border-blue-200 bg-blue-50/40 p-4 space-y-3"
        data-testid="onboarding-recovery-assessment-panel"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-900">Onboarding recovery assessment</p>
            <p className="text-sm font-semibold text-midnight-blue mt-1" data-testid="recovery-classification-label">
              {classificationLabel(classification)}
            </p>
            <p className="text-xs text-blue-950/80 mt-1">{classificationDescription(classification)}</p>
          </div>
          <span className={`shrink-0 rounded border px-2 py-0.5 text-[10px] font-semibold uppercase ${riskClass}`} data-testid="recovery-risk-badge">
            {risk} risk
          </span>
        </div>

        {!classification && (
          <p className="text-sm text-gray-700" data-testid="recovery-no-action-needed">
            No stranded onboarding detected. Recovery orchestration is not required.
          </p>
        )}

        {classification && (
          <>
            <div className="rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-950 flex gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden />
              <div>
                <p className="font-semibold">Blockage</p>
                <p data-testid="recovery-blockage-summary">{recommendation.blockage_summary}</p>
              </div>
            </div>

            <div className="rounded-md border border-slate-200 bg-white p-3 space-y-0">
              <p className="text-xs font-semibold text-slate-700 uppercase tracking-wide mb-2">Recommended recovery</p>
              <SummaryRow label="Recommended action" value={recommendation.recommended_action} testId="recovery-recommended-action" />
              <SummaryRow label="Recovery mode" value={recoveryModeLabel(strategy.recommended_mode)} testId="recovery-recommended-mode" />
              <SummaryRow label="Expected customer outcome" value={recommendation.expected_customer_outcome} testId="recovery-expected-outcome" />
              <SummaryRow label="Operational impact" value={recommendation.operational_impact} testId="recovery-operational-impact" />
              <SummaryRow
                label="Eligible to run now"
                value={assessment.eligibility?.eligible ? (canExecute ? 'Yes' : 'No — review required') : 'No — review required'}
                testId="recovery-eligibility"
              />
              {!assessment.eligibility?.eligible && assessment.eligibility?.reason ? (
                <p className="text-xs text-amber-900 pt-2" data-testid="recovery-eligibility-reason">
                  {assessment.eligibility.reason}
                </p>
              ) : null}
            </div>

            {canExecute && (
              <div className="flex flex-wrap gap-2" data-testid="recovery-execute-actions">
                {executableModes.map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    className="rounded-md bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-700"
                    onClick={() => setExecuteMode(mode)}
                    data-testid={`recovery-execute-btn-${mode}`}
                  >
                    {recoveryModeLabel(mode)}
                  </button>
                ))}
              </div>
            )}
          </>
        )}

        {assessment.observability?.completion && (
          <div className="rounded-md border border-slate-200 bg-white p-3 space-y-1" data-testid="recovery-observability-completion">
            <p className="text-xs font-semibold text-slate-700 uppercase tracking-wide">Recovery completion</p>
            <p className="text-sm text-gray-800">{assessment.observability.completion.message}</p>
            <p className="text-xs text-gray-500">
              Status: <span className="font-mono">{assessment.observability.completion.status}</span>
            </p>
            {assessment.observability.events?.length > 0 && (
              <ul className="mt-2 space-y-1 max-h-32 overflow-y-auto">
                {assessment.observability.events.slice(0, 5).map((ev) => (
                  <li key={ev.event_id} className="text-xs text-gray-600 border-t border-slate-100 pt-1">
                    <span className="font-medium">{ev.event_type}</span>
                    {ev.mode ? ` · ${ev.mode}` : ''}
                    {ev.continuation_delivered != null
                      ? ` · delivered: ${ev.continuation_delivered ? 'yes' : 'no'}`
                      : ''}
                    <span className="block text-gray-400">{ev.created_at}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="rounded-md border border-slate-200 bg-white p-3 space-y-0">
          <p className="text-xs font-semibold text-slate-700 uppercase tracking-wide mb-2">Continuation status</p>
          <SummaryRow label="Payment status" value={state.subscription_status || state.billing_lifecycle_state || '—'} testId="recovery-payment-status" />
          <SummaryRow label="Onboarding stage" value={state.onboarding_status} testId="recovery-onboarding-stage" />
          <SummaryRow label="Password set" value={state.password_set == null ? '—' : state.password_set ? 'Yes' : 'No'} testId="recovery-password-set" />
          <SummaryRow label="Last checkout sent" value={state.checkout_link_sent_at || '—'} testId="recovery-last-checkout" />
          <SummaryRow label="Checkout still fresh" value={state.checkout_fresh ? 'Yes' : 'No'} testId="recovery-checkout-fresh" />
          <SummaryRow
            label="Recovery attempts logged"
            value={assessment.recovery_history?.recovery_attempt_count ?? 0}
            testId="recovery-attempt-count"
          />
        </div>

        <div className="rounded-md border border-blue-200 bg-blue-50 p-2 text-xs text-blue-950 flex gap-2">
          <Info className="h-4 w-4 shrink-0 mt-0.5" aria-hidden />
          <p data-testid="recovery-completion-rule">
            {assessment.completion_rule ||
              'Recovery is complete only when the customer has a valid, observable continuation path.'}
          </p>
        </div>

        {classification && (
          <p className="text-xs text-gray-600" data-testid="recovery-phase-note">
            Governed recovery actions above are audited. Recovery is complete only when the customer has an observable
            continuation path — not when internal state changes alone.
          </p>
        )}
      </div>

      {executeMode && (
        <OnboardingRecoveryExecuteDialog
          open={Boolean(executeMode)}
          onOpenChange={(open) => !open && setExecuteMode(null)}
          clientId={clientId}
          mode={executeMode}
          classification={classification}
          onSubmit={handleExecute}
        />
      )}
      {stepUp.modal}
    </>
  );
}
