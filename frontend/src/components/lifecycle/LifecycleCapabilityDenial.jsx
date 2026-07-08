import React from 'react';
import { Link } from 'react-router-dom';
import { Lock } from 'lucide-react';
import { usePortalMode } from '../../contexts/LifecycleRuntimeContext';
import { lifecycleCapabilityDenialMessage } from '../../utils/lifecycleRecoveryCopy';
import { Button } from '../ui/button';

/**
 * In-page denial when lifecycle restricts access (suspended, billing recovery, etc.).
 * Uses Runtime Contract customer_experience CTAs — never raw CAP_* identifiers.
 */
export function LifecycleCapabilityDenial({ testId = 'lifecycle-capability-denial', showBackToDashboard = true }) {
  const { portalMode, customerExperience } = usePortalMode();
  const message = lifecycleCapabilityDenialMessage(portalMode);
  const primaryCta = customerExperience?.primary_cta;
  const secondaryCta = customerExperience?.secondary_cta;
  const stateLabel = customerExperience?.current_state_label || portalMode?.replace(/_/g, ' ');

  return (
    <div className="min-h-[40vh] flex items-center justify-center p-6 bg-gray-50" data-testid={testId}>
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm text-center space-y-4">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-slate-200 bg-slate-50">
          <Lock className="h-6 w-6 text-midnight-blue/70" aria-hidden />
        </div>
        {stateLabel ? (
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{stateLabel}</p>
        ) : null}
        <p className="text-sm leading-relaxed text-gray-700">{message}</p>
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
          {primaryCta?.label && primaryCta?.route ? (
            <Button asChild className="bg-midnight-blue hover:bg-midnight-blue/90">
              <Link to={primaryCta.route} data-testid={`${testId}-primary-cta`}>
                {primaryCta.label}
              </Link>
            </Button>
          ) : null}
          {secondaryCta?.label && secondaryCta?.route ? (
            <Button asChild variant="outline">
              <Link to={secondaryCta.route} data-testid={`${testId}-secondary-cta`}>
                {secondaryCta.label}
              </Link>
            </Button>
          ) : null}
        </div>
        {showBackToDashboard ? (
          <div className="pt-1">
            <Button
              variant="outline"
              type="button"
              onClick={() => (window.history.length > 2 ? window.history.back() : (window.location.href = '/settings/billing'))}
              data-testid={`${testId}-back`}
            >
              Back to Billing
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
