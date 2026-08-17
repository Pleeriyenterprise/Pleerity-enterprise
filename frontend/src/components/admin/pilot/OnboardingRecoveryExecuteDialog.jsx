import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { Loader2 } from 'lucide-react';
import { apiErrorMessage } from '../../../utils/apiErrorMessage';
import {
  getGovernanceConfirmationWording,
  getGovernanceWarning,
} from '../../../utils/adminActionGovernance';
import { recoveryModeLabel } from '../../../utils/onboardingRecoveryAdmin';
import { adminAPI } from '../../../api/client';

const ACTION_ID = 'onboarding_recovery_execute';

/**
 * Governed execution for onboarding recovery (checkout regeneration, activation, or release).
 */
export default function OnboardingRecoveryExecuteDialog({
  open,
  onOpenChange,
  clientId,
  mode,
  classification,
  assessment,
  onSubmit,
}) {
  const [reason, setReason] = useState('');
  const [sendCustomerEmail, setSendCustomerEmail] = useState(true);
  const [promoDecision, setPromoDecision] = useState('none');
  const [selectedInviteCode, setSelectedInviteCode] = useState('');
  const [approvedPromos, setApprovedPromos] = useState([]);
  const [applyWaiver, setApplyWaiver] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const showWaiverOption =
    classification === 'FIRST_TIME_RESTRICTION_COLLISION' &&
    (mode === 'regenerate_payment' || mode === 'resume_onboarding');
  const showPromoOption = mode === 'regenerate_payment';
  const isRelease = mode === 'release_and_restart';
  const hasValidatedPromo = Boolean(assessment?.promo_recovery?.has_validated_promo);

  useEffect(() => {
    if (open) {
      setReason('');
      setSendCustomerEmail(!isRelease);
      setPromoDecision(hasValidatedPromo ? 'preserve_existing' : 'none');
      setSelectedInviteCode('');
      setApplyWaiver(false);
      setConfirmed(false);
      setError('');
    }
  }, [open, hasValidatedPromo, isRelease]);

  useEffect(() => {
    if (!open || !showPromoOption || hasValidatedPromo) return undefined;
    let cancelled = false;
    adminAPI
      .getApprovedRecoveryPromos()
      .then((res) => {
        if (!cancelled) setApprovedPromos(res.data?.promos || []);
      })
      .catch(() => {
        if (!cancelled) setApprovedPromos([]);
      });
    return () => {
      cancelled = true;
    };
  }, [open, showPromoOption, hasValidatedPromo]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!confirmed) {
      setError('Please confirm you have reviewed impact and reason.');
      return;
    }
    if (showPromoOption && promoDecision === 'apply_selected' && !selectedInviteCode) {
      setError('Select an approved promotion.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await onSubmit({
        mode,
        reason: reason.trim(),
        send_customer_email: isRelease ? false : sendCustomerEmail,
        preserve_promo_eligibility: promoDecision === 'preserve_existing',
        promo_decision: showPromoOption ? promoDecision : 'none',
        selected_invite_code: promoDecision === 'apply_selected' ? selectedInviteCode : null,
        apply_recovery_waiver: applyWaiver,
      });
      onOpenChange(false);
    } catch (err) {
      if (err?.message === 'step_up_cancelled') return;
      setError(apiErrorMessage(err, 'Recovery execution failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="onboarding-recovery-execute-dialog">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Run {recoveryModeLabel(mode)}</DialogTitle>
            <DialogDescription>
              {mode === 'resume_onboarding'
                ? 'Sends a secure continuation link so the customer can resume saved intake progress — not a restart.'
                : isRelease
                  ? 'Preserves this attempt as released, frees the email reservation, and invalidates stale links. Does not delete history.'
                  : 'Delivers a customer continuation path (email and/or secure link). Recovery is not complete until the customer can act.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2 text-sm">
            <p className="text-xs text-amber-900 rounded border border-amber-200 bg-amber-50 p-2">
              {getGovernanceWarning(ACTION_ID)}
            </p>
            <label className="block">
              <span className="font-medium">Support reason (min 10 characters)</span>
              <textarea
                className="mt-1 w-full border rounded px-2 py-1.5 text-sm min-h-[72px]"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                required
                minLength={10}
                data-testid="recovery-execute-reason"
              />
            </label>
            {!isRelease && (
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={sendCustomerEmail}
                  onChange={(e) => setSendCustomerEmail(e.target.checked)}
                  data-testid="recovery-execute-send-email"
                />
                <span>Send customer continuation email</span>
              </label>
            )}
            {showPromoOption && hasValidatedPromo && (
              <fieldset className="space-y-1 rounded border border-slate-200 p-2" data-testid="recovery-promo-existing">
                <legend className="text-xs font-semibold">This onboarding attempt has an eligible promotion attached.</legend>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="promo-decision"
                    checked={promoDecision === 'preserve_existing'}
                    onChange={() => setPromoDecision('preserve_existing')}
                    data-testid="recovery-promo-preserve"
                  />
                  <span>Apply existing promo</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="promo-decision"
                    checked={promoDecision === 'none'}
                    onChange={() => setPromoDecision('none')}
                    data-testid="recovery-promo-paid"
                  />
                  <span>Generate normal paid checkout</span>
                </label>
              </fieldset>
            )}
            {showPromoOption && !hasValidatedPromo && (
              <fieldset className="space-y-1 rounded border border-slate-200 p-2" data-testid="recovery-promo-select">
                <legend className="text-xs font-semibold">Does this customer require a promotion for this recovery?</legend>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="promo-decision"
                    checked={promoDecision === 'none'}
                    onChange={() => setPromoDecision('none')}
                    data-testid="recovery-promo-no"
                  />
                  <span>No</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="promo-decision"
                    checked={promoDecision === 'apply_selected'}
                    onChange={() => setPromoDecision('apply_selected')}
                    data-testid="recovery-promo-yes"
                  />
                  <span>Yes — select approved promotion</span>
                </label>
                {promoDecision === 'apply_selected' && (
                  <select
                    className="mt-1 w-full border rounded px-2 py-1.5 text-sm"
                    value={selectedInviteCode}
                    onChange={(e) => setSelectedInviteCode(e.target.value)}
                    data-testid="recovery-promo-code"
                  >
                    <option value="">Select promotion</option>
                    {approvedPromos.map((p) => (
                      <option key={p.code} value={p.code}>
                        {p.code}
                        {p.campaign_name ? ` — ${p.campaign_name}` : ''}
                      </option>
                    ))}
                  </select>
                )}
              </fieldset>
            )}
            {showWaiverOption && (
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={applyWaiver}
                  onChange={(e) => setApplyWaiver(e.target.checked)}
                  data-testid="recovery-execute-apply-waiver"
                />
                <span>Apply recover-onboarding eligibility waiver before checkout</span>
              </label>
            )}
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
                className="mt-1"
                data-testid="recovery-execute-confirm"
              />
              <span className="text-xs text-gray-700">{getGovernanceConfirmationWording(ACTION_ID)}</span>
            </label>
            {error && (
              <p className="text-xs text-red-700" data-testid="recovery-execute-error">
                {error}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading || reason.trim().length < 10}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Run recovery'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
