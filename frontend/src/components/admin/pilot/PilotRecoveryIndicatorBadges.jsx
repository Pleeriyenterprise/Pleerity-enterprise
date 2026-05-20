import React from 'react';
import { indicatorsToBadges, recoveryBadgeLabel, redemptionStatusBadgeClass } from '../../../utils/pilotRedemptionAdmin';

/**
 * Operational warning badges from backend indicators (no client-side eligibility logic).
 */
export default function PilotRecoveryIndicatorBadges({ indicators, className = '' }) {
  const badges = indicatorsToBadges(indicators);
  if (!badges.length && !indicators?.stranded_onboarding) {
    return null;
  }

  return (
    <div className={`flex flex-wrap gap-1.5 ${className}`} data-testid="pilot-recovery-indicator-badges">
      {indicators?.stranded_onboarding && !badges.includes('stranded_onboarding') && (
        <span
          className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded ${redemptionStatusBadgeClass('payment_failed')}`}
        >
          Stranded onboarding
        </span>
      )}
      {badges.map((key) => (
        <span
          key={key}
          className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded ${
            key === 'override_active' || key === 'first_time_bypass'
              ? 'bg-indigo-100 text-indigo-800'
              : key === 'payment_failed' || key === 'provisioning_failed'
                ? 'bg-red-100 text-red-800'
                : 'bg-amber-100 text-amber-900'
          }`}
          data-testid={`recovery-badge-${key}`}
        >
          {recoveryBadgeLabel(key)}
        </span>
      ))}
    </div>
  );
}
