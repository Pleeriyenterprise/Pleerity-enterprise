import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PilotAccountRecoveryPanel from './PilotAccountRecoveryPanel';

jest.mock('../../../hooks/usePilotAccountRecovery', () => ({
  usePilotAccountRecovery: jest.fn(),
}));

const { usePilotAccountRecovery } = require('../../../hooks/usePilotAccountRecovery');

describe('PilotAccountRecoveryPanel visibility', () => {
  beforeEach(() => {
    usePilotAccountRecovery.mockReset();
  });

  test('hidden when no promo history', () => {
    usePilotAccountRecovery.mockReturnValue({
      loading: false,
      error: null,
      reload: jest.fn(),
      showRecoveryPanel: false,
      redemptions: [],
      eligibilityOverrides: [],
      indicators: {},
      inviteMetadata: {},
      strandedCount: 0,
    });
    const { container } = render(
      <MemoryRouter>
        <PilotAccountRecoveryPanel clientId="plain-client" />
      </MemoryRouter>,
    );
    expect(container.querySelector('[data-testid="pilot-account-recovery-panel"]')).toBeNull();
  });

  test('shows for intake_pending payment_failed user', () => {
    usePilotAccountRecovery.mockReturnValue({
      loading: false,
      error: null,
      reload: jest.fn(),
      showRecoveryPanel: true,
      redemptions: [
        {
          redemption_id: 'r1',
          status: 'payment_failed',
          retry_eligible: false,
          consumes_eligibility: false,
          failure_reason: 'checkout abandoned',
        },
      ],
      eligibilityOverrides: [],
      indicators: { stranded_onboarding: true, badges: ['payment_failed'] },
      inviteMetadata: { pilot_invite_code: 'FOUNDING2026', onboarding_status: 'INTAKE_PENDING' },
      strandedCount: 1,
    });
    render(
      <MemoryRouter>
        <PilotAccountRecoveryPanel clientId="intake-client" defaultEmail="u@example.com" />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('pilot-account-recovery-panel')).toBeInTheDocument();
    expect(screen.getByTestId('pilot-redemption-recovery-panel')).toBeInTheDocument();
    expect(screen.getByTestId('recovery-badge-payment_failed')).toBeInTheDocument();
  });

  test('shows for override-only user', () => {
    usePilotAccountRecovery.mockReturnValue({
      loading: false,
      error: null,
      reload: jest.fn(),
      showRecoveryPanel: true,
      redemptions: [],
      eligibilityOverrides: [
        {
          override_id: 'ov1',
          override_type: 'bypass_first_time',
          scope: 'email',
          scope_value: 'u@example.com',
          override_reason: 'Approved',
          override_created_at: '2026-05-01T12:00:00Z',
        },
      ],
      indicators: { override_active: true, badges: ['override_active'] },
      inviteMetadata: {},
      strandedCount: 0,
    });
    render(
      <MemoryRouter>
        <PilotAccountRecoveryPanel clientId="override-client" />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('override-row-ov1')).toBeInTheDocument();
  });
});
