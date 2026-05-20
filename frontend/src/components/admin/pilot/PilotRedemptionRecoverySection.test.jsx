import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PilotRedemptionRecoverySection from './PilotRedemptionRecoverySection';

jest.mock('../../../api/client', () => ({
  adminAPI: {
    allowPilotRedemptionRetry: jest.fn(),
    resetPilotRedemptionIncomplete: jest.fn(),
    createPilotEligibilityOverride: jest.fn(),
    createPilotAccountEligibilityOverride: jest.fn(),
    revokePilotEligibilityOverride: jest.fn(),
  },
}));

describe('PilotRedemptionRecoverySection', () => {
  test('account panel renders redemption attempts and overrides', () => {
    render(
      <MemoryRouter>
        <PilotRedemptionRecoverySection
          context="account"
          clientId="client-abc"
          redemptions={[
            {
              redemption_id: 'r1',
              status: 'payment_failed',
              retry_eligible: false,
              consumes_eligibility: false,
              redemption_email: 'u@example.com',
              code: 'FOUNDING2026',
              failure_reason: 'checkout abandoned',
              created_at: '2026-05-01T12:00:00Z',
            },
          ]}
          eligibilityOverrides={[
            {
              override_id: 'ov1',
              override_type: 'bypass_first_time',
              scope: 'email',
              scope_value: 'u@example.com',
              override_reason: 'Approved exception',
              override_created_at: '2026-05-02T12:00:00Z',
              override_actor: { email: 'admin@test.com' },
            },
          ]}
          onReload={jest.fn()}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('pilot-redemption-recovery-panel')).toBeInTheDocument();
    expect(screen.getByTestId('redemption-row-r1')).toBeInTheDocument();
    expect(screen.getByTestId('redemption-failure-reason')).toHaveTextContent('checkout abandoned');
    expect(screen.getByTestId('allow-retry-r1')).toBeInTheDocument();
    expect(screen.getByTestId('override-row-ov1')).toBeInTheDocument();
    expect(screen.getByTestId('grant-promo-eligibility-btn')).toBeInTheDocument();
  });

  test('invite panel renders empty state', () => {
    render(
      <MemoryRouter>
        <PilotRedemptionRecoverySection
          context="invite"
          inviteCode="PILOTTEST"
          inviteCodeId="inv-1"
          redemptions={[]}
          eligibilityOverrides={[]}
          onReload={jest.fn()}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText(/No redemption attempts recorded/)).toBeInTheDocument();
  });
});
