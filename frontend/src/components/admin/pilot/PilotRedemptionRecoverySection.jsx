import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, Loader2, Plus, ShieldOff, RefreshCw } from 'lucide-react';
import { adminAPI } from '../../../api/client';
import { Button } from '../../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../ui/card';
import { toast } from '@/utils/portalNotifications';
import { formatDisplayValue } from '../../../utils/apiErrorMessage';
import PilotEligibilityOverrideDialog from './PilotEligibilityOverrideDialog';
import PilotReasonDialog from './PilotReasonDialog';
import {
  isOverrideActive,
  overrideTypeLabel,
  redemptionStatusBadgeClass,
  showAllowRetryAction,
  showResetIncompleteAction,
} from '../../../utils/pilotRedemptionAdmin';

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-GB');
  } catch {
    return String(iso);
  }
}

function CollapsibleSubsection({ title, count, defaultOpen = true, children, testId }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-100 rounded-lg overflow-hidden" data-testid={testId}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-left bg-slate-50/80 hover:bg-slate-100/80 text-sm font-medium"
        aria-expanded={open}
      >
        <span>
          {title}
          {count != null ? ` (${count})` : ''}
        </span>
        <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && <div className="p-3 space-y-2">{children}</div>}
    </div>
  );
}

function RedemptionRow({
  redemption,
  inviteCode,
  onReload,
  allowRetryApi,
  resetIncompleteApi,
  onAllowRetry,
  onResetIncomplete,
  accountClientPathPrefix = '/admin/clients',
}) {
  const [busy, setBusy] = useState(null);

  const st = redemption.status;
  const code = redemption.code || inviteCode;

  return (
    <li
      className="border border-slate-100 rounded px-3 py-2 text-xs space-y-1"
      data-testid={`redemption-row-${redemption.redemption_id || redemption.checkout_session_id}`}
    >
      <div className="flex flex-wrap items-center gap-2 justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`px-1.5 py-0.5 rounded font-medium ${redemptionStatusBadgeClass(st)}`}>{st}</span>
          {redemption.retry_eligible ? (
            <span className="text-emerald-700">Retry eligible</span>
          ) : (
            <span className="text-amber-800">Blocked — needs release or override</span>
          )}
          {redemption.within_grace && <span className="text-slate-500">Within grace window</span>}
          {redemption.consumes_eligibility && (
            <span className="text-slate-500">Consumes first-time eligibility</span>
          )}
        </div>
        <div className="flex flex-wrap gap-1">
          {showAllowRetryAction(redemption) && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={busy != null}
              data-testid={`allow-retry-${redemption.redemption_id}`}
              onClick={() => onAllowRetry(redemption)}
            >
              {busy === 'retry' ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Allow retry'}
            </Button>
          )}
          {showResetIncompleteAction(redemption) && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              disabled={busy != null}
              data-testid={`reset-incomplete-${redemption.redemption_id}`}
              onClick={() => onResetIncomplete(redemption)}
            >
              {busy === 'reset' ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Reset incomplete'}
            </Button>
          )}
        </div>
      </div>
      <p className="text-gray-600">
        {redemption.redemption_email && <span>{redemption.redemption_email} · </span>}
        {code && (
          <>
            Invite:{' '}
            <Link className="text-teal-700 hover:underline" to={`/admin/pilot-invites/${encodeURIComponent(code)}`}>
              {code}
            </Link>
            {' · '}
          </>
        )}
        {redemption.code_type && <span>Type: {redemption.code_type} · </span>}
        {redemption.campaign_name && <span>Campaign: {redemption.campaign_name} · </span>}
        Created {formatDate(redemption.created_at)}
        {redemption.updated_at && <> · Updated {formatDate(redemption.updated_at)}</>}
      </p>
      {redemption.failure_reason && (
        <p className="text-red-800/90" data-testid="redemption-failure-reason">
          Failure: {formatDisplayValue(redemption.failure_reason)}
        </p>
      )}
      {(redemption.checkout_session_id || redemption.plan_code) && (
        <p className="text-gray-500 font-mono text-[10px]">
          {redemption.plan_code && <span>Plan {redemption.plan_code} · </span>}
          {redemption.checkout_session_id && (
            <span title={redemption.checkout_session_id}>
              Session {String(redemption.checkout_session_id).slice(0, 24)}
              {String(redemption.checkout_session_id).length > 24 ? '…' : ''}
            </span>
          )}
        </p>
      )}
    </li>
  );
}

function OverrideHistoryRow({ override, onRevoke, revokingId }) {
  const active = isOverrideActive(override);
  return (
    <li
      key={override.override_id}
      className={`border rounded p-2 text-xs ${active ? 'border-emerald-100 bg-white' : 'border-slate-100 opacity-80 bg-slate-50'}`}
      data-testid={`override-row-${override.override_id}`}
    >
      <div className="flex flex-wrap justify-between gap-2">
        <div>
          <p className="font-medium">
            {overrideTypeLabel(override.override_type)} · {override.scope}={override.scope_value}
            {!active && <span className="text-slate-500 ml-1">(inactive)</span>}
          </p>
          <p className="text-gray-600 mt-0.5">{formatDisplayValue(override.override_reason)}</p>
          <p className="text-gray-500 mt-0.5">
            By {override.override_actor?.email || override.override_actor?.id || 'admin'} ·{' '}
            {formatDate(override.override_created_at)}
            {override.override_expires_at && <> · Expires {formatDate(override.override_expires_at)}</>}
            {override.revoked_at && (
              <>
                {' '}
                · Revoked {formatDate(override.revoked_at)}
                {override.revoked_by?.email ? ` by ${override.revoked_by.email}` : ''}
              </>
            )}
          </p>
          {override.invite_code && <p className="text-gray-500">Invite: {override.invite_code}</p>}
        </div>
        {active && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={revokingId === override.override_id}
            data-testid={`revoke-override-${override.override_id}`}
            onClick={() => onRevoke(override.override_id)}
          >
            {revokingId === override.override_id ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Revoke'}
          </Button>
        )}
      </div>
    </li>
  );
}

/**
 * Promo / invite redemption recovery (shared by CCP, pilot ops, invite admin).
 */
export default function PilotRedemptionRecoverySection({
  context = 'account',
  clientId,
  inviteCode,
  inviteCodeId,
  redemptions = [],
  eligibilityOverrides = [],
  waiverHistory = [],
  loading = false,
  onReload,
  defaultEmail,
  strandedCount = 0,
  accountClientPathPrefix = '/admin/clients',
  panelTitle = 'Promo / Invite Redemption',
  embedded = false,
  showAllControls = false,
}) {
  const [overrideDialog, setOverrideDialog] = useState(null);
  const [reasonDialog, setReasonDialog] = useState(null);
  const [revokingId, setRevokingId] = useState(null);

  const allowRetryApi = (id, body) => adminAPI.allowPilotRedemptionRetry(id, body);
  const resetIncompleteApi = (id, body) => adminAPI.resetPilotRedemptionIncomplete(id, body);

  const createOverride = async (body) => {
    if (context === 'account' && clientId) {
      await adminAPI.createPilotAccountEligibilityOverride(clientId, {
        ...body,
        invite_code: inviteCode || undefined,
      });
    } else if (inviteCode) {
      await adminAPI.createPilotEligibilityOverride(inviteCode, body);
    } else {
      throw new Error('No invite or account context for override');
    }
    toast.success('Override recorded — auditable in history below');
    await onReload();
  };

  const defaultScopeValue =
    overrideDialog?.defaultScope === 'email'
      ? defaultEmail || ''
      : overrideDialog?.defaultScope === 'invite_code_id'
        ? inviteCodeId || ''
        : clientId || '';

  const openAllowRetry = (redemption) => {
    setReasonDialog({
      type: 'allow_retry',
      redemptionId: redemption.redemption_id,
      title: 'Allow retry',
      description: `Release blocked redemption ${redemption.status} so the customer can try again.`,
      confirmLabel: 'Allow retry',
    });
  };

  const openResetIncomplete = (redemption) => {
    setReasonDialog({
      type: 'reset_incomplete',
      redemptionId: redemption.redemption_id,
      title: 'Reset incomplete redemption',
      description: 'Expire/revoke this attempt without granting an automatic retry override.',
      confirmLabel: 'Reset incomplete',
    });
  };

  const openRevokeOverride = (overrideId) => {
    setReasonDialog({
      type: 'revoke_override',
      overrideId,
      title: 'Revoke override',
      description: 'Revokes the eligibility override. The customer may be blocked again until a new override is granted.',
      confirmLabel: 'Revoke override',
      destructive: true,
    });
  };

  const actionButtons = (
    <div className="flex flex-wrap gap-2">
      <Button
        type="button"
        size="sm"
        variant="default"
        data-testid="grant-promo-eligibility-btn"
        onClick={() =>
          setOverrideDialog({
            title: 'Grant promo eligibility',
            description:
              'Allows an existing user to use a promo despite first-time restriction. Does not change campaign defaults.',
            defaultOverrideType: 'bypass_first_time',
            defaultScope: context === 'invite' ? 'email' : defaultEmail ? 'email' : 'client_id',
            lockScope: context === 'account' && Boolean(clientId || defaultEmail),
          })
        }
      >
        <ShieldOff className="h-3 w-3 mr-1" />
        Grant promo eligibility
      </Button>
      {showAllControls && (
        <Button
          type="button"
          size="sm"
          variant="outline"
          data-testid="bypass-first-time-btn"
          onClick={() =>
            setOverrideDialog({
              title: 'Bypass first-time restriction',
              defaultOverrideType: 'bypass_first_time',
              defaultScope: defaultEmail ? 'email' : 'client_id',
              lockScope: Boolean(clientId || defaultEmail),
            })
          }
        >
          Bypass first-time
        </Button>
      )}
      {showAllControls && (
        <Button
          type="button"
          size="sm"
          variant="outline"
          data-testid="waive-onboarding-btn"
          onClick={() =>
            setOverrideDialog({
              title: 'Waive onboarding fee',
              description:
                'Creates an auditable recover_onboarding override. Does not change global campaign or Stripe catalog defaults.',
              defaultOverrideType: 'recover_onboarding',
              defaultScope: 'client_id',
              lockScope: Boolean(clientId),
            })
          }
        >
          Waive onboarding fee
        </Button>
      )}
      <Button
        type="button"
        size="sm"
        variant="outline"
        data-testid="grant-override-btn"
        onClick={() =>
          setOverrideDialog({
            title: 'Grant promo exception',
            defaultOverrideType: 'manual_attach_promo',
            defaultScope: context === 'invite' ? 'invite_code_id' : 'client_id',
          })
        }
      >
        <Plus className="h-3 w-3 mr-1" />
        Grant promo exception
      </Button>
      <Button
        type="button"
        size="sm"
        variant="outline"
        data-testid="recover-onboarding-btn"
        onClick={() =>
          setOverrideDialog({
            title: 'Recover onboarding',
            defaultOverrideType: 'recover_onboarding',
            defaultScope: 'client_id',
          })
        }
      >
        <RefreshCw className="h-3 w-3 mr-1" />
        Recover onboarding
      </Button>
    </div>
  );

  const body = loading ? (
    <p className="text-sm text-gray-500 flex items-center gap-2">
      <Loader2 className="h-4 w-4 animate-spin" /> Loading recovery data…
    </p>
  ) : (
    <>
      {strandedCount > 0 && (
        <p className="text-sm text-amber-800" data-testid="stranded-redemptions-hint">
          {strandedCount} redemption(s) may need recovery attention.
        </p>
      )}
      {actionButtons}
      <CollapsibleSubsection
        title="Redemption attempts"
        count={redemptions.length}
        defaultOpen
        testId="redemption-attempts-collapsible"
      >
        <ul className="space-y-2" data-testid="pilot-redemption-attempts-list">
          {redemptions.map((r) => (
            <RedemptionRow
              key={r.redemption_id || r.checkout_session_id}
              redemption={r}
              inviteCode={inviteCode}
              onReload={onReload}
              allowRetryApi={allowRetryApi}
              resetIncompleteApi={resetIncompleteApi}
              onAllowRetry={openAllowRetry}
              onResetIncomplete={openResetIncomplete}
              accountClientPathPrefix={accountClientPathPrefix}
            />
          ))}
          {!redemptions.length && (
            <li className="text-gray-500 text-sm">No redemption attempts recorded for this {context}.</li>
          )}
        </ul>
      </CollapsibleSubsection>
      <CollapsibleSubsection
        title="Override & waiver history"
        count={eligibilityOverrides.length}
        defaultOpen
        testId="override-history-collapsible"
      >
        <ul className="space-y-2" data-testid="pilot-eligibility-overrides-list">
          {eligibilityOverrides.map((o) => (
            <OverrideHistoryRow
              key={o.override_id}
              override={o}
              onRevoke={openRevokeOverride}
              revokingId={revokingId}
            />
          ))}
          {!eligibilityOverrides.length && (
            <li className="text-gray-500">No overrides or waivers recorded.</li>
          )}
        </ul>
        {waiverHistory.length > 0 && (
          <p className="text-[10px] text-gray-500 mt-2">
            {waiverHistory.length} onboarding waiver record(s) in history.
          </p>
        )}
      </CollapsibleSubsection>
    </>
  );

  return (
    <>
      {embedded ? (
        <div className="space-y-4" data-testid="pilot-redemption-recovery-panel">
          <p className="text-xs text-gray-600">{panelTitle}</p>
          {body}
        </div>
      ) : (
        <Card data-testid="pilot-redemption-recovery-panel">
          <CardHeader>
            <CardTitle className="text-base">{panelTitle}</CardTitle>
            <CardDescription>
              Eligibility is enforced by the backend. All actions require a reason and are audited.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">{body}</CardContent>
        </Card>
      )}

      <PilotEligibilityOverrideDialog
        open={Boolean(overrideDialog)}
        onOpenChange={(o) => !o && setOverrideDialog(null)}
        title={overrideDialog?.title}
        description={overrideDialog?.description}
        defaultOverrideType={overrideDialog?.defaultOverrideType || 'bypass_first_time'}
        defaultScope={overrideDialog?.defaultScope || 'client_id'}
        defaultScopeValue={defaultScopeValue}
        lockScope={overrideDialog?.lockScope}
        onSubmit={createOverride}
      />

      <PilotReasonDialog
        open={Boolean(reasonDialog)}
        onOpenChange={(o) => !o && setReasonDialog(null)}
        title={reasonDialog?.title || ''}
        description={reasonDialog?.description}
        confirmLabel={reasonDialog?.confirmLabel || 'Confirm'}
        destructive={reasonDialog?.destructive}
        onConfirm={async ({ reason }) => {
          if (reasonDialog?.type === 'allow_retry') {
            await allowRetryApi(reasonDialog.redemptionId, {
              reason,
              create_eligibility_override: true,
            });
          } else if (reasonDialog?.type === 'reset_incomplete') {
            await resetIncompleteApi(reasonDialog.redemptionId, { reason });
          } else if (reasonDialog?.type === 'revoke_override') {
            setRevokingId(reasonDialog.overrideId);
            try {
              await adminAPI.revokePilotEligibilityOverride(reasonDialog.overrideId);
            } finally {
              setRevokingId(null);
            }
          }
          toast.success('Recovery action completed');
          await onReload();
        }}
      />
    </>
  );
}
