import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LifecycleKpiAttentionStrip from './LifecycleKpiAttentionStrip';

describe('LifecycleKpiAttentionStrip', () => {
  it('renders nothing without breakdown', () => {
    const { container } = render(
      <MemoryRouter>
        <LifecycleKpiAttentionStrip stats={{ expiring_soon: 1 }} />
      </MemoryRouter>,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders bucket chips when breakdown present', () => {
    render(
      <MemoryRouter>
        <LifecycleKpiAttentionStrip
          stats={{
            lifecycle_kpi_effective_mode: 'shadow',
            lifecycle_kpi_breakdown: {
              certificate_expiring: 1,
              review_due: 2,
              event_action_required: 0,
              tenancy_term_ending: 0,
              occupancy_review_due: 0,
              operational_action_required: 0,
            },
          }}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('lifecycle-kpi-attention-strip')).toBeInTheDocument();
    expect(screen.getByTestId('lifecycle-kpi-bucket-certificate_expiring')).toHaveTextContent('1');
    expect(screen.getByTestId('lifecycle-kpi-bucket-review_due')).toHaveTextContent('2');
  });
});
