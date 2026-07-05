import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
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
import { getFeatureDisplayInfo } from '../UpgradePrompt';

/** Calm, operational framing — discoverability lives in Billing, not punitive “locked” language. */
export const PLAN_RESTRICTED_TITLE = 'Designed for portfolio-scale job workflows';

const COMPLIANCE_BODY =
  'Starting inspection jobs from this control uses portfolio automation. You can still upload evidence, manage requirements, and complete remediation on your current plan.';

const MAINTENANCE_BODY =
  'Creating platform jobs from this entry point uses portfolio automation. You can still log issues and track property activity without changing plans.';

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
  /* No session toast: modal carries discoverability; avoids stacking with urgent compliance toasts. */
  return true;
}

/**
 * Plan-gated job/workflow creation: compliance vs maintenance copy and CTAs.
 * Primary actions = operational (upload / log issue); Billing = secondary discoverability.
 * @param {{ kind: 'compliance_job'|'maintenance_job', propertyId?: string|null, requirementId?: string|null, upgradeDetail?: object|null, billingFeatureFallbackKey?: string|null } | null} gate
 */
export function PlanRestrictedJobModal({ gate, onDismiss }) {
  const navigate = useNavigate();
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
    return getFeatureDisplayInfo(fk).requiredPlan;
  }, [upgradeDetail, gate?.billingFeatureFallbackKey, kind]);

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
          <DialogDescription className="pt-1 text-left text-muted-foreground">{body}</DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex-col gap-2 sm:flex-col sm:space-x-0">
          {kind === 'compliance_job' ? (
            <>
              <Button type="button" className="w-full bg-electric-teal hover:bg-electric-teal/90" onClick={goDocuments}>
                Upload document instead
              </Button>
              <Button type="button" variant="outline" className="w-full" onClick={goRequirements}>
                View requirements
              </Button>
              <Button type="button" variant="ghost" className="w-full text-midnight-blue hover:bg-slate-50" onClick={goBilling}>
                View plans in Billing
              </Button>
            </>
          ) : (
            <>
              <Button type="button" className="w-full bg-electric-teal hover:bg-electric-teal/90" onClick={goLogIssue}>
                Log issue instead
              </Button>
              <Button type="button" variant="outline" className="w-full" onClick={goPropertyActivity}>
                View issues & property activity
              </Button>
              <Button type="button" variant="ghost" className="w-full text-midnight-blue hover:bg-slate-50" onClick={goBilling}>
                View plans in Billing
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
