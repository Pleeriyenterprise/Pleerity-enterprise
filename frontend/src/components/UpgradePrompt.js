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

// Helper function to get human-readable plan name
function getRequiredPlanName(planCode) {
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

export default UpgradePrompt;
