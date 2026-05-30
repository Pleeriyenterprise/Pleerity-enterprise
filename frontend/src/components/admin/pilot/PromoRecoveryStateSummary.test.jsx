import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PromoRecoveryStateSummary from './PromoRecoveryStateSummary';

describe('PromoRecoveryStateSummary', () => {
  it('renders invite link and status badge as JSX, not stringified objects', () => {
    render(
      <MemoryRouter>
        <PromoRecoveryStateSummary
          inviteCode="FOUNDING2026"
          latestRedemption={{ status: 'provisioning_failed', retry_eligible: false }}
          inviteMetadata={{ campaign_name: 'Pilot campaign' }}
        />
      </MemoryRouter>,
    );

    const link = screen.getByRole('link', { name: 'FOUNDING2026' });
    expect(link).toHaveAttribute('href', '/admin/pilot-invites/FOUNDING2026');
    expect(screen.getByText('provisioning_failed')).toBeInTheDocument();
    expect(screen.getByText('Pilot campaign')).toBeInTheDocument();
    expect(screen.queryByText(/"\$\$typeof"/)).toBeNull();
  });

  it('stringifies structured API error objects in text fields', () => {
    render(
      <MemoryRouter>
        <PromoRecoveryStateSummary
          accountHints={{
            onboarding_stage: { error_code: 'X', message: 'Blocked onboarding' },
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText('Blocked onboarding')).toBeInTheDocument();
  });
});
