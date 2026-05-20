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
import { Input } from '../../ui/input';
import { Loader2 } from 'lucide-react';
import {
  ELIGIBILITY_OVERRIDE_TYPES,
  OVERRIDE_SCOPE_OPTIONS,
  buildOverridePayload,
  overrideTypeLabel,
} from '../../../utils/pilotRedemptionAdmin';

/**
 * Reason-required modal for eligibility overrides (no silent overrides).
 * onSubmit receives API-ready body from buildOverridePayload.
 */
export default function PilotEligibilityOverrideDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Grant override',
  defaultOverrideType = 'bypass_first_time',
  defaultScope = 'client_id',
  defaultScopeValue = '',
  lockScope = false,
  lockOverrideType = false,
  onSubmit,
}) {
  const [overrideType, setOverrideType] = useState(defaultOverrideType);
  const [scope, setScope] = useState(defaultScope);
  const [scopeValue, setScopeValue] = useState(defaultScopeValue);
  const [reason, setReason] = useState('');
  const [expiresAt, setExpiresAt] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      setOverrideType(defaultOverrideType);
      setScope(defaultScope);
      setScopeValue(defaultScopeValue);
      setReason('');
      setExpiresAt('');
      setError('');
    }
  }, [open, defaultOverrideType, defaultScope, defaultScopeValue]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const body = buildOverridePayload({
        overrideType,
        reason,
        scope,
        scopeValue,
        expiresAt: expiresAt || undefined,
      });
      await onSubmit(body);
      onOpenChange(false);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed');
    } finally {
      setLoading(false);
    }
  };

  const typeMeta = ELIGIBILITY_OVERRIDE_TYPES.find((t) => t.value === overrideType);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="pilot-eligibility-override-dialog">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{title || overrideTypeLabel(overrideType)}</DialogTitle>
            {description && <DialogDescription>{description}</DialogDescription>}
          </DialogHeader>
          <div className="space-y-3 py-2">
            <label className="block text-sm">
              <span className="font-medium">Override type</span>
              <select
                className="mt-1 w-full border rounded px-2 py-1.5 text-sm"
                value={overrideType}
                disabled={lockOverrideType}
                onChange={(e) => setOverrideType(e.target.value)}
                data-testid="override-type-select"
              >
                {ELIGIBILITY_OVERRIDE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
              {typeMeta?.description && (
                <p className="text-xs text-gray-500 mt-1">{typeMeta.description}</p>
              )}
            </label>
            <label className="block text-sm">
              <span className="font-medium">Scope</span>
              <select
                className="mt-1 w-full border rounded px-2 py-1.5 text-sm"
                value={scope}
                disabled={lockScope}
                onChange={(e) => setScope(e.target.value)}
                data-testid="override-scope-select"
              >
                {OVERRIDE_SCOPE_OPTIONS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="font-medium">Scope value</span>
              <Input
                className="mt-1"
                value={scopeValue}
                disabled={lockScope && Boolean(defaultScopeValue)}
                onChange={(e) => setScopeValue(e.target.value)}
                placeholder={scope === 'email' ? 'user@example.com' : 'client id or invite id'}
                data-testid="override-scope-value"
              />
            </label>
            <label className="block text-sm">
              <span className="font-medium">Reason (required)</span>
              <Input
                className="mt-1"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Operational reason for audit trail"
                data-testid="override-reason-input"
              />
            </label>
            <label className="block text-sm">
              <span className="font-medium">Expires at (optional)</span>
              <Input
                type="datetime-local"
                className="mt-1"
                value={expiresAt}
                onChange={(e) => setExpiresAt(e.target.value)}
                data-testid="override-expires-input"
              />
            </label>
            {error && <p className="text-sm text-red-600" data-testid="override-dialog-error">{error}</p>}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading} data-testid="override-dialog-confirm">
              {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              {confirmLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
