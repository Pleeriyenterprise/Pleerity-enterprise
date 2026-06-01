import { useCallback, useEffect, useState } from 'react';
import { adminAPI } from '../api/client';
import { apiErrorMessage } from '../utils/apiErrorMessage';

/**
 * Loads promo recovery context for any client (not gated on active pilot lifecycle).
 */
export function usePilotAccountRecovery(clientId, { enabled = true } = {}) {
  const [bundle, setBundle] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!clientId || !enabled) return;
    setLoading(true);
    setError(null);
    try {
      const [promoRes, assessmentRes] = await Promise.all([
        adminAPI.getPilotAccountRedemptions(clientId, { limit: 100 }),
        adminAPI.getOnboardingRecoveryAssessment(clientId).catch(() => ({ data: null })),
      ]);
      setBundle({
        ...(promoRes.data || {}),
        onboarding_recovery_assessment: assessmentRes.data || null,
      });
    } catch (e) {
      setError(apiErrorMessage(e, 'Failed to load promo recovery data'));
      setBundle(null);
    } finally {
      setLoading(false);
    }
  }, [clientId, enabled]);

  useEffect(() => {
    load();
  }, [load]);

  return {
    loading,
    error,
    reload: load,
    showRecoveryPanel: Boolean(bundle?.show_recovery_panel),
    redemptions: bundle?.redemptions || [],
    eligibilityOverrides: bundle?.eligibility_overrides || [],
    overrideHistory: bundle?.override_history || bundle?.eligibility_overrides || [],
    waiverHistory: bundle?.waiver_history || [],
    latestRedemption: bundle?.latest_redemption || bundle?.redemptions?.[0] || null,
    indicators: bundle?.indicators || {},
    inviteMetadata: bundle?.invite_metadata || {},
    strandedCount: bundle?.indicators?.recoverable_count ?? 0,
    onboardingRecoveryAssessment: bundle?.onboarding_recovery_assessment || null,
  };
}
