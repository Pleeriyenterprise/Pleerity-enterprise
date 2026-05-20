import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Copy, Loader2, Ban, Save, RefreshCw, Wand2, Files, Send } from 'lucide-react';
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
import PilotRedemptionRecoverySection from '../../components/admin/pilot/PilotRedemptionRecoverySection';

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
  const [redemptionRows, setRedemptionRows] = useState([]);
  const [eligibilityOverrides, setEligibilityOverrides] = useState([]);
  const [allowingRetryId, setAllowingRetryId] = useState(null);
  const [duplicating, setDuplicating] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [showSendInvite, setShowSendInvite] = useState(false);
  const [sendingInvite, setSendingInvite] = useState(false);
  const [sendForm, setSendForm] = useState({
    recipient_email: '',
    recipient_name: '',
    plan_code: 'PLAN_1_SOLO',
    personal_note: '',
  });

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
      const [invRes, useRes, attRes, metricsRes, redRes, ovRes] = await Promise.all([
        adminAPI.getPilotInvite(code),
        adminAPI.getPilotInviteUsage(code),
        adminAPI.getPilotInviteValidationAttempts(code, { limit: 200 }),
        adminAPI.getPilotInviteMetrics(code),
        adminAPI.getPilotInviteRedemptions(code, { limit: 200 }),
        adminAPI.getPilotInviteEligibilityOverrides(code),
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
      setRedemptionRows(redRes.data?.redemptions || []);
      setEligibilityOverrides(ovRes.data?.overrides || []);
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

  useEffect(() => {
    setSendForm((f) => ({ ...f, plan_code: distPlan }));
  }, [distPlan]);

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

  const sendPreview = [
    sendForm.recipient_name ? `Hello ${sendForm.recipient_name},` : 'Hello,',
    '',
    distribution?.email_style_message || distribution?.message_template || '',
    sendForm.personal_note ? `\nPersonal note:\n${sendForm.personal_note}` : '',
  ].join('\n').trim();

  const handleSendInvite = async () => {
    const email = sendForm.recipient_email.trim();
    if (!email) {
      toast.error('Recipient email is required');
      return;
    }
    setSendingInvite(true);
    try {
      await adminAPI.sendPilotInvite(code, {
        recipient_email: email,
        recipient_name: sendForm.recipient_name.trim() || null,
        plan_code: sendForm.plan_code || distPlan,
        personal_note: sendForm.personal_note.trim() || null,
      });
      toast.success('Invite sent');
      setShowSendInvite(false);
      setSendForm((f) => ({ ...f, recipient_email: '', recipient_name: '', personal_note: '' }));
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Send failed');
    } finally {
      setSendingInvite(false);
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
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle className="text-base">Distribution</CardTitle>
              <CardDescription>Shareable link and message — wording from commercial truth.</CardDescription>
            </div>
            <Button
              type="button"
              size="sm"
              onClick={() => setShowSendInvite(true)}
              data-testid="pilot-invite-send-open"
            >
              <Send className="h-4 w-4 mr-2" /> Send invite
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
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
                <Copy className="h-4 w-4 mr-1" /> Copy invite link
              </Button>
            </div>
          </div>
          <div>
            <span className="text-gray-500 block text-xs mb-1">Plain message</span>
            <textarea
              readOnly
              className="w-full border rounded p-2 text-xs min-h-[120px] font-sans"
              value={distribution?.plain_message || distribution?.message_template || ''}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={async () => {
                await copyToClipboard(distribution?.plain_message || distribution?.message_template);
                toast.success('Plain message copied');
              }}
              data-testid="pilot-invite-copy-plain"
            >
              <Copy className="h-3 w-3 mr-1" /> Copy plain message
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={async () => {
                await copyToClipboard(distribution?.email_style_message || distribution?.message_template);
                toast.success('Email-style message copied');
              }}
              data-testid="pilot-invite-copy-email-style"
            >
              <Copy className="h-3 w-3 mr-1" /> Copy email-style message
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={async () => {
                await copyToClipboard(invite?.code || code);
                toast.success('Code copied');
              }}
              data-testid="pilot-invite-copy-code"
            >
              <Copy className="h-3 w-3 mr-1" /> Copy code only
            </Button>
          </div>
        </CardContent>
      </Card>

      {showSendInvite && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-5 border-b flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">Send founding pilot invite</h2>
                <p className="text-sm text-gray-600">
                  Sends a clickable CTA email. This does not reserve or consume invite usage.
                </p>
              </div>
              <Button type="button" variant="ghost" size="sm" onClick={() => setShowSendInvite(false)}>
                Close
              </Button>
            </div>
            <div className="p-5 grid md:grid-cols-2 gap-5">
              <div className="space-y-3">
                <label className="block text-sm">
                  Recipient email
                  <Input
                    className="mt-1"
                    type="email"
                    value={sendForm.recipient_email}
                    onChange={(e) => setSendForm((f) => ({ ...f, recipient_email: e.target.value }))}
                    placeholder="founder@example.com"
                  />
                </label>
                <label className="block text-sm">
                  Recipient name optional
                  <Input
                    className="mt-1"
                    value={sendForm.recipient_name}
                    onChange={(e) => setSendForm((f) => ({ ...f, recipient_name: e.target.value }))}
                    placeholder="Alex"
                  />
                </label>
                <label className="block text-sm">
                  Selected plan
                  <select
                    className="mt-1 w-full border rounded-md px-2 py-2 text-sm"
                    value={sendForm.plan_code}
                    onChange={(e) => {
                      setSendForm((f) => ({ ...f, plan_code: e.target.value }));
                      setDistPlan(e.target.value);
                    }}
                  >
                    {PILOT_PLAN_OPTIONS.map((p) => (
                      <option key={p.value} value={p.value}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm">
                  Personal note optional
                  <textarea
                    className="mt-1 w-full border rounded p-2 text-sm min-h-[100px]"
                    value={sendForm.personal_note}
                    onChange={(e) => setSendForm((f) => ({ ...f, personal_note: e.target.value }))}
                    placeholder="Short note from the team..."
                  />
                </label>
              </div>
              <div className="space-y-3">
                <div className="border rounded-lg p-4 bg-gray-50">
                  <p className="text-xs uppercase tracking-wide text-gray-500 mb-2">CTA preview</p>
                  <p className="text-sm mb-3">{commercial?.commercial_summary || distribution?.commercial_summary || '—'}</p>
                  <a
                    className="inline-block rounded bg-teal-700 text-white text-sm font-semibold px-4 py-2 no-underline"
                    href={distribution?.invite_url || '#'}
                    onClick={(e) => e.preventDefault()}
                  >
                    Start your founding pilot access
                  </a>
                  <p className="text-xs text-gray-500 mt-3 break-all">
                    Fallback raw link: {distribution?.invite_url || '—'}
                  </p>
                </div>
                <label className="block text-sm">
                  Message preview
                  <textarea
                    readOnly
                    className="mt-1 w-full border rounded p-2 text-xs min-h-[220px] font-sans"
                    value={sendPreview}
                  />
                </label>
              </div>
            </div>
            <div className="p-5 border-t flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setShowSendInvite(false)}>
                Cancel
              </Button>
              <Button type="button" onClick={handleSendInvite} disabled={sendingInvite}>
                {sendingInvite ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}
                Send invite
              </Button>
            </div>
          </div>
        </div>
      )}

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
                <Link
                  className="text-teal-700 hover:underline"
                  to={`/admin/pilot-operations/accounts/${a.client_id}`}
                >
                  {a.full_name || a.email || a.client_id}
                </Link>
                <span className="text-gray-500 text-xs ml-2">{a.pilot_status || a.pilot_governance_status}</span>
              </li>
            ))}
            {!usage.accounts?.length && <li className="text-gray-500">No accounts yet.</li>}
          </ul>
        </CardContent>
      </Card>

      <PilotRedemptionRecoverySection
        context="invite"
        inviteCode={code}
        inviteCodeId={invite?.invite_code_id}
        redemptions={redemptionRows}
        eligibilityOverrides={eligibilityOverrides}
        loading={loading}
        onReload={load}
        strandedCount={metrics?.stranded_redemptions || 0}
      />

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
