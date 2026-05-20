import React from 'react';
import { Link } from 'react-router-dom';
import { Alert, AlertDescription } from '../../ui/alert';
import { usePilotAccountRecovery } from '../../../hooks/usePilotAccountRecovery';
import { shouldShowRecoveryPanel } from '../../../utils/pilotRedemptionAdmin';
import PilotRecoveryIndicatorBadges from './PilotRecoveryIndicatorBadges';
import PromoRecoveryStateSummary from './PromoRecoveryStateSummary';
import PilotRedemptionRecoverySection from './PilotRedemptionRecoverySection';

/**
 * Account-scoped promo recovery (Client Control Panel + pilot ops).
 * Visible for stranded / incomplete onboarding — not only active pilot lifecycle.
 */
export default function PilotAccountRecoveryPanel({
  clientId,
  defaultEmail,
  inviteCode: inviteCodeProp,
  accountClientPathPrefix = '/admin/clients',
  sectionTitle = 'Promo & Recovery Controls',
  showPilotOpsLink = true,
  showAllControls = true,
  enabled = true,
}) {
  const {
    loading,
    error,
    reload,
    showRecoveryPanel,
    redemptions,
    eligibilityOverrides,
    indicators,
    inviteMetadata,
    strandedCount,
    overrideHistory,
    waiverHistory,
    latestRedemption,
  } = usePilotAccountRecovery(clientId, { enabled });

  const inviteCode = inviteCodeProp || inviteMetadata?.pilot_invite_code;
  const visible = shouldShowRecoveryPanel({
    showRecoveryPanel,
    redemptions,
    eligibilityOverrides,
    inviteMetadata,
  });

  if (!enabled) return null;
  if (!loading && !visible && !error) return null;

  return (
    <div className="space-y-3" data-testid="pilot-account-recovery-panel">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {visible && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <PilotRecoveryIndicatorBadges indicators={indicators} />
            {showPilotOpsLink && (
              <Link
                className="text-xs text-teal-700 hover:underline shrink-0"
                to={`/admin/pilot-operations/accounts/${encodeURIComponent(clientId)}`}
              >
                Founding Pilot Operations
              </Link>
            )}
          </div>
          <PromoRecoveryStateSummary
            inviteMetadata={inviteMetadata}
            indicators={indicators}
            latestRedemption={latestRedemption}
            inviteCode={inviteCode}
          />
          <PilotRedemptionRecoverySection
            context="account"
            clientId={clientId}
            inviteCode={inviteCode}
            redemptions={redemptions}
            eligibilityOverrides={overrideHistory || eligibilityOverrides}
            waiverHistory={waiverHistory}
            loading={loading}
            onReload={reload}
            defaultEmail={defaultEmail || inviteMetadata?.email}
            strandedCount={strandedCount}
            accountClientPathPrefix={accountClientPathPrefix}
            panelTitle="Operational actions"
            showAllControls={showAllControls}
          />
        </>
      )}
    </div>
  );
}
