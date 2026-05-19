import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Plus,
  RefreshCw,
  Copy,
  RefreshCw as RefreshCwIcon,
  Wand2,
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
  CAMPAIGN_STATUS_OPTIONS,
  CODE_TYPE_OPTIONS,
  ONBOARDING_POLICY_OPTIONS,
  PILOT_PLAN_OPTIONS,
  buildDefaultCreateForm,
  copyToClipboard,
  filterPilotInvites,
  formToCreatePayload,
  formatPilotDuration,
  inviteStatusBadgeClass,
  isInternalTest,
  isPublicPromoFamily,
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
    code_type: '',
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

  const [generatingCode, setGeneratingCode] = useState(false);

  const handleGenerateCode = async ({ regenerate = false } = {}) => {
    setGeneratingCode(true);
    try {
      const res = await adminAPI.generatePilotInviteCode({
        code_type: form.code_type || 'private_invite',
        prefix: form.code_prefix || (form.code_type === 'public_promo' ? 'LAUNCH' : 'FOUNDING'),
        variant: form.code_variant || '',
        campaign_name: form.campaign_name || '',
      });
      const generated = res.data?.code || res.data?.normalized || '';
      setForm((f) => ({
        ...f,
        code: generated,
        auto_generate: false,
        manual_code_override: true,
      }));
      toast.success(regenerate ? 'Code regenerated' : 'Code generated');
    } catch (e) {
      const detail = e.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Could not generate code');
    } finally {
      setGeneratingCode(false);
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
    const payload = formToCreatePayload(form);
    if (!payload.auto_generate && !payload.code) {
      toast.error('Generate a code, enter one manually, or enable auto-generate on save');
      return;
    }
    setCreating(true);
    try {
      const res = await adminAPI.createPilotInvite(payload);
      const createdCode = res.data?.invite_code?.code || payload.code;
      toast.success(`Invite ${createdCode} created`);
      setShowCreate(false);
      setForm(buildDefaultCreateForm());
      setStripeResult(null);
      await load();
      navigate(`/admin/pilot-invites/${encodeURIComponent(createdCode)}`);
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
                <label className="block text-sm md:col-span-2">
                  <span className="font-medium">Invite / promo code</span>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Server-authoritative generation. Generate, regenerate, manual override, or auto-generate on save.
                  </p>
                  <div className="flex flex-wrap gap-2 mt-2">
                    <Input
                      className="flex-1 min-w-[200px] font-mono"
                      value={form.code}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          code: e.target.value,
                          auto_generate: false,
                          manual_code_override: true,
                        }))
                      }
                      placeholder="FOUNDING-8K4D or LAUNCH2026"
                      disabled={form.auto_generate}
                      data-testid="pilot-invite-code-input"
                    />
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => handleGenerateCode()}
                      disabled={generatingCode}
                      data-testid="pilot-invite-generate"
                    >
                      {generatingCode ? (
                        <Loader2 className="h-4 w-4 animate-spin mr-1" />
                      ) : (
                        <Wand2 className="h-4 w-4 mr-1" />
                      )}
                      Generate
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => handleGenerateCode({ regenerate: true })}
                      disabled={generatingCode || !form.code}
                      data-testid="pilot-invite-regenerate"
                    >
                      <RefreshCwIcon className="h-4 w-4 mr-1" />
                      Regenerate
                    </Button>
                  </div>
                  <label className="flex items-center gap-2 mt-2 text-xs">
                    <input
                      type="checkbox"
                      checked={form.auto_generate}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          auto_generate: e.target.checked,
                          manual_code_override: !e.target.checked,
                        }))
                      }
                    />
                    Auto-generate on save when the code field is empty
                  </label>
                </label>
                <label className="block text-sm">
                  <span className="font-medium">Code type</span>
                  <select
                    className="mt-1 w-full border rounded-md px-3 py-2 text-sm"
                    value={form.code_type}
                    onChange={(e) => {
                      const ct = e.target.value;
                      const internal = isInternalTest(ct);
                      setForm((f) => ({
                        ...f,
                        code_type: ct,
                        max_uses: internal ? 5 : f.max_uses,
                        onboarding_fee_policy: internal ? 'waived' : f.onboarding_fee_policy,
                        waive_onboarding_fee: internal ? true : f.waive_onboarding_fee,
                        campaign_status: isPublicPromoFamily(ct) ? 'draft' : 'not_applicable',
                        campaign_state: isPublicPromoFamily(ct) ? 'draft' : f.campaign_state || 'draft',
                        launch_visibility: internal ? 'internal' : isPublicPromoFamily(ct) ? 'restricted' : 'private',
                        analytics_family: internal ? 'internal_test' : ct,
                        internal_live_test: internal,
                        is_publicly_enterable: false,
                        public_entry_enabled: false,
                      }));
                    }}
                    data-testid="pilot-code-type"
                  >
                    {CODE_TYPE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                {isInternalTest(form.code_type) && (
                  <Alert className="md:col-span-2">
                    <AlertDescription>
                      Internal test campaigns are hidden from public entry, onboarding is waived, analytics are separated,
                      and max uses are capped at 10.
                    </AlertDescription>
                  </Alert>
                )}
                {isPublicPromoFamily(form.code_type) && (
                  <>
                    <label className="block text-sm">
                      <span className="font-medium">Campaign name</span>
                      <Input
                        className="mt-1"
                        value={form.campaign_name}
                        onChange={(e) => setForm((f) => ({ ...f, campaign_name: e.target.value }))}
                      />
                    </label>
                    <label className="block text-sm">
                      <span className="font-medium">Campaign status</span>
                      <select
                        className="mt-1 w-full border rounded-md px-3 py-2 text-sm"
                        value={form.campaign_status}
                        onChange={(e) => setForm((f) => ({ ...f, campaign_status: e.target.value }))}
                      >
                        {CAMPAIGN_STATUS_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="flex items-center gap-2 text-sm md:col-span-2">
                      <input
                        type="checkbox"
                        checked={form.public_entry_enabled}
                        onChange={(e) => setForm((f) => ({ ...f, public_entry_enabled: e.target.checked }))}
                      />
                      Enable public entry (master switch — off by default)
                    </label>
                    <label className="flex items-center gap-2 text-sm md:col-span-2">
                      <input
                        type="checkbox"
                        checked={form.is_publicly_enterable}
                        onChange={(e) => setForm((f) => ({ ...f, is_publicly_enterable: e.target.checked }))}
                      />
                      Allow manual code entry at intake
                    </label>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={form.one_redemption_per_email}
                        onChange={(e) => setForm((f) => ({ ...f, one_redemption_per_email: e.target.checked }))}
                      />
                      One redemption per email
                    </label>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={form.first_time_customer_only}
                        onChange={(e) => setForm((f) => ({ ...f, first_time_customer_only: e.target.checked }))}
                      />
                      First-time customers only
                    </label>
                  </>
                )}
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
                    max={isInternalTest(form.code_type) ? 10 : undefined}
                    className="mt-1"
                    value={form.max_uses}
                    onChange={(e) => setForm((f) => ({ ...f, max_uses: Number(e.target.value) }))}
                  />
                </label>
                <label className="block text-sm">
                  <span className="font-medium">Max uses per account</span>
                  <Input
                    type="number"
                    min={1}
                    className="mt-1"
                    value={form.max_uses_per_account}
                    onChange={(e) => setForm((f) => ({ ...f, max_uses_per_account: e.target.value }))}
                    placeholder="Optional"
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
                    disabled={isInternalTest(form.code_type)}
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
            <select
              className="border rounded px-2 py-1 text-sm"
              value={filters.code_type}
              onChange={(e) => setFilters((f) => ({ ...f, code_type: e.target.value }))}
              data-testid="filter-code-type"
            >
              <option value="">All code types</option>
              {CODE_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
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
                    <th className="py-2 pr-3">Type</th>
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
                      <td className="py-2 pr-3 text-xs">
                        <span>{row.code_type || 'private_invite'}</span>
                        {row.code_type === 'internal_test' && (
                          <span className="ml-1 px-1.5 py-0.5 rounded bg-purple-100 text-purple-800">internal</span>
                        )}
                        <div className="text-gray-500">{row.campaign_state || row.campaign_status || '—'}</div>
                      </td>
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
