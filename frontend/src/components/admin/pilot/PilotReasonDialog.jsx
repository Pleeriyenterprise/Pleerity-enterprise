import React, { useState } from 'react';
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
import { apiErrorMessage } from '../../../utils/apiErrorMessage';

export default function PilotReasonDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirm',
  destructive = false,
  minReasonLength = 3,
  extraFields = null,
  onConfirm,
}) {
  const [reason, setReason] = useState('');
  const [extra, setExtra] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if ((reason || '').trim().length < minReasonLength) {
      setError(`Reason must be at least ${minReasonLength} characters`);
      return;
    }
    setLoading(true);
    setError('');
    try {
      await onConfirm({ reason: reason.trim(), ...extra });
      setReason('');
      setExtra({});
      onOpenChange(false);
    } catch (err) {
      setError(apiErrorMessage(err, 'Action failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            {description && <DialogDescription>{description}</DialogDescription>}
          </DialogHeader>
          <div className="space-y-3 py-2">
            <label className="block text-sm">
              <span className="font-medium">Reason (required)</span>
              <Input
                className="mt-1"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Operational reason for audit trail"
                data-testid="pilot-action-reason"
              />
            </label>
            {extraFields?.({ extra, setExtra })}
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" variant={destructive ? 'destructive' : 'default'} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              {confirmLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
