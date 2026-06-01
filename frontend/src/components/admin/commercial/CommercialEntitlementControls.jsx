import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';
import { adminAPI } from '../../../api/client';
import { useStepUpApi } from '../../../hooks/useStepUpApi';
import { runGovernedAdminMutation } from '../../../utils/adminGovernedMutation';
import { formatDisplayValue } from '../../../utils/apiErrorMessage';
import {
  commercialActionLabel,
  COMMERCIAL_RISK_BADGE_CLASS,
} from '../../../utils/commercialEntitlementAdmin';
import CommercialEntitlementExecuteDialog from './CommercialEntitlementExecuteDialog';

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
 * Commercial Controls — governed entitlement exceptions (Phase 2C).
 */
export default function CommercialEntitlementControls({ clientId, enabled = true }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [assessment, setAssessment] = useState(null);
  const [observability, setObservability] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const stepUp = useStepUpApi();

  const reload = useCallback(async () => {
    if (!clientId || !enabled) return;
    setLoading(true);
    setError('');
    try {
      const [aRes, oRes] = await Promise.all([
        adminAPI.getCommercialEntitlementAssessment(clientId),
        adminAPI.getCommercialEntitlementObservability(clientId),
      ]);
      setAssessment(aRes.data);
      setObservability(oRes.data);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load commercial controls');
    } finally {
      setLoading(false);
    }
  }, [clientId, enabled]);

  useEffect(() => {
    reload();
  }, [reload]);

  const handleExecute = async (body) => {
    await stepUp.request(async (stepHeaders) => {
      await runGovernedAdminMutation({
        actionId: 'commercial_entitlement_execute',
        reason: body.reason,
        resourceKey: clientId,
        mutate: async (govHeaders) => {
          const res = await adminAPI.executeCommercialEntitlement(clientId, body, {
            headers: { ...stepHeaders, ...govHeaders },
          });
          toast.success('Commercial entitlement action applied');
          await reload();
          return res;
        },
      });
    });
  };

  if (!enabled || !clientId) return null;

  const classification = assessment?.classification || {};
  const access = assessment?.access || {};
  const active = assessment?.active_governance;
  const executable = assessment?.executable_actions || [];
  const risk = classification.commercial_risk || 'low';
  const riskClass = COMMERCIAL_RISK_BADGE_CLASS[risk] || COMMERCIAL_RISK_BADGE_CLASS.low;

  return (
    <section
      className="rounded-xl bg-white border border-indigo-200/90 shadow-sm"
      data-testid="commercial-entitlement-controls"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-indigo-50/40 rounded-xl transition-colors"
        aria-expanded={open}
      >
        <div className="flex items-start gap-2">
          {active && <AlertTriangle className="h-5 w-5 text-indigo-600 shrink-0 mt-0.5" aria-hidden />}
          <div>
            <div className="text-sm font-semibold text-midnight-blue">Commercial Controls</div>
            <div className="text-xs text-gray-500 mt-0.5">
              Governed grace, billing suspension, sponsorship, and continuity — one active exception per account.
            </div>
          </div>
        </div>
        <ChevronDown className={`h-5 w-5 shrink-0 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {error && (
        <div className="px-4 pb-2 text-xs text-red-700" data-testid="commercial-controls-error">
          {formatDisplayValue(error)}
        </div>
      )}

      {open && (
        <div className="px-4 pb-4 space-y-4 border-t border-indigo-100/80">
          {loading && (
            <p className="text-sm text-gray-600" data-testid="commercial-controls-loading">
              Loading commercial entitlement assessment…
            </p>
          )}
          {!loading && assessment?.found && (
            <>
              <div className="rounded-lg border border-indigo-200 bg-indigo-50/40 p-3 space-y-2">
                <div className="flex justify-between gap-2">
                  <p className="text-xs font-semibold uppercase text-indigo-900">Governance assessment</p>
                  <span className={`shrink-0 rounded border px-2 py-0.5 text-[10px] font-semibold uppercase ${riskClass}`}>
                    {risk} risk
                  </span>
                </div>
                <SummaryRow label="Governance state" value={classification.governance_state} testId="commercial-governance-state" />
                <SummaryRow label="Canonical access" value={access.canonical_entitlement_state} testId="commercial-canonical-access" />
                <SummaryRow label="Access policy" value={access.access_policy} testId="commercial-access-policy" />
                <SummaryRow
                  label="Effective reason"
                  value={access.effective_access_reason || active?.effective_access_reason}
                  testId="commercial-effective-reason"
                />
                {active && (
                  <>
                    <SummaryRow label="Exception" value={active.exception_type} />
                    <SummaryRow label="Expires" value={active.entitlement_expiry_at} testId="commercial-expiry" />
                    <SummaryRow label="Stripe recon" value={active.stripe_reconciliation_status} />
                  </>
                )}
                {assessment.drift?.drift_detected && (
                  <p className="text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded p-2" data-testid="commercial-drift-warning">
                    Entitlement drift detected — run lightweight reconciliation from ops review.
                  </p>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                {executable.map((action) => (
                  <button
                    key={action}
                    type="button"
                    className="text-xs px-3 py-1.5 rounded-md border border-indigo-300 bg-white hover:bg-indigo-50 font-medium text-indigo-900"
                    onClick={() => setPendingAction(action)}
                    data-testid={`commercial-action-${action}`}
                  >
                    {commercialActionLabel(action)}
                  </button>
                ))}
              </div>

              {observability?.audit_events?.length > 0 && (
                <div className="rounded border border-slate-200 p-2">
                  <p className="text-xs font-semibold text-gray-700 mb-2">Recent audit</p>
                  <ul className="text-xs text-gray-600 space-y-1 max-h-32 overflow-y-auto">
                    {observability.audit_events.slice(0, 5).map((ev) => (
                      <li key={ev.event_id}>
                        {ev.event_type} — {ev.created_at?.slice(0, 19) || '—'}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}

      <CommercialEntitlementExecuteDialog
        open={Boolean(pendingAction)}
        onOpenChange={(v) => !v && setPendingAction(null)}
        clientId={clientId}
        action={pendingAction}
        onSubmit={handleExecute}
      />
    </section>
  );
}
