import {
  computeOpsMetrics,
  filterPilotAccounts,
  formatTimelineEvent,
  healthBandClass,
  flattenAccountRow,
} from './pilotOperationsAdmin';

describe('pilotOperationsAdmin', () => {
  const sampleAccounts = [
    {
      client_id: 'c1',
      full_name: 'Alice',
      pilot_status: 'active',
      ops: {
        pilot_governance_status: 'active',
        pilot_health_band: 'healthy',
        days_remaining: 5,
        conversion_readiness: { missing_payment_method: true },
      },
      open_anomalies: [{ anomaly_id: 'a1' }],
    },
    {
      client_id: 'c2',
      contact_email: 'bob@example.com',
      pilot_status: 'converted_to_paid',
      ops: {
        pilot_governance_status: 'converted',
        pilot_health_band: 'conversion_ready',
        days_remaining: 30,
        conversion_readiness: { likely_conversion: true },
      },
      open_anomalies: [],
    },
  ];

  test('flattenAccountRow maps ops fields', () => {
    const row = flattenAccountRow(sampleAccounts[0]);
    expect(row.client_id).toBe('c1');
    expect(row.health_band).toBe('healthy');
    expect(row.anomaly_count).toBe(1);
    expect(row.missing_payment_method).toBe(true);
  });

  test('computeOpsMetrics counts active and anomalies', () => {
    const m = computeOpsMetrics(sampleAccounts);
    expect(m.total).toBe(2);
    expect(m.active).toBe(1);
    expect(m.open_anomalies).toBe(1);
    expect(m.missing_payment_method).toBe(1);
    expect(m.conversion_ready).toBe(1);
  });

  test('filterPilotAccounts by missing_pm and governance', () => {
    const rows = filterPilotAccounts(sampleAccounts, { missing_pm: true }, '');
    expect(rows).toHaveLength(1);
    expect(rows[0].client_id).toBe('c1');
  });

  test('filterPilotAccounts search matches invite code', () => {
    const accounts = [
      {
        client_id: 'c3',
        pilot_invite_code: 'FOUNDING-2026',
        ops: { pilot_governance_status: 'active' },
        open_anomalies: [],
      },
    ];
    const rows = filterPilotAccounts(accounts, {}, 'founding');
    expect(rows).toHaveLength(1);
  });

  test('formatTimelineEvent maps known actions', () => {
    const ev = formatTimelineEvent({
      audit_id: '1',
      action_type: 'converted_to_paid',
      created_at: '2026-01-01T00:00:00Z',
      actor: { type: 'admin', email: 'ops@pleerity.com' },
    });
    expect(ev.label).toBe('Converted to paid');
    expect(ev.category).toBe('conversion');
  });

  test('healthBandClass returns band styles', () => {
    expect(healthBandClass('healthy')).toContain('emerald');
    expect(healthBandClass('at_risk')).toContain('amber');
  });
});
