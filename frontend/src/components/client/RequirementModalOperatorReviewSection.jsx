import React, { useCallback, useState } from 'react';
import { CheckCircle, Loader2, XCircle } from 'lucide-react';
import { Button } from '../ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';
import { toast } from '@/utils/portalNotifications';
import {
  OPERATOR_REVIEW_GUIDANCE,
  buildOperatorReviewContextSummary,
  humanizeEvidenceConfidence,
  resolveOrgReviewEvidenceRecordId,
  submitOrgComplianceEvidenceVerification,
} from '../../utils/orgComplianceReviewOperator';

function formatOperatorDate(value) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  } catch {
    return String(value);
  }
}

/**
 * Inline org-admin verify/reject for hydrated requirement review modal.
 */
export default function RequirementModalOperatorReviewSection({
  merged,
  latestCer,
  propertyId,
  requirementId,
  onResolved,
  disabled = false,
}) {
  const [acting, setActing] = useState(null);
  const [rejectOpen, setRejectOpen] = useState(false);

  const evidenceRecordId = resolveOrgReviewEvidenceRecordId(merged, latestCer);
  const summary = buildOperatorReviewContextSummary(merged, latestCer);
  const confidenceLine = humanizeEvidenceConfidence(summary.confidenceLevel);

  const runDecision = useCallback(
    async (decision) => {
      if (!propertyId || !requirementId || !evidenceRecordId) {
        toast.error('Missing evidence context for verification');
        return;
      }
      setActing(decision);
      try {
        await submitOrgComplianceEvidenceVerification({
          propertyId,
          requirementId,
          evidenceRecordId,
          decision,
        });
        toast.success(decision === 'VERIFY' ? 'Submission verified' : 'Submission rejected');
        setRejectOpen(false);
        await onResolved?.();
      } catch (e) {
        toast.error(e?.response?.data?.detail || 'Verification failed');
      } finally {
        setActing(null);
      }
    },
    [propertyId, requirementId, evidenceRecordId, onResolved],
  );

  const actionsDisabled = disabled || !evidenceRecordId || Boolean(acting);

  return (
    <section
      className="rounded-lg border border-teal-200 bg-teal-50/50 p-4 space-y-4"
      data-testid="requirement-modal-operator-review"
    >
      <div>
        <h3 className="text-xs font-semibold text-midnight-blue uppercase tracking-wide mb-1">Organisation review</h3>
        <p className="text-sm text-gray-800 leading-relaxed" data-testid="operator-review-guidance">
          {OPERATOR_REVIEW_GUIDANCE.inspect}
        </p>
      </div>

      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-2 text-sm" data-testid="operator-review-context-summary">
        <div>
          <dt className="text-xs text-gray-500">Review status</dt>
          <dd className="font-medium text-gray-900">{summary.reviewStatus}</dd>
        </div>
        {summary.evidenceType ? (
          <div>
            <dt className="text-xs text-gray-500">Evidence type</dt>
            <dd className="font-medium text-gray-900">{summary.evidenceType}</dd>
          </div>
        ) : null}
        <div>
          <dt className="text-xs text-gray-500">Submitted</dt>
          <dd className="font-medium text-gray-900">{formatOperatorDate(summary.submittedAt)}</dd>
        </div>
        {summary.submittedBy ? (
          <div>
            <dt className="text-xs text-gray-500">Submitted by (user id)</dt>
            <dd className="font-medium text-gray-900 break-all">{summary.submittedBy}</dd>
          </div>
        ) : null}
      </dl>

      {confidenceLine ? (
        <p className="text-sm text-gray-800" data-testid="operator-review-confidence">
          {confidenceLine}
        </p>
      ) : null}

      <div className="flex flex-col sm:flex-row gap-2 sm:items-center" data-testid="operator-review-actions">
        <Button
          type="button"
          size="sm"
          className="min-h-10 bg-electric-teal hover:bg-electric-teal/90 text-midnight-blue font-semibold"
          disabled={actionsDisabled || acting === 'VERIFY'}
          onClick={() => runDecision('VERIFY')}
          data-testid="operator-review-verify"
        >
          {acting === 'VERIFY' ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <CheckCircle className="h-4 w-4 mr-1" />
              Verify
            </>
          )}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="destructive"
          className="min-h-10"
          disabled={actionsDisabled || acting === 'REJECT'}
          onClick={() => setRejectOpen(true)}
          data-testid="operator-review-reject-open"
        >
          {acting === 'REJECT' ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <XCircle className="h-4 w-4 mr-1" />
              Reject
            </>
          )}
        </Button>
      </div>
      <p className="text-xs text-gray-600">
        <span className="font-medium">Verify:</span> {OPERATOR_REVIEW_GUIDANCE.verify}{' '}
        <span className="font-medium">Reject:</span> {OPERATOR_REVIEW_GUIDANCE.reject}
      </p>

      <AlertDialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <AlertDialogContent data-testid="operator-review-reject-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Reject this submission?</AlertDialogTitle>
            <AlertDialogDescription>
              The submitter will need to correct or resubmit evidence for this requirement. This uses the same
              governance path as rejecting from the compliance review queue.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={Boolean(acting)}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={Boolean(acting)}
              onClick={(e) => {
                e.preventDefault();
                runDecision('REJECT');
              }}
              data-testid="operator-review-reject-confirm"
            >
              Reject submission
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
