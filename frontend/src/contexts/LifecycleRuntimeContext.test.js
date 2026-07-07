import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { LifecycleRuntimeProvider, usePortalMode, useLifecycleRuntime, useCapability } from '../contexts/LifecycleRuntimeContext';
import LifecycleShell, { PortalModePageBanner } from '../components/lifecycle/LifecycleShell';
import { MemoryRouter } from 'react-router-dom';

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { role: 'ROLE_CLIENT', client_id: 'c1' },
  }),
}));

jest.mock('../api/client', () => ({
  clientAPI: {
    getLifecycleRuntime: jest.fn(),
  },
}));

const { clientAPI } = require('../api/client');

const PORTAL_MODES = [
  'FULL_ACCESS',
  'READ_ONLY',
  'GRACE',
  'PAYMENT_REQUIRED',
  'BILLING_RECOVERY',
  'SUSPENDED',
  'ARCHIVED',
  'ACCOUNT_DELETED',
];

function runtimePayload(overrides = {}) {
  return {
    data: {
      lifecycle_runtime: {
        contract_version: '1.0.0',
        runtime_version: 42,
        lifecycle_state: 'ACTIVE',
        portal_mode: 'FULL_ACCESS',
        customer_experience: {
          heading: 'Account active',
          explanation: 'Full access copy',
          current_state_label: 'Active',
          primary_cta: { label: 'Dashboard', route: '/dashboard' },
        },
        navigation_policy: { locked_routes: [], read_only_routes: [], hidden_routes: [] },
        polling_policy: { enabled: false },
        warnings: [],
        capabilities: {},
        ...overrides,
      },
    },
    headers: {
      'x-lifecycle-contract-version': '1.0.0',
      'x-lifecycle-runtime-version': '42',
    },
  };
}

function Probe() {
  const { portalMode } = usePortalMode();
  const { lifecycleState, contractVersion, runtimeVersion } = useLifecycleRuntime();
  return (
    <div data-testid="probe">
      {portalMode}:{lifecycleState}:{contractVersion}:{runtimeVersion}
    </div>
  );
}

function renderWithRuntime(ui, payload) {
  clientAPI.getLifecycleRuntime.mockResolvedValue(payload || runtimePayload());
  return render(
    <MemoryRouter initialEntries={['/documents']}>
      <LifecycleRuntimeProvider>{ui}</LifecycleRuntimeProvider>
    </MemoryRouter>,
  );
}

describe('LifecycleRuntimeProvider', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    clientAPI.getLifecycleRuntime.mockResolvedValue(
      runtimePayload({ portal_mode: 'GRACE', lifecycle_state: 'GRACE_PERIOD' }),
    );
  });

  it('fetches runtime contract once and exposes portal mode', async () => {
    render(
      <LifecycleRuntimeProvider>
        <Probe />
      </LifecycleRuntimeProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('probe')).toHaveTextContent('GRACE:GRACE_PERIOD:1.0.0:42');
    });
    expect(clientAPI.getLifecycleRuntime).toHaveBeenCalled();
  });

  it('uses governed fallback when runtime contract is unavailable', async () => {
    clientAPI.getLifecycleRuntime.mockRejectedValue(new Error('network'));
    render(
      <MemoryRouter>
        <LifecycleRuntimeProvider>
          <LifecycleShell />
        </LifecycleRuntimeProvider>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('lifecycle-runtime-fallback')).toBeInTheDocument();
    });
  });

  it('reads version metadata from response headers', async () => {
    render(
      <LifecycleRuntimeProvider>
        <Probe />
      </LifecycleRuntimeProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('probe')).toHaveTextContent('1.0.0:42');
    });
  });

  it('exposes runtime capabilities and useCapability hook', async () => {
    clientAPI.getLifecycleRuntime.mockResolvedValue(
      runtimePayload({
        capabilities: {
          CAP_DOC_VIEW: 'READ',
          CAP_DOC_UPLOAD: 'ALLOW',
          CAP_BILLING_VIEW: 'DENY',
        },
      }),
    );

    function CapabilityProbe() {
      const docRead = useCapability('CAP_DOC_VIEW', 'read');
      const docWrite = useCapability('CAP_DOC_VIEW', 'write');
      const billing = useCapability('CAP_BILLING_VIEW', 'read');
      const { capabilityAllowed } = useLifecycleRuntime();
      return (
        <div data-testid="cap-probe">
          {docRead.allowed ? 'doc-read' : 'no-doc-read'}:
          {docWrite.allowed ? 'doc-write' : 'no-doc-write'}:
          {billing.allowed ? 'billing' : 'no-billing'}:
          {capabilityAllowed('CAP_DOC_UPLOAD', 'write') ? 'upload' : 'no-upload'}
        </div>
      );
    }

    render(
      <LifecycleRuntimeProvider>
        <CapabilityProbe />
      </LifecycleRuntimeProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('cap-probe')).toHaveTextContent(
        'doc-read:no-doc-write:no-billing:upload',
      );
    });
  });
});

describe.each(PORTAL_MODES)('LifecycleShell portal mode %s', (portalMode) => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders governed customer experience', async () => {
    const heading = `${portalMode} heading`;
    renderWithRuntime(
      <LifecycleShell />,
      runtimePayload({
        portal_mode: portalMode,
        lifecycle_state: portalMode,
        customer_experience: {
          heading,
          explanation: `${portalMode} explanation`,
          current_state_label: portalMode,
          primary_cta: { label: 'Primary', route: '/settings/billing' },
          secondary_cta: { label: 'Support', route: '/help' },
        },
      }),
    );

    await waitFor(() => {
      expect(screen.getByTestId(`lifecycle-shell-${portalMode}`)).toBeInTheDocument();
    });
    if (portalMode !== 'FULL_ACCESS') {
      expect(screen.getByText(heading)).toBeInTheDocument();
    }
  });
});

describe('LifecycleShell presentation modes', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders read-only badge for READ_ONLY mode', async () => {
    renderWithRuntime(
      <LifecycleShell />,
      runtimePayload({
        portal_mode: 'READ_ONLY',
        customer_experience: {
          heading: 'View only',
          explanation: 'Read-only presentation',
          current_state_label: 'Read only',
        },
      }),
    );
    await waitFor(() => {
      expect(screen.getByTestId('lifecycle-shell-READ_ONLY')).toBeInTheDocument();
    });
    expect(screen.getByRole('heading', { name: 'View only' })).toBeInTheDocument();
  });

  it('renders payment recovery and archive copy from customer_experience', async () => {
    renderWithRuntime(
      <LifecycleShell />,
      runtimePayload({
        portal_mode: 'BILLING_RECOVERY',
        customer_experience: {
          heading: 'Billing recovery',
          explanation: 'Update your payment method',
          recovery_guidance: 'Retry payment in billing settings',
        },
      }),
    );
    await waitFor(() => {
      expect(screen.getByText('Billing recovery')).toBeInTheDocument();
    });
    expect(screen.getByText(/Update your payment method/)).toBeInTheDocument();
    expect(screen.getByText(/Retry payment in billing settings/)).toBeInTheDocument();
  });

  it('does not crash when customer_experience fields are non-string objects', async () => {
    renderWithRuntime(
      <LifecycleShell />,
      runtimePayload({
        portal_mode: 'SUSPENDED',
        customer_experience: {
          heading: 'Account suspended',
          explanation: { nested: 'bad' },
          reason: { code: 'SUSPENDED' },
          primary_cta: { label: { bad: true }, route: '/settings/billing' },
        },
      }),
    );
    await waitFor(() => {
      expect(screen.getByTestId('lifecycle-shell-SUSPENDED')).toBeInTheDocument();
    });
    expect(screen.getByRole('heading', { name: 'Account suspended' })).toBeInTheDocument();
  });
});

describe('PortalModePageBanner', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('is hidden for FULL_ACCESS', async () => {
    renderWithRuntime(<PortalModePageBanner />, runtimePayload({ portal_mode: 'FULL_ACCESS' }));
    await waitFor(() => {
      expect(screen.queryByTestId('portal-mode-page-banner')).not.toBeInTheDocument();
    });
  });

  it('shows runtime customer_experience label for non-full modes', async () => {
    renderWithRuntime(
      <PortalModePageBanner />,
      runtimePayload({
        portal_mode: 'ARCHIVED',
        customer_experience: { current_state_label: 'Archived account' },
      }),
    );
    await waitFor(() => {
      expect(screen.getByTestId('portal-mode-page-banner')).toHaveTextContent('Archived account');
    });
  });
});
