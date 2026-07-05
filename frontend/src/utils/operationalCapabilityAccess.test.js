import {
  evaluateCommandCentreCapabilitiesFromMap,
  evaluateDashboardCapabilitiesFromMap,
  evaluateTodayCapabilitiesFromMap,
  getCapabilityDeniedMessage,
  isCapabilityDeniedApiError,
  OPERATIONAL_LIFECYCLE_GRANT_FIXTURES,
  OPS_CAPABILITY,
} from './operationalCapabilityAccess';

describe('operationalCapabilityAccess', () => {
  it('parses capability_denied API payloads', () => {
    const error = {
      response: {
        data: {
          detail: {
            error: 'capability_denied',
            message: 'Dashboard is not available for this account state.',
            capability_id: OPS_CAPABILITY.DASHBOARD_VIEW,
          },
        },
      },
    };
    expect(isCapabilityDeniedApiError(error)).toBe(true);
    expect(getCapabilityDeniedMessage(error)).toBe('Dashboard is not available for this account state.');
  });

  describe.each([
    ['ACTIVE', true, true, true, true],
    ['READ_ONLY', true, true, false, true],
    ['CANCELLED_IMMEDIATE', false, false, false, false],
    ['SUSPENDED', false, false, false, false],
    ['ARCHIVED', false, false, false, false],
    ['UNKNOWN', false, false, false, false],
  ])(
    'lifecycle %s dashboard=%s todayView=%s todayAct=%s cmdCtr=%s',
    (lifecycle, dashboard, todayView, todayAct, cmdCtr) => {
      it('mirrors runtime contract operational grants', () => {
        const dash = evaluateDashboardCapabilitiesFromMap(OPERATIONAL_LIFECYCLE_GRANT_FIXTURES[lifecycle]);
        const today = evaluateTodayCapabilitiesFromMap(OPERATIONAL_LIFECYCLE_GRANT_FIXTURES[lifecycle]);
        const cc = evaluateCommandCentreCapabilitiesFromMap(OPERATIONAL_LIFECYCLE_GRANT_FIXTURES[lifecycle]);
        expect(dash.canViewDashboard).toBe(dashboard);
        expect(today.canViewToday).toBe(todayView);
        expect(today.canActToday).toBe(todayAct);
        expect(cc.canViewCommandCentre).toBe(cmdCtr);
        if (lifecycle === 'ACTIVE') {
          expect(dash.canUseOpsMaintenance).toBe(true);
          expect(today.canUseOpsPredictive).toBe(true);
        }
        if (lifecycle === 'READ_ONLY') {
          expect(dash.canViewScore).toBe(true);
          expect(dash.canUseOpsMaintenance).toBe(false);
        }
      });
    },
  );

  describe.each([
    ['TRIAL', true],
    ['GRACE_PERIOD', true],
    ['CANCELLATION_SCHEDULED', true],
    ['SUBSCRIPTION_EXPIRED', false],
  ])('extended lifecycle %s dashboard allowed=%s', (lifecycle, allowed) => {
    it('preserves recovery and grace operational visibility', () => {
      const dash = evaluateDashboardCapabilitiesFromMap(OPERATIONAL_LIFECYCLE_GRANT_FIXTURES[lifecycle]);
      expect(dash.canViewDashboard).toBe(allowed);
    });
  });
});
