import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Copy, Loader2, Ban, Save, RefreshCw, Wand2, Files } from 'lucide-react';
import { adminAPI } from '../../api/client';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { toast } from '@/utils/portalNotifications';
import { useAuth } from '../../contexts/AuthContext';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import {
  CAMPAIGN_STATE_OPTIONS,
  PILOT_PLAN_OPTIONS,
  copyToClipboard,
  formatPilotDuration,
  inviteStatusBadgeClass,
  isInternalTest,
  isPublicPromoFamily,
} from '../../utils/pilotInviteAdmin';

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-GB');
  } catch {
    return String(iso);
  }
}

export default function AdminPilotInviteDetailPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const { isAdmin, isOwner } = useAuth();
  const canManage = Boolean(isAdmin?.() || isOwner?.());

  const [invite, setInvite] = useState(null);
  const [usage, setUsage] = useState({ redemptions: [], accounts: [] });
  const [validationAttempts, setValidationAttempts] = useState([]);
  const [distribution, setDistribution] = useState(null);
  const [commercial, setCommercial] = useState(null);
  const [distPlan, setDistPlan] = useState('PLAN_1_SOLO');
  const [loading, setLoading] = useState(true);
  const [maxUses, setMaxUses] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [metrics, setMetrics] = useState(null);
  const [duplicating, setDuplicating] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const loadDistribution = useCallback(async (planCode) => {
    if (!code) return;
    const res = await adminAPI.getPilotInviteDistribution(code, { plan_code: planCode });
    setDistribution(res.data?.distribution || null);
    setCommercial(res.data?.commercial || null);
  }, [code]);

  const load = useCallback(async () => {
    if (!code) return;
    setLoading(true);
    try {
      const [invRes, useRes, attRes, metricsRes] = await Promise.all([
        adminAPI.getPilotInvite(code),
        adminAPI.getPilotInviteUsage(code),
        adminAPI.getPilotInviteValidationAttempts(code, { limit: 200 }),
        adminAPI.getPilotInviteMetrics(code),
      ]);
      const inv = invRes.data?.invite_code;
      setInvite(inv);
      setMaxUses(String(inv?.max_uses ?? 1));
      setNotes(inv?.metadata?.internal_notes || '');
      setUsage({
        redemptions: useRes.data?.redemptions || [],
        accounts: useRes.data?.accounts || [],
      });
      setValidationAttempts(attRes.data?.attempts || []);
      setMetrics(metricsRes.data?.metrics || metricsRes.data || null);
      await loadDistribution(distPlan);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load invite');
    } finally {
      setLoading(false);
    }
  }, [code, distPlan, loadDistribution]);

  useEffect(() => {
    if (canManage) load();
  }, [canManage, load]);

  useEffect(() => {
    if (canManage && code) loadDistribution(distPlan);
  }, [distPlan, canManage, code, loadDistribution]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await adminAPI.updatePilotInvite(code, {
        max_uses: Number(maxUses) || 1,
        metadata: { ...(invite?.metadata || {}), internal_notes: notes },
      });
      toast.success('Invite updated');
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  const handleDisable = async () => {
    if (!window.confirm('Disable this invite? Existing subscriptions are not affected.')) return;
    try {
      await adminAPI.disablePilotInvite(code);
      toast.success('Invite disabled');
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Disable failed');
    }
  };

  const handleDuplicate = async () => {
    if (!window.confirm('Duplicate this campaign with a new generated code?')) return;
    setDuplicating(true);
    try {
      const res = await adminAPI.duplicatePilotInvite(code);
      const newCode = res.data?.invite_code?.code;
      toast.success(newCode ? `Duplicated as ${newCode}` : 'Campaign duplicated');
      if (newCode) navigate(`/admin/pilot-invites/${encodeURIComponent(newCode)}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Duplicate failed');
    } finally {
      setDuplicating(false);
    }
  };

  const handleRegenerate = async () => {
    if (!window.confirm('Replace this code with a new one? Only allowed when unused.')) return;
    setRegenerating(true);
    try {
      const res = await adminAPI.regeneratePilotInviteCode(code);
      const newCode = res.data?.invite_code?.code;
      toast.success(newCode ? `Regenerated as ${newCode}` : 'Code regenerated');
      if (newCode && newCode !== code) {
        navigate(`/admin/pilot-invites/${encodeURIComponent(newCode)}`, { replace: true });
      } else {
        await load();
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Regenerate failed');
    } finally {
      setRegenerating(false);
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
          <Loader2 className="h-5 w-5 animate-spin" /> Loading invite…
        </div>
      </UnifiedAdminLayout>
    );
  }

  if (!invite) {
    return (
      <UnifiedAdminLayout>
        <div className="p-6">
          <Alert variant="destructive">
            <AlertDescription>Invite not found.</AlertDescription>
          </Alert>
          <Button variant="link" asChild className="mt-4">
            <Link to="/admin/pilot-invites">Back to invites</Link>
          </Button>
        </div>
      </UnifiedAdminLayout>
    );
  }

  return (
    <UnifiedAdminLayout>
    <div className="p-6 max-w-5xl mx-auto space-y-6" data-testid="pilot-invite-detail">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/admin/pilot-invites">
            <ArrowLeft className="h-4 w-4 mr-1" /> Back
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-semibold font-mono">{invite.code}</h1>
          <p className="text-sm text-gray-600">{formatPilotDuration(invite)}</p>
        </div>
        <span
          className={`ml-auto px-2 py-1 rounded text-xs ${inviteStatusBadgeClass(
            invite.effective_status || invite.status,
          )}`}
        >
          {invite.effective_status || invite.status}
        </span>
      </div>

      {metrics && (
        <Card data-testid="pilot-invite-metrics">
          <CardHeader>
            <CardTitle className="text-base">Operational metrics</CardTitle>
          </CardHeader>
          <CardContent className="grid sm:grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div>
              <span className="text-gray-500 block text-xs">Redemption rate</span>
              <span className="font-medium">{Math.round((metrics.redemption_rate || 0) * 100)}%</span>
            </div>
            <div>
              <span className="text-gray-500 block text-xs">Failed validations</span>
              <span className="font-medium">{metrics.validation_failed_count ?? 0}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-xs">Abuse attempts</span>
              <span className="font-medium">{metrics.abuse_attempt_count ?? 0}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-xs">Remaining uses</span>
              <span className="font-medium">{metrics.remaining_uses ?? 0}</span>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Stripe &amp; policy</CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-2">
            <p>
              <span className="text-gray-500">Coupon:</span>{' '}
              <span className="font-mono">{invite.stripe_coupon_id || '—'}</span>
            </p>
            <p>
              <span className="text-gray-500">Promotion:</span>{' '}
              <span className="font-mono">{invite.stripe_promotion_code_id || '—'}</span>
            </p>
            <p>
              <span className="text-gray-500">Type:</span> {invite.code_type || 'private_invite'}
              {isInternalTest(invite.code_type) && (
                <span className="ml-2 px-2 py-0.5 rounded bg-purple-100 text-purple-800 text-xs">
                  internal test
                </span>
              )}
            </p>
            <p>
              <span className="text-gray-500">Campaign:</span> {invite.campaign_name || '—'} (
              {invite.campaign_state || invite.campaign_status || '—'}, v{invite.campaign_config_version || 1})
            </p>
            <p>
              <span className="text-gray-500">Visibility:</span> {invite.launch_visibility || 'private'} · analytics:{' '}
              {invite.analytics_family || invite.code_type || 'private_invite'}
            </p>
            <p>
              <span className="text-gray-500">Public entry:</span>{' '}
              {invite.public_entry_enabled ? 'enabled' : 'disabled'}
              {invite.is_publicly_enterable ? ' · manual entry allowed' : ' · link/manual governed'}
            </p>
            {invite.campaign_mutation_applies_to && (
              <p className="text-amber-700">
                Campaign config changed for future redemptions only; existing redeemed account snapshots are preserved.
              </p>
            )}
            <p>
              <span className="text-gray-500">Onboarding:</span> {invite.onboarding_fee_policy}
            </p>
            <p>
              <span className="text-gray-500">Uses:</span> {invite.used_count ?? 0} / {invite.max_uses} (
              {invite.remaining_uses ?? 0} remaining)
            </p>
            <p>
              <span className="text-gray-500">Expires:</span> {formatDate(invite.expires_at)}
            </p>
            <p>
              <span className="text-gray-500">Created:</span> {formatDate(invite.created_at)} by{' '}
              {invite.created_by || '—'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Commercial summary</CardTitle>
            <CardDescription>From central commercial truth (plan-specific).</CardDescription>
          </CardHeader>
          <CardContent>
            <select
              className="border rounded px-2 py-1 text-sm mb-3 w-full"
              value={distPlan}
              onChange={(e) => setDistPlan(e.target.value)}
            >
              {PILOT_PLAN_OPTIONS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
            <p className="text-sm" data-testid="commercial-summary">
              {commercial?.commercial_summary || distribution?.commercial_summary || '—'}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card data-testid="pilot-invite-distribution">
        <CardHeader>
          <CardTitle className="text-base">Distribution</CardTitle>
          <CardDescription>Shareable link and message — wording from commercial truth.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div>
            <span className="text-gray-500 block text-xs mb-1">Code only</span>
            <div className="flex gap-2 mb-3">
              <Input readOnly value={invite?.code || code || ''} className="font-mono text-xs" />
              <Button
                type="button"
                variant="outline"
                onClick={async () => {
                  await copyToClipboard(invite?.code || code);
                  toast.success('Code copied');
                }}
                data-testid="pilot-invite-copy-code"
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div>
            <span className="text-gray-500 block text-xs mb-1">Invite URL</span>
            <div className="flex gap-2">
              <Input readOnly value={distribution?.invite_url || ''} className="font-mono text-xs" />
              <Button
                type="button"
                variant="outline"
                onClick={async () => {
                  await copyToClipboard(distribution?.invite_url);
                  toast.success('URL copied');
                }}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div>
            <span className="text-gray-500 block text-xs mb-1">Message template</span>
            <textarea
              readOnly
              className="w-full border rounded p-2 text-xs min-h-[120px] font-sans"
              value={distribution?.message_template || ''}
            />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="mt-2"
              onClick={async () => {
                await copyToClipboard(distribution?.copy_block || distribution?.message_template);
                toast.success('Message copied');
              }}
            >
              <Copy className="h-3 w-3 mr-1" /> Copy message
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Manage</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="block text-sm">
            Max uses
            <Input
              type="number"
              min={1}
              className="mt-1 w-32"
              value={maxUses}
              onChange={(e) => setMaxUses(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            Internal notes
            <Input className="mt-1" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
          {(isPublicPromoFamily(invite.code_type) || isInternalTest(invite.code_type)) && (
            <div className="space-y-3 border-t pt-3">
              <p className="text-xs font-medium text-gray-600">Campaign visibility</p>
              {isInternalTest(invite.code_type) ? (
                <p className="text-xs text-purple-800 bg-purple-50 rounded p-2">
                  Internal test campaigns are link-controlled, hidden from public entry, capped server-side, and excluded
                  from public analytics.
                </p>
              ) : (
                <>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={Boolean(invite.public_entry_enabled)}
                      onChange={async (e) => {
                        try {
                          await adminAPI.updatePilotInvite(code, { public_entry_enabled: e.target.checked });
                          toast.success(e.target.checked ? 'Public entry enabled' : 'Public entry disabled');
                          await load();
                        } catch (err) {
                          toast.error(err.response?.data?.detail || 'Update failed');
                        }
                      }}
                    />
                    Public entry enabled
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={Boolean(invite.is_publicly_enterable)}
                      onChange={async (e) => {
                        try {
                          await adminAPI.updatePilotInvite(code, { is_publicly_enterable: e.target.checked });
                          toast.success('Manual entry setting updated');
                          await load();
                        } catch (err) {
                          toast.error(err.response?.data?.detail || 'Update failed');
                        }
                      }}
                    />
                    Allow manual code entry
                  </label>
                </>
              )}
              <label className="block text-sm">
                Campaign state
                <select
                  className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm"
                  value={invite.campaign_state || 'draft'}
                  onChange={async (e) => {
                    try {
                      await adminAPI.updatePilotInvite(code, { campaign_state: e.target.value });
                      toast.success('Campaign state updated');
                      await load();
                    } catch (err) {
                      toast.error(err.response?.data?.detail || 'Update failed');
                    }
                  }}
                >
                  {CAMPAIGN_STATE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
              Save
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={handleRegenerate}
              disabled={regenerating || (invite?.used_count ?? 0) > 0}
              data-testid="pilot-invite-detail-regenerate"
            >
              {regenerating ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              Regenerate code
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={handleDuplicate}
              disabled={duplicating}
              data-testid="pilot-invite-detail-duplicate"
            >
              {duplicating ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Files className="h-4 w-4 mr-2" />
              )}
              Duplicate campaign
            </Button>
            <Button variant="destructive" onClick={handleDisable}>
              <Ban className="h-4 w-4 mr-2" /> Deactivate
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Usage</CardTitle>
        </CardHeader>
        <CardContent>
          <h3 className="text-sm font-medium mb-2">Accounts ({usage.accounts?.length || 0})</h3>
          <ul className="text-sm space-y-1 mb-4">
            {(usage.accounts || []).map((a) => (
              <li key={a.client_id}>
                <Link className="text-teal-700 hover:underline" to={`/admin/clients/${a.client_id}`}>
                  {a.full_name || a.email || a.client_id}
                </Link>
                <span className="text-gray-500 text-xs ml-2">{a.pilot_status || a.pilot_governance_status}</span>
              </li>
            ))}
            {!usage.accounts?.length && <li className="text-gray-500">No accounts yet.</li>}
          </ul>
          <h3 className="text-sm font-medium mb-2">Redemptions</h3>
          <ul className="text-xs text-gray-600 space-y-1">
            {(usage.redemptions || []).map((r) => (
              <li key={r.redemption_id || r.checkout_session_id}>
                {r.status} · {formatDate(r.created_at)} · session {r.checkout_session_id?.slice(0, 12)}…
              </li>
            ))}
            {!usage.redemptions?.length && <li>No redemptions recorded.</li>}
          </ul>
        </CardContent>
      </Card>

      <Card data-testid="pilot-invite-validation-attempts">
        <CardHeader>
          <CardTitle className="text-base">Validation attempts</CardTitle>
          <CardDescription>Failed and successful code checks (intake / checkout).</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="text-xs text-gray-600 space-y-1 max-h-64 overflow-y-auto">
            {validationAttempts.map((a) => (
              <li key={a.attempt_id || `${a.created_at}-${a.outcome}`}>
                <span className={a.outcome === 'success' ? 'text-emerald-700' : 'text-red-700'}>
                  {a.outcome}
                </span>
                {a.reason_code ? ` · ${a.reason_code}` : ''} · {a.entry_channel || 'manual'} ·{' '}
                {formatDate(a.created_at)}
                {a.email ? ` · ${a.email}` : ''}
              </li>
            ))}
            {!validationAttempts.length && <li className="text-gray-500">No validation attempts recorded.</li>}
          </ul>
        </CardContent>
      </Card>
    </div>
    </UnifiedAdminLayout>
  );
}
