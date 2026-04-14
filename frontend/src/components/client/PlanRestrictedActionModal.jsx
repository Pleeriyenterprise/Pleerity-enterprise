import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import {
  buildSafeQueryPath,
  resolveDocumentsPath,
  normalizeRouteId,
  resolvePropertyPath,
} from '../../utils/clientPortalNavigation';
import { useEntitlements } from '../../contexts/EntitlementsContext';
import { getFeatureDisplayInfo } from '../UpgradePrompt';

export const PLAN_RESTRICTED_TITLE = "This action isn't available on your current plan";

const COMPLIANCE_BODY =
  'Starting compliance inspection work from a requirement requires a higher plan. You can still upload documents or manage requirements.';

const MAINTENANCE_BODY =
  'Starting maintenance jobs from the platform requires a higher plan. You can still log issues or track property activity.';

const TOAST_PREFIX = 'cvp_plan_gate_toast_';

/**
 * One short toast per browser tab session per `toastSessionKey` (modal still shows every time).
 */
export function notifyPlanRestrictedActionOnce(toastSessionKey, message) {
  const key = `${TOAST_PREFIX}${toastSessionKey}`;
  try {
    if (typeof window !== 'undefined' && sessionStorage.getItem(key)) return;
    if (typeof window !== 'undefined') sessionStorage.setItem(key, '1');
  } catch {
    /* ignore */
  }
  toast.message(message);
}

/**
 * @param {import('axios').AxiosError} error
 * @param {React.Dispatch<React.SetStateAction<object|null>>} setGate
 * @param {{ propertyId?: string|null, requirementId?: string|null }} [context]
 * @returns {boolean} true if error was consumed (show modal, skip generic toast)
 */
export function openPlanRestrictedJobGate(error, setGate, context = {}) {
  const kind = error?.planRestrictedActionKind;
  if (kind !== 'compliance_job' && kind !== 'maintenance_job') return false;
  setGate({
    kind,
    propertyId: context.propertyId ?? null,
    requirementId: context.requirementId ?? null,
    upgradeDetail: error.upgradeDetail,
    billingFeatureFallbackKey: error.planRestrictedBillingFeatureKey || null,
  });
  notifyPlanRestrictedActionOnce(
    kind === 'compliance_job' ? 'compliance_job' : 'maintenance_job',
    kind === 'compliance_job'
      ? 'Upgrade required to start compliance inspection jobs'
      : 'Upgrade required to start maintenance jobs',
  );
  return true;
}

/**
 * Plan-gated job/workflow creation: compliance vs maintenance copy and CTAs.
 * @param {{ kind: 'compliance_job'|'maintenance_job', propertyId?: string|null, requirementId?: string|null, upgradeDetail?: object|null, billingFeatureFallbackKey?: string|null } | null} gate
 */
export function PlanRestrictedJobModal({ gate, onDismiss }) {
  const navigate = useNavigate();
  const { entitlements } = useEntitlements();
  const open = Boolean(gate);
  const kind = gate?.kind === 'maintenance_job' ? 'maintenance_job' : 'compliance_job';
  const upgradeDetail = gate?.upgradeDetail ?? null;

  const upgradeToPlan = useMemo(() => {
    const fromApi = upgradeDetail?.upgrade_to ?? upgradeDetail?.minimum_plan;
    if (fromApi) return fromApi;
    const fk =
      gate?.billingFeatureFallbackKey ||
      upgradeDetail?.feature ||
      upgradeDetail?.feature_key ||
      (kind === 'compliance_job' ? 'maintenance_workflows' : 'maintenance_workflows');
    return getFeatureDisplayInfo(fk, entitlements).requiredPlan;
  }, [upgradeDetail, entitlements, gate?.billingFeatureFallbackKey, kind]);

  const pid = normalizeRouteId(gate?.propertyId);
  const rid = normalizeRouteId(gate?.requirementId);

  const close = () => {
    onDismiss?.();
  };

  const goBilling = () => {
    navigate(buildSafeQueryPath('/settings/billing', { upgrade_to: upgradeToPlan }));
    close();
  };

  const goDocuments = () => {
    const extra = { focus: 'upload' };
    if (rid) extra.requirement_id = rid;
    navigate(pid ? resolveDocumentsPath(pid, extra) : buildSafeQueryPath('/documents', extra));
    close();
  };

  const goRequirements = () => {
    const q = {};
    if (pid) q.property_id = pid;
    if (rid) q.highlight = rid;
    navigate(buildSafeQueryPath('/requirements', q));
    close();
  };

  const goLogIssue = () => {
    const q = { open_log_issue: '1' };
    if (pid) q.property_id = pid;
    navigate(buildSafeQueryPath('/operations/issues', q));
    close();
  };

  const goPropertyActivity = () => {
    navigate(pid ? resolvePropertyPath(pid) : buildSafeQueryPath('/operations/issues'));
    close();
  };

  const body = kind === 'maintenance_job' ? MAINTENANCE_BODY : COMPLIANCE_BODY;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && close()}>
      <DialogContent className="sm:max-w-md" data-testid="plan-restricted-action-modal">
        <DialogHeader>
          <DialogTitle>{PLAN_RESTRICTED_TITLE}</DialogTitle>
          <DialogDescription className="text-left text-muted-foreground pt-1">{body}</DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex-col gap-2 sm:flex-col sm:space-x-0">
          <Button type="button" className="w-full bg-electric-teal hover:bg-electric-teal/90" onClick={goBilling}>
            Upgrade plan
          </Button>
          {kind === 'compliance_job' ? (
            <>
              <Button type="button" variant="outline" className="w-full" onClick={goDocuments}>
                Upload document instead
              </Button>
              <button
                type="button"
                onClick={goRequirements}
                className="text-sm text-electric-teal hover:underline font-medium pt-1 text-left"
              >
                View requirements
              </button>
            </>
          ) : (
            <>
              <Button type="button" variant="outline" className="w-full" onClick={goLogIssue}>
                Log issue instead
              </Button>
              <button
                type="button"
                onClick={goPropertyActivity}
                className="text-sm text-electric-teal hover:underline font-medium pt-1 text-left"
              >
                View issues & property activity
              </button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
