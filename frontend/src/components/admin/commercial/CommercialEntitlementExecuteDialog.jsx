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
import { adminAPI } from '../../../api/client';
import { apiErrorMessage } from '../../../utils/apiErrorMessage';
import {
  getGovernanceConfirmationWording,
  getGovernanceWarning,
} from '../../../utils/adminActionGovernance';
import { commercialActionLabel } from '../../../utils/commercialEntitlementAdmin';

const ACTION_ID = 'commercial_entitlement_execute';

const NEEDS_DURATION = new Set([
  'grant_grace_period',
  'suspend_billing',
  'grant_sponsored_access',
  'retention_extension',
  'waive_onboarding_fee',
  'apply_recovery_compensation',
  'restrict_entitlement',
]);

const NEEDS_SPONSOR = new Set(['grant_sponsored_access']);

export default function CommercialEntitlementExecuteDialog({
  open,
  onOpenChange,
  clientId,
  action,
  onSubmit,
}) {
  const [reason, setReason] = useState('');
  const [durationDays, setDurationDays] = useState(14);
  const [sponsorReference, setSponsorReference] = useState('');
  const [sendCustomerEmail, setSendCustomerEmail] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setReason('');
    setDurationDays(14);
    setSponsorReference('');
    setSendCustomerEmail(false);
    setConfirmed(false);
    setError('');
    setPreview(null);
  }, [open, action]);

  useEffect(() => {
    if (!open || !clientId || !action || action === 'resume_billing' || action === 'revoke_commercial_exception') {
      return;
    }
    let cancelled = false;
    const load = async () => {
      setPreviewLoading(true);
      try {
        const body = { action, duration_days: durationDays };
        if (NEEDS_SPONSOR.has(action) && sponsorReference.trim()) {
          body.sponsor_reference = sponsorReference.trim();
        }
        const res = await adminAPI.previewCommercialEntitlementImpact(clientId, body);
        if (!cancelled) setPreview(res.data?.impact_preview || null);
      } catch {
        if (!cancelled) setPreview(null);
      } finally {
        if (!cancelled) setPreviewLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [open, clientId, action, durationDays, sponsorReference]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!confirmed) {
      setError('Please confirm you have reviewed impact and reason.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const body = {
        action,
        reason: reason.trim(),
        send_customer_email: sendCustomerEmail,
      };
      if (NEEDS_DURATION.has(action)) body.duration_days = durationDays;
      if (NEEDS_SPONSOR.has(action)) body.sponsor_reference = sponsorReference.trim();
      await onSubmit(body);
      onOpenChange(false);
    } catch (err) {
      if (err?.message === 'step_up_cancelled') return;
      setError(apiErrorMessage(err, 'Commercial action failed'));
    } finally {
      setLoading(false);
    }
  };

  const revocable = action === 'resume_billing' || action === 'revoke_commercial_exception';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="commercial-entitlement-execute-dialog">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{commercialActionLabel(action)}</DialogTitle>
            <DialogDescription>
              Governed commercial exception — platform state is authoritative; Stripe reconciliation is lightweight in v1.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2 text-sm">
            <p className="text-xs text-amber-900 rounded border border-amber-200 bg-amber-50 p-2">
              {getGovernanceWarning(ACTION_ID)}
            </p>
            {previewLoading && <p className="text-xs text-gray-500">Loading impact preview…</p>}
            {preview && (
              <div className="rounded border border-slate-200 bg-slate-50 p-2 text-xs space-y-1" data-testid="commercial-impact-preview">
                <p><span className="font-semibold">Customer:</span> {preview.customer_impact}</p>
                <p><span className="font-semibold">Access:</span> {preview.access_impact}</p>
                <p><span className="font-semibold">Billing:</span> {preview.billing_impact}</p>
                <p><span className="font-semibold">Continuity:</span> {preview.operational_continuity}</p>
                <p><span className="font-semibold">Stripe:</span> {preview.stripe_impact}</p>
              </div>
            )}
            {!revocable && NEEDS_DURATION.has(action) && (
              <label className="block">
                <span className="font-medium">Duration (days)</span>
                <input
                  type="number"
                  min={1}
                  max={90}
                  className="mt-1 w-full border rounded px-2 py-1.5 text-sm"
                  value={durationDays}
                  onChange={(e) => setDurationDays(Number(e.target.value) || 1)}
                  data-testid="commercial-execute-duration"
                />
              </label>
            )}
            {NEEDS_SPONSOR.has(action) && (
              <label className="block">
                <span className="font-medium">Sponsor reference (required)</span>
                <input
                  className="mt-1 w-full border rounded px-2 py-1.5 text-sm"
                  value={sponsorReference}
                  onChange={(e) => setSponsorReference(e.target.value)}
                  required
                  data-testid="commercial-execute-sponsor"
                />
              </label>
            )}
            <label className="block">
              <span className="font-medium">Support reason (min 10 characters)</span>
              <textarea
                className="mt-1 w-full border rounded px-2 py-1.5 text-sm min-h-[72px]"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                required
                minLength={10}
                data-testid="commercial-execute-reason"
              />
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={sendCustomerEmail}
                onChange={(e) => setSendCustomerEmail(e.target.checked)}
                data-testid="commercial-execute-send-email"
              />
              <span>Send customer continuity email</span>
            </label>
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
                className="mt-1"
                data-testid="commercial-execute-confirm"
              />
              <span className="text-xs text-gray-700">{getGovernanceConfirmationWording(ACTION_ID)}</span>
            </label>
            {error && (
              <p className="text-xs text-red-700" data-testid="commercial-execute-error">
                {error}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading || reason.trim().length < 10}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Apply'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
