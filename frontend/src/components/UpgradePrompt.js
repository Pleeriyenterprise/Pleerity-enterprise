import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, ArrowUpRight, Sparkles, CheckCircle } from 'lucide-react';
import { Button } from './ui/button';

/**
 * Upgrade Prompt Component - Displayed when user attempts to access a gated feature.
 * 
 * NON-NEGOTIABLE RULES:
 * 1. No silent failures - always show this prompt
 * 2. Clearly explain what the feature does
 * 3. Show which plan unlocks it
 * 4. Link to upgrade page
 * 5. No background side effects
 * 
 * Props:
 * - featureName: Human-readable feature name
 * - featureDescription: What the feature does
 * - requiredPlan: Plan code that unlocks this feature
 * - requiredPlanName: Human-readable plan name
 * - currentPlan: Current plan name (optional)
 * - variant: 'inline' | 'modal' | 'card' (default: 'card')
 * - onUpgrade: Optional callback when upgrade button clicked
 * - onDismiss: Optional callback when dismissed (only for modal variant)
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
}) => {
  const navigate = useNavigate();

  const handleUpgradeClick = () => {
    if (onUpgrade) {
      onUpgrade();
    }
    navigate(`/app/billing?upgrade_to=${requiredPlan}`);
  };

  // Inline variant - minimal, fits within existing UI
  if (variant === 'inline') {
    return (
      <div 
        className={`flex items-center gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 ${className}`}
        data-testid="upgrade-prompt-inline"
      >
        <Lock className="w-4 h-4 flex-shrink-0" />
        <span>
          <strong>{featureName}</strong> requires {requiredPlanName} plan.{' '}
          <button
            onClick={handleUpgradeClick}
            className="text-amber-800 underline hover:text-amber-900 font-medium"
          >
            Upgrade now
          </button>
        </span>
      </div>
    );
  }

  // Modal variant - full-screen overlay
  if (variant === 'modal') {
    return (
      <div 
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
        data-testid="upgrade-prompt-modal"
      >
        <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl">
          <div className="flex items-center justify-center w-16 h-16 bg-gradient-to-br from-amber-100 to-amber-200 rounded-full mx-auto mb-4">
            <Lock className="w-8 h-8 text-amber-600" />
          </div>
          
          <h2 className="text-xl font-bold text-center text-gray-900 mb-2">
            Upgrade Required
          </h2>
          
          <p className="text-center text-gray-600 mb-4">
            <strong className="text-gray-900">{featureName}</strong> is not available on your current plan.
          </p>
          
          {featureDescription && (
            <p className="text-center text-sm text-gray-500 mb-6">
              {featureDescription}
            </p>
          )}
          
          <div className="bg-gradient-to-r from-electric-teal/10 to-electric-teal/5 border border-electric-teal/20 rounded-xl p-4 mb-6">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-5 h-5 text-electric-teal" />
              <span className="font-semibold text-gray-900">{requiredPlanName} Plan</span>
            </div>
            <p className="text-sm text-gray-600">
              Unlock {featureName} and more advanced features by upgrading to {requiredPlanName}.
            </p>
          </div>
          
          <div className="flex gap-3">
            {onDismiss && (
              <Button
                variant="outline"
                className="flex-1"
                onClick={onDismiss}
              >
                Maybe Later
              </Button>
            )}
            <Button
              className="flex-1 bg-electric-teal hover:bg-electric-teal/90"
              onClick={handleUpgradeClick}
            >
              View Upgrade Options
              <ArrowUpRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Card variant (default) - standalone card for embedding
  return (
    <div 
      className={`bg-gradient-to-br from-gray-50 to-gray-100 border-2 border-amber-200 rounded-2xl p-6 ${className}`}
      data-testid="upgrade-prompt-card"
    >
      <div className="flex items-start gap-4">
        <div className="flex items-center justify-center w-12 h-12 bg-amber-100 rounded-xl flex-shrink-0">
          <Lock className="w-6 h-6 text-amber-600" />
        </div>
        
        <div className="flex-1">
          <h3 className="font-semibold text-gray-900 mb-1">
            {featureName}
          </h3>
          
          {featureDescription && (
            <p className="text-sm text-gray-600 mb-3">
              {featureDescription}
            </p>
          )}
          
          <div className="flex items-center gap-2 text-sm text-amber-700 mb-4">
            <span className="px-2 py-0.5 bg-amber-100 rounded font-medium">
              {requiredPlanName}
            </span>
            <span>plan required</span>
          </div>
          
          <Button
            size="sm"
            className="bg-electric-teal hover:bg-electric-teal/90"
            onClick={handleUpgradeClick}
          >
            Upgrade to Unlock
            <ArrowUpRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </div>
    </div>
  );
};

/**
 * Feature Gate Component - Wraps content and shows upgrade prompt if not entitled.
 * 
 * Props:
 * - feature: Feature key to check
 * - entitlements: Entitlements object from API
 * - children: Content to show if entitled
 * - fallback: Optional custom fallback (default: UpgradePrompt)
 */
export const FeatureGate = ({
  feature,
  entitlements,
  children,
  fallback = null,
}) => {
  if (!entitlements || !entitlements.features) {
    // Still loading or no entitlements - show nothing or loading state
    return null;
  }

  const featureData = entitlements.features[feature];
  
  if (featureData?.enabled) {
    return children;
  }

  // Feature not enabled - show upgrade prompt or custom fallback
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
    />
  );
};

/**
 * Property Limit Prompt - Specific upgrade prompt for property limits.
 */
export const PropertyLimitPrompt = ({
  currentLimit,
  requestedCount,
  currentPlan,
  upgradePlan,
  upgradePlanName,
  upgradeLimit,
  onUpgrade = null,
  className = '',
}) => {
  const navigate = useNavigate();

  const handleUpgradeClick = () => {
    if (onUpgrade) {
      onUpgrade();
    }
    navigate(`/app/billing?upgrade_to=${upgradePlan}`);
  };

  return (
    <div 
      className={`bg-red-50 border-2 border-red-200 rounded-2xl p-6 ${className}`}
      data-testid="property-limit-prompt"
    >
      <div className="flex items-start gap-4">
        <div className="flex items-center justify-center w-12 h-12 bg-red-100 rounded-xl flex-shrink-0">
          <Lock className="w-6 h-6 text-red-600" />
        </div>
        
        <div className="flex-1">
          <h3 className="font-semibold text-red-900 mb-1">
            Property Limit Reached
          </h3>
          
          <p className="text-sm text-red-700 mb-3">
            Your current plan ({currentPlan}) allows a maximum of <strong>{currentLimit}</strong> properties.
            You're trying to add {requestedCount} properties.
          </p>
          
          {upgradePlanName && (
            <div className="bg-white/50 rounded-lg p-3 mb-4">
              <div className="flex items-center gap-2 text-sm">
                <CheckCircle className="w-4 h-4 text-green-600" />
                <span>
                  <strong>{upgradePlanName}</strong> allows up to <strong>{upgradeLimit}</strong> properties
                </span>
              </div>
            </div>
          )}
          
          <Button
            className="bg-electric-teal hover:bg-electric-teal/90"
            onClick={handleUpgradeClick}
          >
            Upgrade to {upgradePlanName || 'Higher Plan'}
            <ArrowUpRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </div>
    </div>
  );
};

// Helper function to get human-readable plan name (exported for UpgradeRequired)
export function getRequiredPlanName(planCode) {
  const planNames = {
    'PLAN_1_SOLO': 'Solo Landlord',
    'PLAN_2_PORTFOLIO': 'Portfolio',
    'PLAN_3_PRO': 'Professional',
    // Legacy
    'PLAN_1': 'Solo Landlord',
    'PLAN_2_5': 'Portfolio',
    'PLAN_6_15': 'Professional',
  };
  return planNames[planCode] || 'Portfolio';
}

// Feature key -> minimum plan (matches backend plan_registry)
const FEATURE_MIN_PLAN = {
  document_upload_bulk_zip: 'PLAN_2_PORTFOLIO',
  zip_upload: 'PLAN_2_PORTFOLIO',
  reports_pdf: 'PLAN_2_PORTFOLIO',
  scheduled_reports: 'PLAN_2_PORTFOLIO',
  ai_extraction_advanced: 'PLAN_3_PRO',
  extraction_review_ui: 'PLAN_3_PRO',
  ai_review_interface: 'PLAN_3_PRO',
  reports_csv: 'PLAN_3_PRO',
  sms_reminders: 'PLAN_3_PRO',
  tenant_portal: 'PLAN_3_PRO',
  tenant_portal_access: 'PLAN_3_PRO',
  webhooks: 'PLAN_3_PRO',
  white_label_reports: 'PLAN_3_PRO',
  audit_log_export: 'PLAN_3_PRO',
  audit_exports: 'PLAN_3_PRO',
  white_label: 'PLAN_3_PRO',
};

const FEATURE_DISPLAY = {
  zip_upload: { name: 'ZIP bulk upload', description: 'Upload documents as a single ZIP archive.' },
  document_upload_bulk_zip: { name: 'ZIP bulk upload', description: 'Upload documents as a single ZIP archive.' },
  reports_pdf: { name: 'PDF reports', description: 'Generate and download PDF compliance reports.' },
  reports_csv: { name: 'CSV export', description: 'Export report data as CSV.' },
  scheduled_reports: { name: 'Scheduled reports', description: 'Schedule automated report delivery.' },
  ai_extraction_advanced: { name: 'Advanced AI extraction', description: 'Confidence scoring and field validation for extracted data.' },
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
};

export function getFeatureDisplayInfo(featureKey, entitlements = null) {
  const planCode = entitlements?.features?.[featureKey]?.minimum_plan ?? FEATURE_MIN_PLAN[featureKey] ?? 'PLAN_2_PORTFOLIO';
  const display = FEATURE_DISPLAY[featureKey] || { name: featureKey.replace(/_/g, ' '), description: '' };
  return {
    featureName: display.name,
    featureDescription: display.description,
    requiredPlan: planCode,
    requiredPlanName: getRequiredPlanName(planCode),
  };
}

/**
 * Reusable "Upgrade required" state for plan-gated features.
 * Use when a 403 with upgrade_required is returned or when user hits a locked route.
 * Props: feature (key), plan (optional override), variant, showBackToDashboard
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
  const featureKey = upgradeDetail?.feature ?? upgradeDetail?.feature_key ?? feature;
  const planOverride = plan ?? upgradeDetail?.upgrade_to ?? null;
  const info = getFeatureDisplayInfo(featureKey, null);
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
      />
      {showBackToDashboard && (
        <div className="flex justify-center">
          <Button
            variant="outline"
            onClick={() => navigate('/app/dashboard')}
            data-testid="upgrade-required-back"
          >
            Back to Dashboard
          </Button>
        </div>
      )}
    </div>
  );
}

export default UpgradePrompt;
