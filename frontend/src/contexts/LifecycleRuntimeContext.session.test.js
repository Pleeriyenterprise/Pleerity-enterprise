import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { LifecycleRuntimeProvider, useLifecycleRuntime } from '../contexts/LifecycleRuntimeContext';

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { role: 'ROLE_CLIENT', client_id: 'c1', portal_user_id: 'pu1' },
    loginWithToken: jest.fn(),
    logout: jest.fn(),
  }),
}));

jest.mock('../api/client', () => ({
  clientAPI: {
    getLifecycleRuntime: jest.fn(),
    refreshSessionRuntime: jest.fn(),
  },
}));

jest.mock('../utils/sessionRuntimeSync', () => ({
  broadcastRuntimeInvalidation: jest.fn(),
  isDocumentOnline: () => true,
  subscribeSessionRuntimeSync: () => () => {},
}));

const { clientAPI } = require('../api/client');

function Probe() {
  const { refreshSession } = useLifecycleRuntime();
  return (
    <button type="button" onClick={() => refreshSession('manual')}>
      refresh
    </button>
  );
}

describe('LifecycleRuntimeProvider session refresh', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    clientAPI.getLifecycleRuntime.mockResolvedValue({
      data: {
        lifecycle_runtime: {
          contract_version: '1.0.0',
          runtime_version: 10,
          portal_mode: 'FULL_ACCESS',
          capabilities: {},
          polling_policy: { enabled: false },
        },
      },
      headers: {},
    });
    clientAPI.refreshSessionRuntime.mockResolvedValue({
      data: {
        lifecycle_runtime: {
          contract_version: '1.0.0',
          runtime_version: 11,
          portal_mode: 'BILLING_RECOVERY',
          capabilities: { CAP_BILLING_VIEW: 'READ' },
          polling_policy: { enabled: false },
        },
        session_runtime: {
          session_id: 'sess-xyz',
          runtime_version: 11,
          entitlements_version: 2,
        },
      },
    });
  });

  it('refreshSession calls session-runtime refresh endpoint', async () => {
    jest.useFakeTimers();
    render(
      <LifecycleRuntimeProvider>
        <Probe />
      </LifecycleRuntimeProvider>,
    );

    await waitFor(() => {
      expect(clientAPI.getLifecycleRuntime).toHaveBeenCalled();
    });

    jest.advanceTimersByTime(6000);
    fireEvent.click(screen.getByRole('button', { name: 'refresh' }));

    await waitFor(() => {
      expect(clientAPI.refreshSessionRuntime).toHaveBeenCalledWith('manual');
    });
    jest.useRealTimers();
  });
});
