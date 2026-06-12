import React from 'react';
import { render, screen } from '@testing-library/react';
import PortalLoadingState from './PortalLoadingState';
import { todayLoadingStages } from './portalLoadingStageModels';

describe('PortalLoadingState', () => {
  it('renders title, stages, and accessibility status', () => {
    render(
      <PortalLoadingState
        title="Loading your operational inbox…"
        stages={todayLoadingStages()}
        testId="portal-loading-test"
      />,
    );
    expect(screen.getByTestId('portal-loading-test')).toBeInTheDocument();
    expect(screen.getByText(/Loading your operational inbox/)).toBeInTheDocument();
    expect(screen.getByText('Checking requirements')).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders footer note by default', () => {
    render(<PortalLoadingState title="Working…" stages={[]} />);
    expect(screen.getByText(/Large portfolios may take a little longer/)).toBeInTheDocument();
  });
});
