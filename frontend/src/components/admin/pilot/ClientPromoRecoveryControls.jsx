import React, { useMemo, useState } from 'react';
import { ChevronDown, AlertTriangle } from 'lucide-react';
import { Alert, AlertDescription } from '../../ui/alert';
import { usePilotAccountRecovery } from '../../../hooks/usePilotAccountRecovery';
import { formatDisplayValue } from '../../../utils/apiErrorMessage';
import { shouldShowRecoveryPanel } from '../../../utils/pilotRedemptionAdmin';
import PilotRecoveryIndicatorBadges from './PilotRecoveryIndicatorBadges';
import PromoRecoveryStateSummary from './PromoRecoveryStateSummary';
import PilotRedemptionRecoverySection from './PilotRedemptionRecoverySection';

/**
 * First-class promo & recovery surface for Client Control Panel.
 * Reuses shared recovery APIs and components — no duplicate business logic.
 */
export default function ClientPromoRecoveryControls({
  clientId,
  defaultEmail,
  accountHints = {},
  enabled = true,
}) {
  const {
    loading,
    error,
    reload,
    showRecoveryPanel,
    redemptions,
    eligibilityOverrides,
    overrideHistory,
    waiverHistory,
    indicators,
    inviteMetadata,
    latestRedemption,
    strandedCount,
  } = usePilotAccountRecovery(clientId, { enabled });

  const visible = shouldShowRecoveryPanel({
    showRecoveryPanel,
    redemptions,
    eligibilityOverrides,
    inviteMetadata,
  });

  const defaultOpen = useMemo(
    () =>
      Boolean(
        indicators?.stranded_onboarding ||
          indicators?.payment_failed ||
          indicators?.provisioning_failed ||
          indicators?.retry_blocked,
      ),
    [indicators],
  );

  const [open, setOpen] = useState(defaultOpen);

  if (!enabled) return null;
  if (!loading && !visible && !error) return null;

  const inviteCode = inviteMetadata?.pilot_invite_code;

  return (
    <section
      className="rounded-xl bg-white border border-amber-200/90 shadow-sm"
      data-testid="client-promo-recovery-controls"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-amber-50/50 rounded-xl transition-colors"
        aria-expanded={open}
      >
        <div className="flex items-start gap-2">
          {indicators?.stranded_onboarding && (
            <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" aria-hidden />
          )}
          <div>
            <div className="text-sm font-semibold text-midnight-blue">Promo &amp; Recovery Controls</div>
            <div className="text-xs text-gray-500 mt-0.5">
              Onboarding, promo eligibility, waivers, and redemption recovery — available before successful
              provisioning.
            </div>
            {!open && (
              <div className="mt-2">
                <PilotRecoveryIndicatorBadges indicators={indicators} />
              </div>
            )}
          </div>
        </div>
        <ChevronDown
          className={`h-5 w-5 shrink-0 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {error && (
        <div className="px-4 pt-2" data-testid="promo-recovery-error">
          <Alert variant="destructive">
            <AlertDescription>{formatDisplayValue(error, 'Failed to load promo recovery data')}</AlertDescription>
          </Alert>
        </div>
      )}

      {open && (
        <div className="px-4 pb-4 space-y-4 border-t border-amber-100/80">
          <PilotRecoveryIndicatorBadges indicators={indicators} />
          <PromoRecoveryStateSummary
            inviteMetadata={inviteMetadata}
            indicators={indicators}
            latestRedemption={latestRedemption}
            accountHints={accountHints}
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
            accountClientPathPrefix="/admin/clients"
            panelTitle="Operational actions"
            embedded
            showAllControls
          />
        </div>
      )}
    </section>
  );
}
