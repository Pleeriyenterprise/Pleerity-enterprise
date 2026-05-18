import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Plus,
  RefreshCw,
  Copy,
  Sparkles,
  ExternalLink,
  CheckCircle,
  XCircle,
  Loader2,
  Info,
} from 'lucide-react';
import { adminAPI } from '../../api/client';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { toast } from '@/utils/portalNotifications';
import { useAuth } from '../../contexts/AuthContext';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import {
  ONBOARDING_POLICY_OPTIONS,
  PILOT_PLAN_OPTIONS,
  buildDefaultCreateForm,
  copyToClipboard,
  filterPilotInvites,
  formToCreatePayload,
  formatPilotDuration,
  inviteStatusBadgeClass,
  normalizeInviteCode,
  stripeValidationToDisplay,
} from '../../utils/pilotInviteAdmin';

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-GB');
  } catch {
    return String(iso);
  }
}

export default function AdminPilotInvitesPage() {
  const navigate = useNavigate();
  const { isAdmin, isOwner } = useAuth();
  const canManage = Boolean(isAdmin?.() || isOwner?.());

  const [invites, setInvites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [opsConfig, setOpsConfig] = useState(null);
  const [filters, setFilters] = useState({
    status: 'all',
    onboarding_policy: '',
    duration_months: '',
    plan_code: '',
  });
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(buildDefaultCreateForm);
  const [creating, setCreating] = useState(false);
  const [validatingStripe, setValidatingStripe] = useState(false);
  const [stripeResult, setStripeResult] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [listRes, cfgRes] = await Promise.all([
        adminAPI.listPilotInvites({ limit: 500 }),
        adminAPI.getPilotInviteOperationalConfig(),
      ]);
      setInvites(listRes.data?.invite_codes || []);
      setOpsConfig(cfgRes.data || null);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Failed to load pilot invites');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (canManage) load();
  }, [canManage, load]);

  const filtered = useMemo(() => filterPilotInvites(invites, filters), [invites, filters]);

  const handleSuggestCode = async () => {
    try {
      const res = await adminAPI.suggestPilotInviteCode({
        prefix: form.code_prefix || 'FOUNDING',
        variant: form.code_variant || '',
      });
      setForm((f) => ({ ...f, code: res.data?.code || '', auto_generate: false }));
    } catch {
      toast.error('Could not generate code');
    }
  };

  const handleValidateStripe = async () => {
    setValidatingStripe(true);
    setStripeResult(null);
    try {
      const payload = formToCreatePayload(form);
      const res = await adminAPI.validatePilotInviteStripe({
        stripe_coupon_id: payload.stripe_coupon_id,
        stripe_promotion_code_id: payload.stripe_promotion_code_id,
        discount_mode: payload.discount_mode,
        discount_percent: payload.discount_percent,
        discount_duration: payload.discount_duration,
        discount_duration_in_months: payload.discount_duration_in_months,
      });
      setStripeResult(res.data);
    } catch (e) {
      const detail = e.response?.data?.detail;
      setStripeResult({
        valid: false,
        message: typeof detail === 'string' ? detail : 'Validation request failed',
        details: [],
      });
    } finally {
      setValidatingStripe(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.stripe_coupon_id?.trim() && !form.stripe_promotion_code_id?.trim()) {
      toast.error('Stripe coupon or promotion code ID is required');
      return;
    }
    let code = normalizeInviteCode(form.code);
    if (form.auto_generate && !code) {
      const sug = await adminAPI.suggestPilotInviteCode({
        prefix: form.code_prefix,
        variant: form.code_variant,
      });
      code = normalizeInviteCode(sug.data?.code);
    }
    if (!code) {
      toast.error('Invite code is required');
      return;
    }
    setCreating(true);
    try {
      const payload = { ...formToCreatePayload({ ...form, code }), code };
      const res = await adminAPI.createPilotInvite(payload);
      toast.success(`Invite ${res.data?.invite_code?.code || code} created`);
      setShowCreate(false);
      setForm(buildDefaultCreateForm());
      setStripeResult(null);
      await load();
      navigate(`/admin/pilot-invites/${encodeURIComponent(code)}`);
    } catch (e) {
      const detail = e.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Create failed');
    } finally {
      setCreating(false);
    }
  };

  const stripeDisplay = stripeValidationToDisplay(stripeResult);

  if (!canManage) {
    return (
      <UnifiedAdminLayout>
        <div className="p-6">
          <Alert>
            <AlertDescription>Owner or admin access is required to manage founding pilot invites.</AlertDescription>
          </Alert>
        </div>
      </UnifiedAdminLayout>
    );
  }

  return (
    <UnifiedAdminLayout>
    <div className="p-6 max-w-7xl mx-auto space-y-6" data-testid="admin-pilot-invites-page">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-midnight-blue">Founding Pilot Invites</h1>
          <p className="text-sm text-gray-600 mt-1">
            Create and manage invite codes, Stripe coupons, and distribution links.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={load} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={() => setShowCreate((v) => !v)} data-testid="pilot-invite-create-toggle">
            <Plus className="h-4 w-4 mr-2" />
            Create invite
          </Button>
        </div>
      </div>

      {opsConfig && (
        <Card data-testid="pilot-invite-ops-config">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2 flex-wrap">
              <Info className="h-4 w-4" />
              Stripe &amp; environment
              <span
                className={`text-xs font-semibold px-2 py-0.5 rounded ${
                  opsConfig.stripe_mode === 'live'
                    ? 'bg-red-100 text-red-900'
                    : opsConfig.stripe_mode === 'test'
                      ? 'bg-slate-200 text-slate-800'
                      : 'bg-amber-100 text-amber-900'
                }`}
                data-testid="stripe-mode-badge"
              >
                {opsConfig.mode_badge || `${opsConfig.stripe_mode} mode`}
              </span>
              {!opsConfig.mode_authoritative && (
                <span className="text-xs text-amber-700">STRIPE_MODE not set (inferred)</span>
              )}
            </CardTitle>
            <CardDescription>Required configuration — secrets are never shown here.</CardDescription>
          </CardHeader>
          <CardContent className="text-sm space-y-2">
            {(opsConfig.errors || []).length > 0 && (
              <ul className="text-xs text-red-700 space-y-1" data-testid="stripe-config-errors">
                {opsConfig.errors.map((msg) => (
                  <li key={msg}>{msg}</li>
                ))}
              </ul>
            )}
            {(opsConfig.warnings || []).length > 0 && (
              <ul className="text-xs text-amber-800 space-y-1" data-testid="stripe-config-warnings">
                {opsConfig.warnings.map((msg) => (
                  <li key={msg}>{msg}</li>
                ))}
              </ul>
            )}
            <ul className="grid sm:grid-cols-2 gap-2">
              {(opsConfig.requirements || []).map((r) => (
                <li key={r.key} className="flex items-center gap-2">
                  {r.configured ? (
                    <CheckCircle className="h-4 w-4 text-emerald-600 shrink-0" />
                  ) : (
                    <XCircle className="h-4 w-4 text-red-600 shrink-0" />
                  )}
                  <span>{r.label}</span>
                </li>
              ))}
            </ul>
            {opsConfig.frontend_alignment && (
              <p className="text-xs text-gray-600">
                Frontend alignment: {opsConfig.frontend_alignment.status} (
                {opsConfig.frontend_alignment.expected_env_var})
              </p>
            )}
            <p className="text-xs text-gray-500">
              Webhooks: {(opsConfig.webhook_paths || []).join(', ')} · Intake: ?{opsConfig.intake_invite_query_param}
              =CODE&amp;plan=PLAN
            </p>
          </CardContent>
        </Card>
      )}

      {showCreate && (
        <Card data-testid="pilot-invite-create-form">
          <CardHeader>
            <CardTitle>New founding pilot invite</CardTitle>
            <CardDescription>Stripe coupon must exist in Dashboard and match duration/percent below.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4">
                <label className="block text-sm">
                  <span className="font-medium">Invite code</span>
                  <div className="flex gap-2 mt-1">
                    <Input
                      value={form.code}
                      onChange={(e) => setForm((f) => ({ ...f, code: e.target.value, auto_generate: false }))}
                      placeholder="FOUNDING-2026-AB12"
                      disabled={form.auto_generate}
                      data-testid="pilot-invite-code-input"
                    />
                    <Button type="button" variant="outline" onClick={handleSuggestCode}>
                      <Sparkles className="h-4 w-4" />
                    </Button>
                  </div>
                  <label className="flex items-center gap-2 mt-2 text-xs">
                    <input
                      type="checkbox"
                      checked={form.auto_generate}
                      onChange={(e) => setForm((f) => ({ ...f, auto_generate: e.target.checked }))}
                    />
                    Auto-generate on save
                  </label>
                </label>
                <label className="block text-sm">
                  <span className="font-medium">Pilot duration (months)</span>
                  <Input
                    type="number"
                    min={1}
                    max={36}
                    className="mt-1"
                    value={form.discount_duration_in_months}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, discount_duration_in_months: Number(e.target.value) }))
                    }
                    data-testid="pilot-duration-months"
                  />
                </label>
                <label className="block text-sm">
                  <span className="font-medium">Discount %</span>
                  <Input
                    type="number"
                    min={1}
                    max={100}
                    className="mt-1"
                    value={form.discount_percent}
                    onChange={(e) => setForm((f) => ({ ...f, discount_percent: Number(e.target.value) }))}
                  />
                </label>
                <label className="block text-sm">
                  <span className="font-medium">Max uses</span>
                  <Input
                    type="number"
                    min={1}
                    className="mt-1"
                    value={form.max_uses}
                    onChange={(e) => setForm((f) => ({ ...f, max_uses: Number(e.target.value) }))}
                  />
                </label>
                <label className="block text-sm">
                  <span className="font-medium">Stripe coupon ID</span>
                  <Input
                    className="mt-1 font-mono text-xs"
                    value={form.stripe_coupon_id}
                    onChange={(e) => setForm((f) => ({ ...f, stripe_coupon_id: e.target.value }))}
                    data-testid="stripe-coupon-id"
                  />
                </label>
                <label className="block text-sm">
                  <span className="font-medium">Promotion code ID (optional)</span>
                  <Input
                    className="mt-1 font-mono text-xs"
                    value={form.stripe_promotion_code_id}
                    onChange={(e) => setForm((f) => ({ ...f, stripe_promotion_code_id: e.target.value }))}
                  />
                </label>
                <label className="block text-sm">
                  <span className="font-medium">Onboarding fee policy</span>
                  <select
                    className="mt-1 w-full border rounded-md px-3 py-2 text-sm"
                    value={form.onboarding_fee_policy}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        onboarding_fee_policy: e.target.value,
                        waive_onboarding_fee: e.target.value === 'waived',
                      }))
                    }
                    data-testid="onboarding-fee-policy"
                  >
                    {ONBOARDING_POLICY_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm">
                  <span className="font-medium">Expiry (optional)</span>
                  <Input
                    type="datetime-local"
                    className="mt-1"
                    value={form.expires_at}
                    onChange={(e) => setForm((f) => ({ ...f, expires_at: e.target.value }))}
                  />
                </label>
              </div>
              <label className="block text-sm">
                <span className="font-medium">Allowed plans</span>
                <div className="flex flex-wrap gap-3 mt-2">
                  {PILOT_PLAN_OPTIONS.map((p) => (
                    <label key={p.value} className="flex items-center gap-1.5 text-sm">
                      <input
                        type="checkbox"
                        checked={form.applies_to_plan_codes.includes(p.value)}
                        onChange={(e) => {
                          setForm((f) => {
                            const set = new Set(f.applies_to_plan_codes);
                            if (e.target.checked) set.add(p.value);
                            else set.delete(p.value);
                            return { ...f, applies_to_plan_codes: [...set] };
                          });
                        }}
                      />
                      {p.label}
                    </label>
                  ))}
                </div>
              </label>
              <label className="block text-sm">
                <span className="font-medium">Internal notes</span>
                <Input
                  className="mt-1"
                  value={form.internal_notes}
                  onChange={(e) => setForm((f) => ({ ...f, internal_notes: e.target.value }))}
                />
              </label>
              <div className="flex flex-wrap gap-2 items-center">
                <Button type="button" variant="secondary" onClick={handleValidateStripe} disabled={validatingStripe}>
                  {validatingStripe ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Validate Stripe coupon
                </Button>
                <Button type="submit" disabled={creating}>
                  {creating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Create invite
                </Button>
              </div>
              {stripeDisplay && (
                <Alert variant={stripeDisplay.ok ? 'default' : 'destructive'} data-testid="stripe-validation-result">
                  <AlertDescription>
                    <p className="font-medium">{stripeDisplay.title}</p>
                    <ul className="list-disc ml-4 mt-1 text-xs">
                      {stripeDisplay.lines.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Invite codes</CardTitle>
          <div className="flex flex-wrap gap-2 mt-3">
            <select
              className="border rounded px-2 py-1 text-sm"
              value={filters.status}
              onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
              data-testid="filter-status"
            >
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="expired">Expired</option>
              <option value="disabled">Disabled</option>
              <option value="exhausted">Exhausted</option>
              <option value="waived_onboarding">Waived onboarding</option>
            </select>
            <select
              className="border rounded px-2 py-1 text-sm"
              value={filters.onboarding_policy}
              onChange={(e) => setFilters((f) => ({ ...f, onboarding_policy: e.target.value }))}
            >
              <option value="">All onboarding policies</option>
              {ONBOARDING_POLICY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <Input
              placeholder="Duration (months)"
              className="w-36 h-8 text-sm"
              value={filters.duration_months}
              onChange={(e) => setFilters((f) => ({ ...f, duration_months: e.target.value }))}
            />
            <select
              className="border rounded px-2 py-1 text-sm"
              value={filters.plan_code}
              onChange={(e) => setFilters((f) => ({ ...f, plan_code: e.target.value }))}
            >
              <option value="">All plans</option>
              {PILOT_PLAN_OPTIONS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {loading ? (
            <p className="text-sm text-gray-500 flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading…
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="pilot-invites-table">
                <thead>
                  <tr className="border-b text-left text-gray-600">
                    <th className="py-2 pr-3">Code</th>
                    <th className="py-2 pr-3">Duration</th>
                    <th className="py-2 pr-3">Onboarding</th>
                    <th className="py-2 pr-3">Uses</th>
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2 pr-3">Coupon</th>
                    <th className="py-2 pr-3">Created</th>
                    <th className="py-2" />
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row) => (
                    <tr key={row.code} className="border-b hover:bg-slate-50">
                      <td className="py-2 pr-3 font-mono font-medium">{row.code}</td>
                      <td className="py-2 pr-3" data-testid={`duration-${row.code}`}>
                        {formatPilotDuration(row)}
                      </td>
                      <td className="py-2 pr-3">{row.onboarding_fee_policy || '—'}</td>
                      <td className="py-2 pr-3">
                        {row.used_count ?? 0} / {row.max_uses ?? 1}
                        <span className="text-gray-500"> ({row.remaining_uses ?? 0} left)</span>
                      </td>
                      <td className="py-2 pr-3">
                        <span
                          className={`px-2 py-0.5 rounded text-xs ${inviteStatusBadgeClass(
                            row.effective_status || row.status,
                          )}`}
                        >
                          {row.effective_status || row.status}
                        </span>
                      </td>
                      <td className="py-2 pr-3 font-mono text-xs truncate max-w-[120px]">
                        {row.stripe_coupon_id || '—'}
                      </td>
                      <td className="py-2 pr-3 text-xs">{formatDate(row.created_at)}</td>
                      <td className="py-2">
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={async () => {
                              await copyToClipboard(row.code);
                              toast.success('Code copied');
                            }}
                          >
                            <Copy className="h-3 w-3" />
                          </Button>
                          <Button size="sm" variant="ghost" asChild>
                            <Link to={`/admin/pilot-invites/${encodeURIComponent(row.code)}`}>
                              <ExternalLink className="h-3 w-3" />
                            </Link>
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!filtered.length && <p className="text-sm text-gray-500 py-6">No invites match filters.</p>}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
    </UnifiedAdminLayout>
  );
}
