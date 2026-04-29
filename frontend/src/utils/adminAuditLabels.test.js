import {
  formatAuditTimestampUtc,
  getAuditEventLabel,
  getAuditEventSeverity,
  getAuditSeverityBadgeClass,
} from './adminAuditLabels';

describe('adminAuditLabels', () => {
  it('maps known audit actions to readable labels', () => {
    expect(getAuditEventLabel('USER_LOGIN_SUCCESS')).toBe('User signed in');
    expect(getAuditEventLabel('ADMIN_ACTION')).toBe('Admin operation performed');
    expect(getAuditEventLabel('NOTIFICATION_BLOCKED_PLAN_GATE')).toContain('Notification blocked');
  });

  it('assigns severity tiers', () => {
    expect(getAuditEventSeverity('USER_LOGIN_SUCCESS')).toBe('low');
    expect(getAuditEventSeverity('EMAIL_FAILED')).toBe('high');
    expect(getAuditEventSeverity('UNKNOWN_CUSTOM_EVENT')).toBe('info');
  });

  it('formats UTC timestamps consistently', () => {
    const s = formatAuditTimestampUtc('2026-04-28T15:30:00.000Z');
    expect(s).toContain('UTC');
  });

  it('exposes badge classes for severity', () => {
    expect(getAuditSeverityBadgeClass('high')).toContain('red');
  });
});
