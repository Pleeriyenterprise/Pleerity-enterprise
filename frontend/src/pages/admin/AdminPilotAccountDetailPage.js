import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  RefreshCw,
  Loader2,
  Wrench,
  CreditCard,
  Ban,
  Clock,
  Pause,
  Play,
  Gift,
  CheckCircle,
  FileEdit,
} from 'lucide-react';
import { adminAPI } from '../../api/client';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { toast } from '@/utils/portalNotifications';
import { useAuth } from '../../contexts/AuthContext';
import PilotReasonDialog from '../../components/admin/pilot/PilotReasonDialog';
import {
  apiErrorMessage,
  formatTimelineEvent,
  healthBandClass,
  severityClass,
} from '../../utils/pilotOperationsAdmin';

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-GB');
  } catch {
    return String(iso);
  }
}

export default function AdminPilotAccountDetailPage() {
  const { clientId } = useParams();
  const { isAdmin, isOwner } = useAuth();
  const canManage = Boolean(isAdmin?.() || isOwner?.());
  const isOwnerRole = Boolean(isOwner?.());

  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [dialog, setDialog] = useState(null);

  const load = useCallback(async () => {
    if (!clientId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await adminAPI.getPilotLifecycleOperationalProfile(clientId);
      setProfile(res.data);
    } catch (e) {
      setError(apiErrorMessage(e, 'Failed to load operational profile'));
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    if (canManage) load();
  }, [canManage, load]);

  const timeline = useMemo(() => {
    const events = (profile?.timeline || []).map(formatTimelineEvent);
    return events.sort((a, b) => {
      const ta = new Date(a.timestamp || 0).getTime();
      const tb = new Date(b.timestamp || 0).getTime();
      return tb - ta;
    });
  }, [profile]);

  const ops = profile?.ops || {};
  const pilot = profile?.pilot || {};
  const risk = profile?.pilot?.pilot_conversion_risk || ops?.conversion_readiness || {};
  const redeemedSnapshot = profile?.redeemed_campaign_snapshot || pilot?.pilot_redeemed_campaign_snapshot || {};
  const accountOverrides = profile?.account_overrides || [];

  const runRecovery = async (label, fn) => {
    setActionBusy(true);
    try {
      await fn();
      toast.success(label);
      await load();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setActionBusy(false);
    }
  };

  if (!canManage) {
    return (
      <UnifiedAdminLayout>
        <div className="p-6">
          <Alert>
            <AlertDescription>Owner or admin access required.</AlertDescription>
          </Alert>
        </div>
      </UnifiedAdminLayout>
    );
  }

  if (loading) {
    return (
      <UnifiedAdminLayout>
        <div className="p-6 flex items-center gap-2 text-gray-600">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading operational profile…
        </div>
      </UnifiedAdminLayout>
    );
  }

  if (error || !profile) {
    return (
      <UnifiedAdminLayout>
        <div className="p-6">
          <Alert variant="destructive">
            <AlertDescription>{error || 'Not found'}</AlertDescription>
          </Alert>
          <Button variant="link" asChild className="mt-4">
            <Link to="/admin/pilot-operations">Back to operations</Link>
          </Button>
        </div>
      </UnifiedAdminLayout>
    );
  }

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-5xl mx-auto space-y-6" data-testid="pilot-account-detail">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/admin/pilot-operations">
              <ArrowLeft className="h-4 w-4 mr-1" /> Operations
            </Link>
          </Button>
          <div className="flex-1">
            <h1 className="text-xl font-semibold">{clientId}</h1>
            <p className="text-sm text-gray-600">
              Invite: {pilot.pilot_invite_code || '—'} · Plan: {profile.billing_plan || pilot.billing_plan || '—'}
            </p>
          </div>
          <span className={`px-2 py-1 rounded text-xs ${healthBandClass(ops.pilot_health_band)}`}>
            {ops.pilot_health_band || '—'}
            {ops.pilot_health_score != null ? ` (${ops.pilot_health_score})` : ''}
          </span>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Lifecycle summary</CardTitle>
          </CardHeader>
          <CardContent className="grid sm:grid-cols-2 gap-3 text-sm">
            <p>Program: {pilot.pilot_program_type || '—'}</p>
            <p>Started: {formatDate(pilot.pilot_started_at)}</p>
            <p>Effective expiry: {formatDate(profile.effective_expires_at || ops.effective_expires_at)}</p>
            <p>Expired by date: {profile.is_expired_by_date ? 'Yes' : 'No'}</p>
            <p>Extensions: {pilot.pilot_extension_count ?? 0}</p>
            <p>Manual override: {ops.pilot_manually_overridden ? 'Yes' : 'No'}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Lifecycle domains</CardTitle>
            <CardDescription>Stripe → billing · Platform → governance · Entitlement engine → access</CardDescription>
          </CardHeader>
          <CardContent className="grid sm:grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-xs text-gray-500 uppercase">Governance</p>
              <p className="font-medium">{ops.pilot_governance_status || pilot.pilot_status}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Billing</p>
              <p className="font-medium">{ops.pilot_billing_status || '—'}</p>
              <p className="text-xs text-gray-500">Stripe: {ops.stripe_subscription_status || '—'}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Entitlement</p>
              <p className="font-medium">{ops.pilot_entitlement_status || '—'}</p>
            </div>
          </CardContent>
        </Card>

        <div className="grid md:grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Conversion readiness</CardTitle>
            </CardHeader>
            <CardContent className="text-sm space-y-1">
              <p>Days remaining: {ops.days_remaining ?? '—'}</p>
              <p>Expected paid: {formatDate(pilot.pilot_expected_first_paid_invoice_at)}</p>
              <p>Payment method: {ops.payment_method_collected ? 'Collected' : 'Missing'}</p>
              <p>Likely conversion: {risk.likely_conversion || ops.conversion_readiness?.likely_conversion ? 'Yes' : 'No'}</p>
              <p>Approaching paid transition: {risk.approaching_paid_transition ? 'Yes' : 'No'}</p>
              <p>Churn risk: {risk.likely_churn || ops.cancellation_risk ? 'Yes' : 'No'}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Onboarding fee</CardTitle>
            </CardHeader>
            <CardContent className="text-sm space-y-1">
              <p>Policy: {profile.onboarding_fee?.onboarding_fee_policy || pilot.onboarding_fee_policy || '—'}</p>
              <p>Waived: {profile.onboarding_fee?.onboarding_fee_waived ? 'Yes' : 'No'}</p>
              <p>First paid invoice: {ops.first_paid_invoice_paid ? 'Yes' : 'No'}</p>
              {ops.pilot_health_flags?.length > 0 && (
                <ul className="list-disc ml-4 mt-2 text-xs text-amber-800">
                  {ops.pilot_health_flags.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Commercial summary</CardTitle>
            </CardHeader>
            <CardContent className="text-sm space-y-1">
              <p>Discount: {pilot.pilot_discount_percent != null ? `${pilot.pilot_discount_percent}%` : '—'}</p>
              <p>Source: {pilot.pilot_discount_source || '—'}</p>
              <p>Duration: {pilot.pilot_duration_months != null ? `${pilot.pilot_duration_months} months` : '—'}</p>
              <p>Invite code: {pilot.pilot_invite_code || '—'}</p>
              <p>Analytics family: {ops.pilot_analytics_family || pilot.pilot_analytics_family || '—'}</p>
              <p>Campaign version: {ops.pilot_campaign_config_version || pilot.pilot_campaign_config_version || '—'}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Stripe linkage</CardTitle>
            </CardHeader>
            <CardContent className="text-sm space-y-1">
              <p>Subscription status: {ops.stripe_subscription_status || '—'}</p>
              <p>Payment method collected: {pilot.pilot_stripe_payment_method_collected ? 'Yes' : 'No'}</p>
              <p>Default PM: {pilot.pilot_stripe_default_payment_method_id || '—'}</p>
              <p>First paid invoice: {pilot.pilot_first_paid_invoice_paid ? 'Yes' : 'No'}</p>
            </CardContent>
          </Card>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <Card data-testid="pilot-redeemed-campaign-snapshot">
            <CardHeader>
              <CardTitle className="text-base">Redeemed campaign snapshot</CardTitle>
              <CardDescription>Immutable campaign truth captured at redemption.</CardDescription>
            </CardHeader>
            <CardContent className="text-sm space-y-1">
              <p>Code: {redeemedSnapshot.redeemed_code || pilot.pilot_invite_code || '—'}</p>
              <p>Type: {redeemedSnapshot.code_type || pilot.pilot_code_type || '—'}</p>
              <p>Campaign: {redeemedSnapshot.campaign_name || '—'}</p>
              <p>Version: {redeemedSnapshot.campaign_config_version || '—'}</p>
              <p>Visibility: {redeemedSnapshot.launch_visibility || pilot.pilot_launch_visibility || '—'}</p>
              <p>Redeemed: {formatDate(redeemedSnapshot.redeemed_at || redeemedSnapshot.completed_at)}</p>
            </CardContent>
          </Card>
          <Card data-testid="pilot-account-overrides">
            <CardHeader>
              <CardTitle className="text-base">Account overrides</CardTitle>
              <CardDescription>Account-level changes independent of campaign defaults.</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-xs">
                {accountOverrides.map((o) => (
                  <li key={o.override_id} className="border rounded p-2">
                    <p className="font-medium">
                      {o.override_type} · {formatDate(o.created_at)}
                    </p>
                    <p className="text-gray-600">
                      Expiry: {formatDate(o.before_effective_expiry)} → {formatDate(o.after_effective_expiry)}
                    </p>
                    {o.reason && <p>{o.reason}</p>}
                  </li>
                ))}
                {!accountOverrides.length && <li className="text-gray-500">No account overrides recorded.</li>}
              </ul>
            </CardContent>
          </Card>
        </div>

        <Card data-testid="open-anomalies">
          <CardHeader>
            <CardTitle className="text-base">Open anomalies ({(profile.open_anomalies || []).length})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {(profile.open_anomalies || []).length === 0 ? (
              <p className="text-sm text-gray-500">No open anomalies.</p>
            ) : (
              profile.open_anomalies.map((a) => (
                <div key={a.anomaly_id} className="border rounded p-3 text-sm flex justify-between gap-2">
                  <div>
                    <span className={`px-2 py-0.5 rounded text-xs ${severityClass(a.severity)}`}>{a.severity}</span>
                    <span className="ml-2 font-mono text-xs">{a.anomaly_code}</span>
                    <p className="text-xs text-gray-600 mt-1">{a.message}</p>
                    <p className="text-xs text-gray-400">Detected {formatDate(a.detected_at)}</p>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      setDialog({
                        type: 'resolve_anomaly',
                        anomalyId: a.anomaly_id,
                        title: 'Resolve anomaly',
                        description: a.anomaly_code,
                      })
                    }
                  >
                    Resolve
                  </Button>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recovery &amp; sync tools</CardTitle>
            <CardDescription>Operational actions — backend authoritative</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={actionBusy}
              onClick={() => runRecovery('Reconciliation complete', () => adminAPI.reconcilePilotLifecycleAccount(clientId))}
            >
              <Wrench className="h-4 w-4 mr-1" /> Reconcile
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={actionBusy}
              onClick={() =>
                runRecovery('Payment method synced', () => adminAPI.syncPilotStripePaymentMethod(clientId))
              }
            >
              <CreditCard className="h-4 w-4 mr-1" /> Sync Stripe PM
            </Button>
            <Button variant="outline" size="sm" onClick={load} disabled={actionBusy}>
              <RefreshCw className="h-4 w-4 mr-1" /> Refresh profile
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Governance actions</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => setDialog({ type: 'extend', title: 'Extend pilot' })}>
              <Clock className="h-4 w-4 mr-1" /> Extend
            </Button>
            <Button size="sm" variant="outline" onClick={() => setDialog({ type: 'set_expiry', title: 'Set expiry' })}>
              Set expiry
            </Button>
            <Button size="sm" variant="outline" onClick={() => setDialog({ type: 'pause', title: 'Pause pilot' })}>
              <Pause className="h-4 w-4 mr-1" /> Pause
            </Button>
            <Button size="sm" variant="outline" onClick={() => setDialog({ type: 'resume', title: 'Resume pilot' })}>
              <Play className="h-4 w-4 mr-1" /> Resume
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setDialog({ type: 'onboarding_fee', title: 'Update onboarding fee policy' })}
            >
              <FileEdit className="h-4 w-4 mr-1" /> Onboarding fee
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setDialog({ type: 'convert', title: 'Mark converted to paid' })}
            >
              <CheckCircle className="h-4 w-4 mr-1" /> Convert
            </Button>
            {isOwnerRole && (
              <Button size="sm" variant="outline" onClick={() => setDialog({ type: 'comp', title: 'Comp account' })}>
                <Gift className="h-4 w-4 mr-1" /> Comp
              </Button>
            )}
            <Button
              size="sm"
              variant="destructive"
              onClick={() => setDialog({ type: 'cancel', title: 'Cancel pilot', destructive: true })}
            >
              <Ban className="h-4 w-4 mr-1" /> Cancel
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Timeline</CardTitle>
            <CardDescription>Audit trail (newest first)</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {timeline.map((ev) => (
                <li key={ev.id} className="border-l-2 border-slate-200 pl-3 text-sm">
                  <div className="flex justify-between gap-2">
                    <span className="font-medium">{ev.label}</span>
                    <span className="text-xs text-gray-500 shrink-0">{formatDate(ev.timestamp)}</span>
                  </div>
                  <p className="text-xs text-gray-500">
                    {ev.category} · {ev.actor?.type || 'system'}
                    {ev.actor?.email ? ` (${ev.actor.email})` : ''}
                  </p>
                  {ev.reason && <p className="text-xs mt-1">{ev.reason}</p>}
                </li>
              ))}
              {!timeline.length && <p className="text-gray-500 text-sm">No timeline events.</p>}
            </ul>
          </CardContent>
        </Card>

        <PilotReasonDialog
          open={Boolean(dialog)}
          onOpenChange={(o) => !o && setDialog(null)}
          title={dialog?.title || ''}
          description={dialog?.description}
          destructive={dialog?.destructive}
          minReasonLength={dialog?.type === 'comp' ? 10 : 3}
          extraFields={
            dialog?.type === 'extend'
              ? ({ extra, setExtra }) => (
                  <div className="space-y-2">
                    <label className="block text-sm">
                      Extension mode
                      <select
                        className="mt-1 w-full border rounded px-2 py-1 text-sm"
                        value={extra.mode || 'months'}
                        onChange={(e) => setExtra({ mode: e.target.value })}
                      >
                        <option value="days">Days</option>
                        <option value="weeks">Weeks</option>
                        <option value="months">Months</option>
                        <option value="until">Until date</option>
                      </select>
                    </label>
                    {extra.mode === 'until' ? (
                      <label className="block text-sm">
                        Extend until
                        <Input
                          type="datetime-local"
                          className="mt-1"
                          onChange={(e) => setExtra({ mode: 'until', until: e.target.value })}
                        />
                      </label>
                    ) : (
                      <label className="block text-sm">
                        Amount
                        <Input
                          type="number"
                          min={1}
                          className="mt-1 w-24"
                          value={extra.amount || extra.months || 1}
                          onChange={(e) => setExtra({ mode: extra.mode || 'months', amount: Number(e.target.value) })}
                        />
                      </label>
                    )}
                  </div>
                )
              : dialog?.type === 'set_expiry'
                ? ({ extra, setExtra }) => (
                    <label className="block text-sm">
                      Expires at (local)
                      <Input
                        type="datetime-local"
                        className="mt-1"
                        onChange={(e) => setExtra({ expires_at: e.target.value })}
                      />
                    </label>
                  )
                : dialog?.type === 'cancel'
                  ? ({ extra, setExtra }) => (
                      <label className="flex items-center gap-2 text-xs mt-2">
                        <input
                          type="checkbox"
                          onChange={(e) => setExtra({ cancel_stripe: e.target.checked })}
                        />
                        Cancel Stripe subscription
                      </label>
                    )
                  : dialog?.type === 'onboarding_fee'
                    ? ({ extra, setExtra }) => (
                        <label className="block text-sm">
                          Policy
                          <select
                            className="mt-1 w-full border rounded px-2 py-1 text-sm"
                            value={extra.onboarding_fee_policy || 'waived'}
                            onChange={(e) => setExtra({ onboarding_fee_policy: e.target.value })}
                          >
                            <option value="waived">waived</option>
                            <option value="deferred">deferred</option>
                            <option value="charge_now">charge_now</option>
                            <option value="discount">discount</option>
                          </select>
                        </label>
                      )
                    : null
          }
          onConfirm={async ({ reason, ...extra }) => {
            const t = dialog?.type;
            if (t === 'resolve_anomaly') {
              await adminAPI.resolvePilotLifecycleAnomaly(dialog.anomalyId, { resolution_notes: reason });
            } else if (t === 'extend') {
              const mode = extra.mode || 'months';
              const amount = Number(extra.amount || extra.months || 1);
              if (mode === 'until' && !extra.until) throw new Error('Extension end datetime required');
              const body =
                mode === 'until'
                  ? { reason, until: new Date(extra.until).toISOString() }
                  : { reason, [mode]: amount };
              await adminAPI.extendPilotAccount(clientId, body);
            } else if (t === 'set_expiry') {
              if (!extra.expires_at) throw new Error('Expiry datetime required');
              await adminAPI.setPilotExpiry(clientId, {
                reason,
                expires_at: new Date(extra.expires_at).toISOString(),
              });
            } else if (t === 'convert') {
              await adminAPI.convertPilotAccount(clientId, { reason });
            } else if (t === 'comp') {
              await adminAPI.compPilotAccount(clientId, { reason, notes: reason });
            } else if (t === 'cancel') {
              await adminAPI.cancelPilotAccount(clientId, {
                reason,
                cancel_stripe_subscription: Boolean(extra.cancel_stripe),
                revoke_access_immediately: false,
              });
            } else if (t === 'pause') {
              await adminAPI.pausePilotAccount(clientId, { reason });
            } else if (t === 'resume') {
              await adminAPI.resumePilotAccount(clientId, { reason });
            } else if (t === 'onboarding_fee') {
              await adminAPI.setPilotOnboardingFeePolicy(clientId, {
                reason,
                onboarding_fee_policy: extra.onboarding_fee_policy || 'waived',
              });
            }
            toast.success('Action completed');
            await load();
          }}
        />
      </div>
    </UnifiedAdminLayout>
  );
}
