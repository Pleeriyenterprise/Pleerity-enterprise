import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Plus, ShieldOff } from 'lucide-react';
import { adminAPI } from '../../../api/client';
import { Button } from '../../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../ui/card';
import { toast } from '@/utils/portalNotifications';
import PilotEligibilityOverrideDialog from './PilotEligibilityOverrideDialog';
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

function RedemptionRow({
  redemption,
  inviteCode,
  onReload,
  allowRetryApi,
  resetIncompleteApi,
  accountClientPathPrefix = '/admin/pilot-operations/accounts',
}) {
  const [busy, setBusy] = useState(null);

  const run = async (action, fn) => {
    setBusy(action);
    try {
      await fn();
      toast.success('Recovery action completed');
      await onReload();
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message || 'Action failed');
    } finally {
      setBusy(null);
    }
  };

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
              onClick={() => {
                const reason = window.prompt('Reason for allowing retry (required, min 3 chars):');
                if (!reason || reason.trim().length < 3) {
                  if (reason != null) toast.error('Reason must be at least 3 characters');
                  return;
                }
                run('retry', () =>
                  allowRetryApi(redemption.redemption_id, {
                    reason: reason.trim(),
                    create_eligibility_override: true,
                  }),
                );
              }}
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
              onClick={() => {
                const reason = window.prompt('Reason for resetting incomplete redemption (required):');
                if (!reason || reason.trim().length < 3) {
                  if (reason != null) toast.error('Reason must be at least 3 characters');
                  return;
                }
                run('reset', () => resetIncompleteApi(redemption.redemption_id, { reason: reason.trim() }));
              }}
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
          Failure: {redemption.failure_reason}
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
      {redemption.client_id && (
        <p>
          Account:{' '}
          <Link
            className="text-teal-700 hover:underline"
            to={`${accountClientPathPrefix}/${redemption.client_id}`}
          >
            {redemption.client_id}
          </Link>
        </p>
      )}
    </li>
  );
}

/**
 * Promo / invite redemption recovery panel (account or invite context).
 */
export default function PilotRedemptionRecoverySection({
  context = 'account',
  clientId,
  inviteCode,
  inviteCodeId,
  redemptions = [],
  eligibilityOverrides = [],
  loading = false,
  onReload,
  defaultEmail,
  strandedCount = 0,
}) {
  const [overrideDialog, setOverrideDialog] = useState(null);
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
    toast.success('Eligibility override granted');
    await onReload();
  };

  const revokeOverride = async (overrideId) => {
    const reason = window.prompt('Reason for revoking override (required):');
    if (!reason || reason.trim().length < 3) {
      if (reason != null) toast.error('Reason must be at least 3 characters');
      return;
    }
    setRevokingId(overrideId);
    try {
      await adminAPI.revokePilotEligibilityOverride(overrideId);
      toast.success('Override revoked');
      await onReload();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Revoke failed');
    } finally {
      setRevokingId(null);
    }
  };

  const defaultScopeValue =
    overrideDialog?.defaultScope === 'email'
      ? defaultEmail || ''
      : overrideDialog?.defaultScope === 'invite_code_id'
        ? inviteCodeId || ''
        : clientId || '';

  return (
    <>
      <Card data-testid="pilot-redemption-recovery-panel">
        <CardHeader>
          <CardTitle className="text-base">Promo / Invite Redemption</CardTitle>
          <CardDescription>
            Failed or incomplete redemption attempts and eligibility overrides. Eligibility is enforced by the
            backend — actions here call admin APIs only.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? (
            <p className="text-sm text-gray-500 flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading redemption data…
            </p>
          ) : (
            <>
              {strandedCount > 0 && (
                <p className="text-sm text-amber-800" data-testid="stranded-redemptions-hint">
                  {strandedCount} redemption(s) may need recovery attention.
                </p>
              )}
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
                        'Allows this existing user to use a promo despite first-time restriction. Does not change campaign rules globally.',
                      defaultOverrideType: 'bypass_first_time',
                      defaultScope:
                        context === 'invite' ? 'email' : defaultEmail ? 'email' : 'client_id',
                      lockScope: context === 'account' && Boolean(clientId || defaultEmail),
                    })
                  }
                >
                  <ShieldOff className="h-3 w-3 mr-1" />
                  Grant promo eligibility
                </Button>
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
                  onClick={() =>
                    setOverrideDialog({
                      title: 'Recover onboarding',
                      defaultOverrideType: 'recover_onboarding',
                      defaultScope: 'client_id',
                    })
                  }
                >
                  Recover onboarding
                </Button>
              </div>

              <h3 className="text-sm font-medium" data-testid="redemption-attempts-heading">
                Redemption attempts ({redemptions.length})
              </h3>
              <ul className="space-y-2" data-testid="pilot-redemption-attempts-list">
                {redemptions.map((r) => (
                  <RedemptionRow
                    key={r.redemption_id || r.checkout_session_id}
                    redemption={r}
                    inviteCode={inviteCode}
                    onReload={onReload}
                    allowRetryApi={allowRetryApi}
                    resetIncompleteApi={resetIncompleteApi}
                  />
                ))}
                {!redemptions.length && (
                  <li className="text-gray-500 text-sm">No redemption attempts recorded for this {context}.</li>
                )}
              </ul>

              <h3 className="text-sm font-medium">Active eligibility overrides</h3>
              <ul className="space-y-2 text-xs" data-testid="pilot-eligibility-overrides-list">
                {eligibilityOverrides.map((o) => (
                  <li
                    key={o.override_id}
                    className={`border rounded p-2 ${isOverrideActive(o) ? 'border-emerald-100' : 'border-slate-100 opacity-70'}`}
                    data-testid={`override-row-${o.override_id}`}
                  >
                    <div className="flex flex-wrap justify-between gap-2">
                      <div>
                        <p className="font-medium">
                          {overrideTypeLabel(o.override_type)} · {o.scope}={o.scope_value}
                        </p>
                        <p className="text-gray-600 mt-0.5">{o.override_reason}</p>
                        <p className="text-gray-500 mt-0.5">
                          By {o.override_actor?.email || o.override_actor?.id || 'admin'} ·{' '}
                          {formatDate(o.override_created_at)}
                          {o.override_expires_at && <> · Expires {formatDate(o.override_expires_at)}</>}
                          {o.revoked_at && <> · Revoked {formatDate(o.revoked_at)}</>}
                        </p>
                        {o.invite_code && <p className="text-gray-500">Invite: {o.invite_code}</p>}
                      </div>
                      {isOverrideActive(o) && (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={revokingId === o.override_id}
                          data-testid={`revoke-override-${o.override_id}`}
                          onClick={() => revokeOverride(o.override_id)}
                        >
                          {revokingId === o.override_id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            'Revoke'
                          )}
                        </Button>
                      )}
                    </div>
                  </li>
                ))}
                {!eligibilityOverrides.length && (
                  <li className="text-gray-500">No eligibility overrides.</li>
                )}
              </ul>
            </>
          )}
        </CardContent>
      </Card>

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
    </>
  );
}
