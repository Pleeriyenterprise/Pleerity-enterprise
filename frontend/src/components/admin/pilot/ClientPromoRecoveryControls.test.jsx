import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ClientPromoRecoveryControls from './ClientPromoRecoveryControls';

jest.mock('../../../hooks/usePilotAccountRecovery', () => ({
  usePilotAccountRecovery: jest.fn(),
}));

jest.mock('./PilotRedemptionRecoverySection', () => ({
  __esModule: true,
  default: () => <div data-testid="mock-recovery-section">Recovery section</div>,
}));

jest.mock('./PromoRecoveryStateSummary', () => ({
  __esModule: true,
  default: () => <div data-testid="mock-state-summary">State summary</div>,
}));

const { usePilotAccountRecovery } = require('../../../hooks/usePilotAccountRecovery');

describe('ClientPromoRecoveryControls', () => {
  beforeEach(() => {
    usePilotAccountRecovery.mockReset();
  });

  it('hidden when no promo history', () => {
    usePilotAccountRecovery.mockReturnValue({
      loading: false,
      error: null,
      reload: jest.fn(),
      showRecoveryPanel: false,
      redemptions: [],
      eligibilityOverrides: [],
      overrideHistory: [],
      waiverHistory: [],
      indicators: {},
      inviteMetadata: {},
      latestRedemption: null,
      strandedCount: 0,
    });
    const { container } = render(
      <MemoryRouter>
        <ClientPromoRecoveryControls clientId="plain" />
      </MemoryRouter>,
    );
    expect(container.querySelector('[data-testid="client-promo-recovery-controls"]')).toBeNull();
  });

  it('shows waiver and retry controls for stranded intake user', async () => {
    usePilotAccountRecovery.mockReturnValue({
      loading: false,
      error: null,
      reload: jest.fn(),
      showRecoveryPanel: true,
      redemptions: [
        {
          redemption_id: 'r1',
          status: 'provisioning_failed',
          retry_eligible: false,
          failure_reason: 'provision timeout',
        },
      ],
      eligibilityOverrides: [],
      overrideHistory: [],
      waiverHistory: [],
      indicators: { stranded_onboarding: true, badges: ['provisioning_failed'] },
      inviteMetadata: { pilot_invite_code: 'FOUNDING2026', onboarding_status: 'INTAKE_PENDING' },
      latestRedemption: { status: 'provisioning_failed', retry_eligible: false },
      strandedCount: 1,
    });
    render(
      <MemoryRouter>
        <ClientPromoRecoveryControls
          clientId="intake-1"
          accountHints={{ onboarding_stage: 'INTAKE_PENDING' }}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('client-promo-recovery-controls')).toBeInTheDocument();
    expect(screen.getByText(/Promo & Recovery Controls/)).toBeInTheDocument();
    expect(screen.getByTestId('mock-state-summary')).toBeInTheDocument();
    expect(screen.getByTestId('mock-recovery-section')).toBeInTheDocument();
  });

  it('shows structured API errors without crashing', () => {
    usePilotAccountRecovery.mockReturnValue({
      loading: false,
      error: { error_code: 'FORBIDDEN', message: 'Insufficient permissions' },
      reload: jest.fn(),
      showRecoveryPanel: false,
      redemptions: [],
      eligibilityOverrides: [],
      overrideHistory: [],
      waiverHistory: [],
      indicators: {},
      inviteMetadata: {},
      latestRedemption: null,
      strandedCount: 0,
    });
    render(
      <MemoryRouter>
        <ClientPromoRecoveryControls clientId="err-client" />
      </MemoryRouter>,
    );
    expect(screen.getByText('Insufficient permissions')).toBeInTheDocument();
  });

  it('expands collapsible section on click', () => {
    usePilotAccountRecovery.mockReturnValue({
      loading: false,
      error: null,
      reload: jest.fn(),
      showRecoveryPanel: true,
      redemptions: [],
      eligibilityOverrides: [{ override_id: 'ov1', override_type: 'bypass_first_time', scope: 'email', scope_value: 'u@x.com', override_reason: 'ok', override_created_at: '2026-01-01' }],
      overrideHistory: [{ override_id: 'ov1', override_type: 'bypass_first_time', scope: 'email', scope_value: 'u@x.com', override_reason: 'ok', override_created_at: '2026-01-01' }],
      waiverHistory: [],
      indicators: { override_active: true },
      inviteMetadata: { pilot_invite_code: 'CODE' },
      latestRedemption: null,
      strandedCount: 0,
    });
    render(
      <MemoryRouter>
        <ClientPromoRecoveryControls clientId="override-only" />
      </MemoryRouter>,
    );
    const toggle = screen.getByRole('button', { name: /Promo & Recovery Controls/i });
    fireEvent.click(toggle);
    expect(screen.getByTestId('mock-recovery-section')).toBeInTheDocument();
  });
});
