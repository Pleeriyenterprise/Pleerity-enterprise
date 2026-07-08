import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { InPageCapabilityGate } from './InPageCapabilityGate';
import { LifecycleRuntimeProvider } from '../../contexts/LifecycleRuntimeContext';

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { role: 'ROLE_CLIENT', client_id: 'c1' },
  }),
}));

jest.mock('../../api/client', () => ({
  clientAPI: {
    getLifecycleRuntime: jest.fn(),
  },
}));

const { clientAPI } = require('../../api/client');

function runtimePayload(overrides = {}) {
  return {
    data: {
      lifecycle_runtime: {
        contract_version: '1.0.0',
        runtime_version: 42,
        lifecycle_state: 'SUSPENDED',
        portal_mode: 'SUSPENDED',
        customer_experience: {
          heading: 'Account suspended',
          current_state_label: 'Suspended',
          primary_cta: { label: 'Resolve payment', route: '/settings/billing' },
          secondary_cta: { label: 'Contact support', route: '/support' },
        },
        navigation_policy: { locked_routes: [], read_only_routes: [], hidden_routes: [] },
        polling_policy: { enabled: false },
        warnings: [],
        capabilities: { CAP_TODAY_VIEW: 'DENY' },
        ...overrides,
      },
    },
    headers: {
      'x-lifecycle-contract-version': '1.0.0',
      'x-lifecycle-runtime-version': '42',
    },
  };
}

function renderGate(ui, payload) {
  clientAPI.getLifecycleRuntime.mockResolvedValue(payload || runtimePayload());
  return render(
    <MemoryRouter>
      <LifecycleRuntimeProvider>{ui}</LifecycleRuntimeProvider>
    </MemoryRouter>,
  );
}

describe('InPageCapabilityGate', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows lifecycle denial copy instead of CAP ids when suspended', async () => {
    renderGate(
      <InPageCapabilityGate allowed={false} capabilityId="CAP_TODAY_VIEW" presentationFeature="compliance_dashboard">
        <div>child</div>
      </InPageCapabilityGate>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('in-page-capability-gate')).toBeInTheDocument();
    });
    expect(screen.getByText(/unavailable while your account is suspended/i)).toBeInTheDocument();
    expect(screen.queryByText(/CAP_TODAY_VIEW/)).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Resolve payment' })).toHaveAttribute('href', '/settings/billing');
  });

  it('renders children when allowed', async () => {
    renderGate(
      <InPageCapabilityGate allowed capabilityId="CAP_TODAY_VIEW">
        <div data-testid="gate-child">child</div>
      </InPageCapabilityGate>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('gate-child')).toBeInTheDocument();
    });
  });
});
