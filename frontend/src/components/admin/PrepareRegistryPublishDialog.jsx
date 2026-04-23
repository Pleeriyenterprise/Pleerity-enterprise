import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { adminAPI } from '../../api/client';
import { toast } from '@/utils/portalNotifications';

/**
 * Safe row-level entry into the governed publish queue (create → submit → approve → publish elsewhere).
 * Fetches publish-impact first; does not bypass validation or audit (handled server-side on publish).
 */
export default function PrepareRegistryPublishDialog({
  open,
  onOpenChange,
  entryId,
  canonicalCode,
  scopeKey,
  canMutate,
}) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [impact, setImpact] = useState(null);
  const [ack, setAck] = useState(false);

  useEffect(() => {
    if (!open || !entryId) {
      setImpact(null);
      setAck(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    adminAPI
      .getComplianceRegistryPublishImpact(entryId)
      .then((res) => {
        if (!cancelled) setImpact(res.data || null);
      })
      .catch((err) => {
        if (!cancelled) {
          const d = err?.response?.data?.detail;
          toast.error(typeof d === 'string' ? d : 'Could not load publish impact', { critical: true });
          setImpact(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, entryId]);

  const perDraft = impact?.impact?.per_draft?.[0];
  const errs = Array.isArray(perDraft?.validation_errors) ? perDraft.validation_errors : [];
  const rem = impact?.rematerialisation;

  const createQueue = () => {
    if (!canMutate || !entryId || !ack) return;
    setCreating(true);
    const title = `Single line: ${String(canonicalCode || '').toUpperCase()} | ${String(scopeKey || 'DEFAULT')}`;
    adminAPI
      .createComplianceRegistryPublishQueue({ title, draft_entry_ids: [entryId] })
      .then((res) => {
        const qid = res.data?.queue?.queue_id;
        toast.success(
          'Publish queue item created. Submit for review, then Owner approves and publishes. ' +
            'The live registry snapshot merges this line’s keys; other published keys stay unless a later publish replaces them.',
        );
        onOpenChange(false);
        if (qid) {
          navigate(`/admin/compliance/registry/publish-queue?q=${encodeURIComponent(qid)}`);
        } else {
          navigate('/admin/compliance/registry/publish-queue');
        }
      })
      .catch((err) => {
        const d = err?.response?.data?.detail;
        toast.error(typeof d === 'string' ? d : 'Create queue failed', { critical: true });
      })
      .finally(() => setCreating(false));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Prepare publish (governed path)</DialogTitle>
          <DialogDescription>
            This creates a <strong>publish-queue item</strong> for this draft only. It does not publish immediately.
            Validation runs again on submit/publish server-side.
          </DialogDescription>
        </DialogHeader>

        <div className="text-xs text-slate-700 space-y-3">
          <p>
            <strong>Registry truth (immediate after Owner publish):</strong> the active published snapshot map used by
            the planner and resolver is updated for the keys in this queue (merged into existing snapshot keys).
          </p>
          <p>
            <strong>Property rows (not automatic fleet-wide):</strong>{' '}
            {rem?.detail ||
              'Per-property Mongo requirement rows refresh when materialise/sync runs for that property — not instantly for every portfolio.'}
          </p>
        </div>

        {loading ? (
          <p className="text-sm text-gray-600">Loading impact…</p>
        ) : (
          <div className="rounded border border-gray-200 bg-gray-50 p-3 text-xs space-y-2">
            <p className="font-mono text-gray-800">
              {String(canonicalCode || '').toUpperCase()} · {String(scopeKey || 'DEFAULT')}
            </p>
            {errs.length > 0 ? (
              <div>
                <p className="font-semibold text-red-800 mb-1">Validation blocks publish until fixed:</p>
                <ul className="list-disc pl-4 text-red-900 space-y-0.5">
                  {errs.slice(0, 12).map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
                {errs.length > 12 ? <p className="text-red-800 mt-1">…and {errs.length - 12} more</p> : null}
              </div>
            ) : (
              <p className="text-teal-900">No validation errors reported for this draft in the impact payload.</p>
            )}
          </div>
        )}

        <label className="flex items-start gap-2 text-sm text-gray-800 cursor-pointer">
          <input type="checkbox" className="mt-1" checked={ack} onChange={(e) => setAck(e.target.checked)} />
          <span>
            I understand this is a <strong>queue + approval</strong> path (not a silent one-click publish), and that
            published registry truth updates globally while property materialisation may still need per-site sync.
          </span>
        </label>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={createQueue}
            disabled={!canMutate || !ack || creating || errs.length > 0 || loading}
          >
            {creating ? 'Creating…' : 'Create queue item'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
