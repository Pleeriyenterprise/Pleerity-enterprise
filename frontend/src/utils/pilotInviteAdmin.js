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

export function normalizeInviteCode(raw) {
  return String(raw || '')
    .trim()
    .toUpperCase()
    .replace(/\s+/g, '');
}

export function filterPilotInvites(invites, filters) {
  const list = Array.isArray(invites) ? invites : [];
  const status = (filters?.status || '').toLowerCase();
  const policy = (filters?.onboarding_policy || '').toLowerCase();
  const duration = filters?.duration_months ? Number(filters.duration_months) : null;
  const plan = (filters?.plan_code || '').trim().toUpperCase();

  return list.filter((row) => {
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
  };
}

export function formToCreatePayload(form) {
  const metadata = {};
  if (form.internal_notes?.trim()) {
    metadata.internal_notes = form.internal_notes.trim();
  }
  return {
    code: normalizeInviteCode(form.code),
    program_type: form.program_type,
    applies_to_plan_codes: form.applies_to_plan_codes,
    max_uses: Number(form.max_uses) || 1,
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
    waive_onboarding_fee: form.onboarding_fee_policy === 'waived',
    onboarding_fee_policy: form.onboarding_fee_policy,
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
