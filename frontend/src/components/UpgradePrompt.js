import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { Layers, ArrowUpRight, Sparkles, CheckCircle } from 'lucide-react';
import { Button } from './ui/button';
import { buildSafeQueryPath } from '../utils/clientPortalNavigation';
import { operationalLabelForToken } from '../utils/presentationLanguage';
import { GovernedUpgradeDiscoverCard } from './client/PlanGatingDiscoverability';
import { cn } from '../lib/utils';

/**
 * Upgrade / tier discoverability — presentation only. Backend gating unchanged.
 *
 * Principles: calm operational framing, scale & automation language, no punitive “locked” tone.
 */
const UpgradePrompt = ({
  featureName,
  featureDescription,
  requiredPlan,
  requiredPlanName,
  currentPlan = null,
  variant = 'card',
  onUpgrade = null,
  onDismiss = null,
  className = '',
  contextHint = null,
  dataTestId = null,
}) => {
  const navigate = useNavigate();

  const handleUpgradeClick = () => {
    if (onUpgrade) {
      onUpgrade();
    }
    navigate(buildSafeQueryPath('/settings/billing', { upgrade_to: requiredPlan }));
  };

  const planDiscoverabilityLine = `Included with the ${requiredPlanName} tier for portfolio-scale workflows and optional automation.`;
  const planDiscoverabilityShort = `Portfolio-scale plans include this under the ${requiredPlanName} tier — see Billing for current options.`;

  if (variant === 'inline') {
    return (
      <div
        className={cn(
          'flex flex-col gap-1 rounded-lg border border-slate-200 bg-slate-50/90 px-3 py-2 text-sm text-slate-700',
          className,
        )}
        data-testid={dataTestId || 'upgrade-prompt-inline'}
      >
        <div className="flex items-start gap-2">
          <Layers className="mt-0.5 h-4 w-4 flex-shrink-0 text-midnight-blue/55" aria-hidden />
          <div className="min-w-0">
            <span className="block font-medium leading-snug text-midnight-blue">{planDiscoverabilityShort}</span>
            <span className="mt-1 block">
              <button
                type="button"
                onClick={handleUpgradeClick}
                className="font-semibold text-electric-teal underline decoration-electric-teal/40 underline-offset-2 hover:text-electric-teal/90"
              >
                View plans in Billing
              </button>
            </span>
          </div>
        </div>
        {contextHint ? (
          <p className="pl-6 text-xs leading-snug text-slate-600" data-testid="upgrade-context-hint">
            {contextHint}
          </p>
        ) : null}
      </div>
    );
  }

  if (variant === 'modal') {
    return (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        data-testid={dataTestId || 'upgrade-prompt-modal'}
      >
        <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full border border-slate-100 bg-slate-50">
            <Layers className="h-7 w-7 text-midnight-blue/70" aria-hidden />
          </div>

          <h2 className="mb-2 text-center text-xl font-bold text-gray-900">{featureName}</h2>

          <p className="mb-2 text-center font-medium text-gray-800">{planDiscoverabilityLine}</p>

          {currentPlan ? (
            <p className="mb-2 text-center text-xs text-gray-500">
              Billing lists options for your <span className="font-medium text-gray-700">{currentPlan}</span> workspace.
            </p>
          ) : null}

          <p className="mb-4 text-center text-sm text-gray-600">
            Your current plan stays focused on core operations; this capability is available when you add portfolio-scale
            tooling.
          </p>

          {featureDescription ? <p className="mb-4 text-center text-sm text-gray-500">{featureDescription}</p> : null}

          {contextHint ? (
            <p className="mb-4 text-center text-xs text-gray-500" data-testid="upgrade-context-hint">
              {contextHint}
            </p>
          ) : null}

          <div className="mb-6 rounded-xl border border-electric-teal/20 bg-gradient-to-r from-electric-teal/10 to-electric-teal/5 p-4">
            <div className="mb-2 flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-electric-teal" aria-hidden />
              <span className="font-semibold text-gray-900">{requiredPlanName}</span>
            </div>
            <p className="text-sm text-gray-600">
              Adds optional automation, reporting, and collaboration suited to larger portfolios — without changing how
              compliance authority works in your account.
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row">
            {onDismiss ? (
              <>
                <Button type="button" className="flex-1 bg-electric-teal hover:bg-electric-teal/90" onClick={onDismiss}>
                  Continue
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="flex-1 border-slate-200 text-midnight-blue hover:bg-slate-50"
                  onClick={handleUpgradeClick}
                >
                  View plans in Billing
                  <ArrowUpRight className="ml-2 h-4 w-4" />
                </Button>
              </>
            ) : (
              <Button
                type="button"
                className="w-full bg-electric-teal hover:bg-electric-teal/90"
                onClick={handleUpgradeClick}
              >
                View plans in Billing
                <ArrowUpRight className="ml-2 h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <GovernedUpgradeDiscoverCard
      title={featureName}
      onPrimaryCta={handleUpgradeClick}
      primaryCtaLabel="View plans in Billing"
      className={className}
      data-testid={dataTestId || 'upgrade-prompt-card'}
    >
      <p className="text-sm leading-relaxed text-slate-600">{planDiscoverabilityLine}</p>
      {featureDescription ? <p className="text-sm leading-relaxed text-slate-600">{featureDescription}</p> : null}
      {contextHint ? (
        <p className="text-xs leading-relaxed text-slate-500" data-testid="upgrade-context-hint">
          {contextHint}
        </p>
      ) : null}
    </GovernedUpgradeDiscoverCard>
  );
};

/**
 * Feature Gate — wraps content; shows discoverability when not entitled (no entitlement change).
 */
export const FeatureGate = ({ feature, entitlements, children, fallback = null }) => {
  const { usageContext } = useEntitlements();
  const contextHint = useMemo(() => formatUpgradeUsageContext(usageContext), [usageContext]);

  if (!entitlements || !entitlements.features) {
    return null;
  }

  const featureData = entitlements.features[feature];

  if (featureData?.enabled) {
    return children;
  }

  if (fallback) {
    return fallback;
  }

  return (
    <UpgradePrompt
      featureName={featureData?.name || feature}
      featureDescription={featureData?.description}
      requiredPlan={featureData?.minimum_plan || 'PLAN_2_PORTFOLIO'}
      requiredPlanName={getRequiredPlanName(featureData?.minimum_plan)}
      currentPlan={entitlements.plan_name}
      variant="card"
      contextHint={contextHint}
    />
  );
};

/**
 * Property limit — authoritative limits preserved; calmer presentation (not a red “error” surface).
 */
export const PropertyLimitPrompt = ({
  currentLimit,
  requestedCount,
  currentPlan,
  upgradePlan,
  upgradePlanName,
  upgradeLimit,
  onUpgrade = null,
  switchPlanOnly = false,
  className = '',
}) => {
  const navigate = useNavigate();
  const { usageContext } = useEntitlements();
  const existingOnAccount =
    typeof usageContext?.property_count === 'number' ? usageContext.property_count : null;

  const handleUpgradeClick = () => {
    if (onUpgrade) {
      onUpgrade();
    }
    if (switchPlanOnly) {
      return;
    }
    navigate(buildSafeQueryPath('/settings/billing', { upgrade_to: upgradePlan }));
  };

  return (
    <div
      className={cn(
        'rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-6 shadow-sm',
        className,
      )}
      data-testid="property-limit-prompt"
    >
      <div className="flex items-start gap-4">
        <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl border border-slate-100 bg-white">
          <Layers className="h-6 w-6 text-midnight-blue/70" aria-hidden />
        </div>

        <div className="min-w-0 flex-1">
          <h3 className="mb-1 font-semibold text-midnight-blue">Portfolio capacity for your plan</h3>

          <p className="mb-3 text-sm text-slate-700">
            <span className="font-medium text-midnight-blue">{currentPlan}</span> supports up to{' '}
            <strong>{currentLimit}</strong> propert{currentLimit === 1 ? 'y' : 'ies'}. This action involves{' '}
            <strong>{requestedCount}</strong> propert{requestedCount === 1 ? 'y' : 'ies'}.
          </p>

          {existingOnAccount != null && existingOnAccount > 0 ? (
            <p
              className="mb-3 rounded-r border-l-2 border-slate-200 bg-slate-100/60 py-2 pl-3 text-sm text-slate-800"
              data-testid="property-limit-existing-portfolio-hint"
            >
              Your account already has <strong>{existingOnAccount}</strong> propert
              {existingOnAccount === 1 ? 'y' : 'ies'} on file. Limits apply to your whole portfolio, including properties
              added in this flow.
            </p>
          ) : null}

          {upgradePlanName ? (
            <div className="mb-4 rounded-lg border border-slate-100 bg-white/80 p-3">
              <div className="flex items-center gap-2 text-sm text-slate-700">
                <CheckCircle className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
                <span>
                  <strong className="text-midnight-blue">{upgradePlanName}</strong> supports up to{' '}
                  <strong>{upgradeLimit}</strong> propert{upgradeLimit === 1 ? 'y' : 'ies'} when you need more capacity.
                </span>
              </div>
            </div>
          ) : null}

          <Button
            className="bg-electric-teal text-white hover:bg-electric-teal/90"
            onClick={handleUpgradeClick}
            type="button"
          >
            Compare plans in Billing
            <ArrowUpRight className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};

export function getRequiredPlanName(planCode) {
  const planNames = {
    PLAN_1_SOLO: 'Solo Landlord',
    PLAN_2_PORTFOLIO: 'Portfolio',
    PLAN_3_PRO: 'Professional',
    PLAN_1: 'Solo Landlord',
    PLAN_2_5: 'Portfolio',
    PLAN_6_15: 'Professional',
  };
  return planNames[planCode] || 'Portfolio';
}

const FEATURE_MIN_PLAN = {
  document_upload_bulk_zip: 'PLAN_2_PORTFOLIO',
  zip_upload: 'PLAN_2_PORTFOLIO',
  reports_pdf: 'PLAN_2_PORTFOLIO',
  scheduled_reports: 'PLAN_2_PORTFOLIO',
  ai_extraction_advanced: 'PLAN_3_PRO',
  extraction_review_ui: 'PLAN_3_PRO',
  ai_review_interface: 'PLAN_3_PRO',
  reports_csv: 'PLAN_2_PORTFOLIO',
  sms_reminders: 'PLAN_2_PORTFOLIO',
  tenant_portal: 'PLAN_3_PRO',
  tenant_portal_access: 'PLAN_3_PRO',
  webhooks: 'PLAN_3_PRO',
  white_label_reports: 'PLAN_3_PRO',
  audit_log_export: 'PLAN_3_PRO',
  audit_exports: 'PLAN_3_PRO',
  white_label: 'PLAN_3_PRO',
  maintenance_workflows: 'PLAN_2_PORTFOLIO',
  contractor_network: 'PLAN_3_PRO',
  predictive_maintenance: 'PLAN_2_PORTFOLIO',
  invoicing: 'PLAN_3_PRO',
  rent_operations: 'PLAN_2_PORTFOLIO',
};

const FEATURE_DISPLAY = {
  zip_upload: { name: 'ZIP bulk upload', description: 'Upload documents as a single ZIP archive.' },
  document_upload_bulk_zip: { name: 'ZIP bulk upload', description: 'Upload documents as a single ZIP archive.' },
  reports_pdf: { name: 'PDF reports', description: 'Generate and download PDF compliance reports.' },
  reports_csv: { name: 'CSV export', description: 'Export report data as CSV.' },
  scheduled_reports: { name: 'Scheduled reports', description: 'Schedule automated report delivery.' },
  ai_extraction_advanced: {
    name: 'Advanced AI extraction',
    description: 'Confidence scoring and field validation for extracted data.',
  },
  extraction_review_ui: { name: 'Extraction review', description: 'Review and approve AI-extracted data before applying.' },
  ai_review_interface: { name: 'AI review interface', description: 'Review and apply AI-extracted data (Professional).' },
  sms_reminders: { name: 'SMS reminders', description: 'Receive compliance reminders via SMS.' },
  tenant_portal: { name: 'Tenant portal', description: 'Invite tenants and manage tenant access.' },
  tenant_portal_access: { name: 'Tenant portal', description: 'Invite tenants and manage tenant access.' },
  webhooks: { name: 'Webhooks', description: 'Configure webhooks for integrations.' },
  white_label_reports: { name: 'White-label branding', description: 'Customise report branding.' },
  white_label: { name: 'White-label branding', description: 'Customise report branding.' },
  audit_log_export: { name: 'Audit export', description: 'Export audit logs.' },
  audit_exports: { name: 'Audit export', description: 'Export audit logs.' },
  maintenance_workflows: { name: 'Maintenance & jobs', description: 'Create and manage jobs and maintenance issues per property.' },
  contractor_network: {
    name: 'Contractor network',
    description: 'Assign contractors to jobs, manage your directory, and coordinate work from the portal (Professional plan).',
  },
  predictive_maintenance: {
    name: 'Risk signals & assets',
    description: 'Predictive risk signals from your property data, plus asset tracking.',
  },
  invoicing: {
    name: 'Invoice & job approvals',
    description:
      'Review and approve invoices and cost submissions linked to jobs. Compare amounts to benchmarks and maintain an audit trail.',
  },
  rent_operations: {
    name: 'Rent Operations',
    description:
      'Track expected rent, record payments, monitor arrears, and log property expenses. Operational visibility only — not accounting software.',
  },
};

export function getFeatureDisplayInfo(featureKey, entitlements = null) {
  const planCode =
    entitlements?.features?.[featureKey]?.minimum_plan ?? FEATURE_MIN_PLAN[featureKey] ?? 'PLAN_2_PORTFOLIO';
  const display = FEATURE_DISPLAY[featureKey] || {
    name: operationalLabelForToken(featureKey, { emptyLabel: 'Feature' }),
    description: '',
  };
  return {
    featureName: display.name,
    featureDescription: display.description,
    requiredPlan: planCode,
    requiredPlanName: getRequiredPlanName(planCode),
  };
}

/**
 * One-line portfolio hint for upgrade surfaces (from GET /client/entitlements/context).
 */
export function formatUpgradeUsageContext(usageContext) {
  if (!usageContext || typeof usageContext.property_count !== 'number') return null;
  const n = usageContext.property_count;
  const cap = usageContext.max_properties;
  const at = Boolean(usageContext.at_property_limit);
  if (typeof cap === 'number' && cap > 0) {
    if (at) {
      return `You're at your plan's property limit (${n} of ${cap}). Higher tiers can add capacity and optional automation — Billing lists current limits.`;
    }
    return `You have ${n} propert${n === 1 ? 'y' : 'ies'} on file; your plan allows up to ${cap}.`;
  }
  return `You have ${n} propert${n === 1 ? 'y' : 'ies'} on file.`;
}

/**
 * Plan-gated route or 403 surface — presentation only.
 */
export function UpgradeRequired({
  feature,
  plan = null,
  variant = 'card',
  showBackToDashboard = true,
  className = '',
  upgradeDetail = null,
}) {
  const navigate = useNavigate();
  const { usageContext, entitlements } = useEntitlements();
  const contextHint = useMemo(() => formatUpgradeUsageContext(usageContext), [usageContext]);
  const featureKey = upgradeDetail?.feature ?? upgradeDetail?.feature_key ?? feature;
  const planOverride = plan ?? upgradeDetail?.upgrade_to ?? null;
  const info = getFeatureDisplayInfo(featureKey, entitlements);
  const requiredPlan = planOverride ?? info.requiredPlan;
  const requiredPlanName = getRequiredPlanName(requiredPlan);

  return (
    <div className={showBackToDashboard ? 'space-y-4' : ''}>
      <UpgradePrompt
        featureName={info.featureName}
        featureDescription={info.featureDescription}
        requiredPlan={requiredPlan}
        requiredPlanName={requiredPlanName}
        variant={variant}
        className={className}
        contextHint={contextHint}
      />
      {showBackToDashboard ? (
        <div className="flex justify-center">
          <Button
            variant="outline"
            onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/dashboard'))}
            data-testid="upgrade-required-back"
            type="button"
          >
            Back to Dashboard
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export default UpgradePrompt;
