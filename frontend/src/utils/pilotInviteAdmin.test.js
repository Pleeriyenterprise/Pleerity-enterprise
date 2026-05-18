import {
  filterPilotInvites,
  formatPilotDuration,
  formToCreatePayload,
  normalizeInviteCode,
  stripeValidationToDisplay,
} from './pilotInviteAdmin';

describe('pilotInviteAdmin', () => {
  test('normalizeInviteCode uppercases and strips spaces', () => {
    expect(normalizeInviteCode(' landlord-pilot-2026 ')).toBe('LANDLORD-PILOT-2026');
  });

  test('formatPilotDuration uses months from row not hardcoded 2', () => {
    expect(
      formatPilotDuration({
        discount_duration: 'repeating',
        discount_duration_in_months: 3,
        discount_percent: 100,
      }),
    ).toBe('100% off for 3 months');
  });

  test('filterPilotInvites by status exhausted', () => {
    const rows = [
      { code: 'A', effective_status: 'active', remaining_uses: 0, max_uses: 1, used_count: 1 },
      { code: 'B', effective_status: 'active', remaining_uses: 2, max_uses: 5, used_count: 3 },
    ];
    expect(filterPilotInvites(rows, { status: 'exhausted' })).toHaveLength(1);
    expect(filterPilotInvites(rows, { status: 'exhausted' })[0].code).toBe('A');
  });

  test('formToCreatePayload maps waived onboarding', () => {
    const payload = formToCreatePayload({
      code: 'TEST',
      program_type: 'FOUNDING_PILOT',
      applies_to_plan_codes: ['PLAN_1_SOLO'],
      max_uses: 5,
      expires_at: '',
      email_restriction: '',
      stripe_coupon_id: 'c1',
      stripe_promotion_code_id: '',
      discount_mode: 'coupon',
      discount_percent: 100,
      discount_duration: 'repeating',
      discount_duration_in_months: 2,
      onboarding_fee_policy: 'waived',
      waive_onboarding_fee: true,
      internal_notes: 'note',
    });
    expect(payload.onboarding_fee_policy).toBe('waived');
    expect(payload.metadata.internal_notes).toBe('note');
  });

  test('stripeValidationToDisplay success', () => {
    const d = stripeValidationToDisplay({
      valid: true,
      coupon: { id: 'c1', percent_off: 100, duration: 'repeating', duration_in_months: 2 },
      invite_expects: { discount_percent: 100, discount_duration: 'repeating', discount_duration_in_months: 2 },
    });
    expect(d.ok).toBe(true);
    expect(d.lines[0]).toContain('100%');
  });
});
