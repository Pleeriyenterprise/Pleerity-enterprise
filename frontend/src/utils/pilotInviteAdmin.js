/**
 * Admin pilot invite helpers — code generation, filtering, share copy (no duplicated commercial wording).
 */

export const PILOT_PLAN_OPTIONS = [
  { value: 'PLAN_1_SOLO', label: 'Solo Landlord' },
  { value: 'PLAN_2_PORTFOLIO', label: 'Portfolio' },
  { value: 'PLAN_3_PRO', label: 'Pro' },
];

export const ONBOARDING_POLICY_OPTIONS = [
  { value: 'waived', label: 'Waived (default founding pilot)' },
  { value: 'charge_now', label: 'Charge at checkout' },
  { value: 'deferred', label: 'Deferred (experimental — blocked at checkout)' },
];

export const DISCOUNT_DURATION_OPTIONS = [
  { value: 'repeating', label: 'Repeating (pilot months)' },
  { value: 'once', label: 'Once' },
  { value: 'forever', label: 'Forever' },
];

export const CODE_TYPE_OPTIONS = [
  { value: 'private_invite', label: 'Private invite (founding pilot link)' },
  { value: 'public_promo', label: 'Public promo (campaign)' },
  { value: 'referral', label: 'Referral' },
  { value: 'partner', label: 'Partner' },
  { value: 'internal_test', label: 'Internal live/test (hidden)' },
];

export const CAMPAIGN_STATUS_OPTIONS = [
  { value: 'draft', label: 'Draft' },
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'ended', label: 'Ended' },
];

export const CAMPAIGN_STATE_OPTIONS = [
  { value: 'draft', label: 'Draft' },
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'expired', label: 'Expired' },
  { value: 'archived', label: 'Archived' },
];

export const LAUNCH_VISIBILITY_OPTIONS = [
  { value: 'private', label: 'Private' },
  { value: 'restricted', label: 'Restricted' },
  { value: 'public', label: 'Public' },
  { value: 'internal', label: 'Internal' },
];

export function isPublicPromoFamily(codeType) {
  return ['public_promo', 'referral', 'partner'].includes(String(codeType || '').toLowerCase());
}

export function isInternalTest(codeType) {
  return String(codeType || '').toLowerCase() === 'internal_test';
}

/** Display-only normalization; authoritative rules run on the backend. */
export function normalizeInviteCode(raw) {
  return String(raw || '')
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
}

export function filterPilotInvites(invites, filters) {
  const list = Array.isArray(invites) ? invites : [];
  const status = (filters?.status || '').toLowerCase();
  const policy = (filters?.onboarding_policy || '').toLowerCase();
  const duration = filters?.duration_months ? Number(filters.duration_months) : null;
  const plan = (filters?.plan_code || '').trim().toUpperCase();
  const codeType = (filters?.code_type || '').trim().toLowerCase();

  return list.filter((row) => {
    if (codeType && (row.code_type || 'private_invite') !== codeType) return false;
    if (status && status !== 'all') {
      if (status === 'exhausted') {
        if ((row.remaining_uses ?? 0) > 0) return false;
      } else if (status === 'waived_onboarding') {
        if (row.onboarding_fee_policy !== 'waived') return false;
      } else if ((row.effective_status || row.status) !== status) {
        return false;
      }
    }
    if (policy && row.onboarding_fee_policy !== policy) return false;
    if (duration != null && Number(row.discount_duration_in_months) !== duration) return false;
    if (plan) {
      const allowed = row.applies_to_plan_codes || [];
      if (allowed.length && !allowed.map((p) => String(p).toUpperCase()).includes(plan)) return false;
    }
    return true;
  });
}

export function inviteStatusBadgeClass(effectiveStatus) {
  const s = (effectiveStatus || '').toLowerCase();
  if (s === 'active') return 'bg-emerald-100 text-emerald-800';
  if (s === 'expired') return 'bg-amber-100 text-amber-800';
  if (s === 'disabled') return 'bg-gray-200 text-gray-700';
  return 'bg-slate-100 text-slate-700';
}

export function formatPilotDuration(row) {
  const months = row?.discount_duration_in_months;
  const dur = row?.discount_duration;
  const pct = row?.discount_percent;
  if (dur === 'repeating' && months) {
    return `${pct ?? 100}% off for ${months} month${months === 1 ? '' : 's'}`;
  }
  if (dur === 'forever') return `${pct ?? 100}% off (forever)`;
  if (dur === 'once') return `${pct ?? 100}% off (once)`;
  return `${pct ?? 100}% off`;
}

export async function copyToClipboard(text) {
  const value = String(text || '');
  if (!value) return false;
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return true;
  }
  const ta = document.createElement('textarea');
  ta.value = value;
  document.body.appendChild(ta);
  ta.select();
  const ok = document.execCommand('copy');
  document.body.removeChild(ta);
  return ok;
}

export function buildDefaultCreateForm() {
  return {
    code: '',
    auto_generate: true,
    code_prefix: 'FOUNDING',
    code_variant: '',
    program_type: 'FOUNDING_PILOT',
    discount_duration_in_months: 2,
    discount_percent: 100,
    discount_duration: 'repeating',
    discount_mode: 'coupon',
    max_uses: 1,
    expires_at: '',
    applies_to_plan_codes: ['PLAN_1_SOLO', 'PLAN_2_PORTFOLIO', 'PLAN_3_PRO'],
    onboarding_fee_policy: 'waived',
    waive_onboarding_fee: true,
    stripe_coupon_id: '',
    stripe_promotion_code_id: '',
    email_restriction: '',
    internal_notes: '',
    code_type: 'private_invite',
    campaign_name: '',
    campaign_status: 'not_applicable',
    campaign_state: 'draft',
    launch_visibility: 'private',
    analytics_family: 'private_invite',
    max_uses_per_account: '',
    internal_live_test: false,
    is_publicly_enterable: false,
    public_entry_enabled: false,
    first_time_customer_only: false,
    one_redemption_per_email: false,
    one_redemption_per_customer: false,
    max_uses_per_day: '',
  };
}

export function formToCreatePayload(form) {
  const metadata = {};
  if (form.internal_notes?.trim()) {
    metadata.internal_notes = form.internal_notes.trim();
  }
  if (form.code_prefix?.trim()) {
    metadata.generation_prefix = form.code_prefix.trim();
  }
  if (form.code_variant?.trim()) {
    metadata.generation_variant = form.code_variant.trim();
  }
  const internal = isInternalTest(form.code_type);
  return {
    code: normalizeInviteCode(form.code),
    auto_generate: Boolean(form.auto_generate),
    program_type: form.program_type,
    applies_to_plan_codes: form.applies_to_plan_codes,
    max_uses: internal ? Math.min(Number(form.max_uses) || 5, 10) : Number(form.max_uses) || 1,
    expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
    email_restriction: form.email_restriction?.trim() || null,
    stripe_coupon_id: form.stripe_coupon_id?.trim() || null,
    stripe_promotion_code_id: form.stripe_promotion_code_id?.trim() || null,
    discount_mode: form.discount_mode,
    discount_type: 'percent',
    discount_percent: Number(form.discount_percent) || 100,
    discount_duration: form.discount_duration,
    discount_duration_in_months:
      form.discount_duration === 'repeating' ? Number(form.discount_duration_in_months) || 2 : null,
    waive_onboarding_fee: internal ? true : form.onboarding_fee_policy === 'waived',
    onboarding_fee_policy: internal ? 'waived' : form.onboarding_fee_policy,
    code_type: form.code_type || 'private_invite',
    campaign_name: form.campaign_name?.trim() || null,
    campaign_status: isPublicPromoFamily(form.code_type)
      ? form.campaign_status || 'draft'
      : 'not_applicable',
    campaign_state: isPublicPromoFamily(form.code_type)
      ? form.campaign_status || form.campaign_state || 'draft'
      : form.campaign_state || 'draft',
    launch_visibility: internal ? 'internal' : form.launch_visibility || 'private',
    analytics_family: internal ? 'internal_test' : form.analytics_family || form.code_type || 'private_invite',
    max_uses_per_account: form.max_uses_per_account ? Number(form.max_uses_per_account) : null,
    internal_live_test: internal || Boolean(form.internal_live_test),
    is_publicly_enterable: internal ? false : Boolean(form.is_publicly_enterable),
    public_entry_enabled: internal ? false : Boolean(form.public_entry_enabled),
    first_time_customer_only: Boolean(form.first_time_customer_only),
    one_redemption_per_email: Boolean(form.one_redemption_per_email),
    one_redemption_per_customer: Boolean(form.one_redemption_per_customer),
    max_uses_per_day: form.max_uses_per_day ? Number(form.max_uses_per_day) : null,
    public_description: form.public_description?.trim() || null,
    metadata,
  };
}

export function stripeValidationToDisplay(result) {
  if (!result) return null;
  if (!result.valid) {
    return {
      ok: false,
      title: 'Stripe validation failed',
      lines: result.details?.length ? result.details : [result.message || 'Unknown error'],
    };
  }
  const c = result.coupon || {};
  const exp = result.invite_expects || {};
  return {
    ok: true,
    title: 'Stripe coupon valid',
    lines: [
      `Coupon ${c.id}: ${c.percent_off}% off, duration=${c.duration}${
        c.duration_in_months ? ` (${c.duration_in_months} mo)` : ''
      }`,
      `Invite expects: ${exp.discount_percent}% / ${exp.discount_duration}${
        exp.discount_duration_in_months ? ` / ${exp.discount_duration_in_months} mo` : ''
      }`,
    ],
  };
}
