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

const ACTION_ID = 'onboarding_recovery_execute';

/**
 * Governed execution for onboarding recovery (checkout regeneration or activation resend).
 */
export default function OnboardingRecoveryExecuteDialog({
  open,
  onOpenChange,
  clientId,
  mode,
  classification,
  onSubmit,
}) {
  const [reason, setReason] = useState('');
  const [sendCustomerEmail, setSendCustomerEmail] = useState(true);
  const [preservePromo, setPreservePromo] = useState(true);
  const [applyWaiver, setApplyWaiver] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const showWaiverOption = classification === 'FIRST_TIME_RESTRICTION_COLLISION';
  const showPromoOption = mode === 'regenerate_payment';

  useEffect(() => {
    if (open) {
      setReason('');
      setSendCustomerEmail(true);
      setPreservePromo(true);
      setApplyWaiver(false);
      setConfirmed(false);
      setError('');
    }
  }, [open]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!confirmed) {
      setError('Please confirm you have reviewed impact and reason.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await onSubmit({
        mode,
        reason: reason.trim(),
        send_customer_email: sendCustomerEmail,
        preserve_promo_eligibility: preservePromo,
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
              Delivers a customer continuation path (email and/or secure link). Recovery is not complete until the
              customer can act.
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
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={sendCustomerEmail}
                onChange={(e) => setSendCustomerEmail(e.target.checked)}
                data-testid="recovery-execute-send-email"
              />
              <span>Send customer continuation email</span>
            </label>
            {showPromoOption && (
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={preservePromo}
                  onChange={(e) => setPreservePromo(e.target.checked)}
                  data-testid="recovery-execute-preserve-promo"
                />
                <span>Preserve promo eligibility on checkout</span>
              </label>
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
