import React from 'react';
import { render, screen } from '@testing-library/react';
import PortalCardLoading from './PortalCardLoading';

describe('PortalCardLoading', () => {
  it('shows label with status role', () => {
    render(<PortalCardLoading label="Calculating compliance score…" />);
    expect(screen.getByText('Calculating compliance score…')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');
  });
});
