import React from 'react';
import { renderHook } from '@testing-library/react';
import { usePortfolioUsageContext } from './usePortfolioUsageContext';

jest.mock('../api/client', () => ({
  clientAPI: {
    getEntitlementsContext: jest.fn(),
  },
}));

jest.mock('../contexts/LifecycleRuntimeContext', () => ({
  useLifecycleRuntime: jest.fn(),
}));

const { clientAPI } = require('../api/client');
const { useLifecycleRuntime } = require('../contexts/LifecycleRuntimeContext');

describe('usePortfolioUsageContext', () => {
  beforeEach(() => {
    clientAPI.getEntitlementsContext.mockReset();
    useLifecycleRuntime.mockReturnValue({
      runtime: {
        lifecycle_state: 'ACTIVE',
        plan: { plan_code: 'PLAN_1_SOLO', plan_name: 'Solo', max_properties: 2 },
      },
      runtimeAvailable: true,
      loading: false,
      refetch: jest.fn(),
    });
  });

  it('does not call legacy entitlements context API', () => {
    const { result } = renderHook(() => usePortfolioUsageContext());
    expect(clientAPI.getEntitlementsContext).not.toHaveBeenCalled();
    expect(result.current.usageContext).toBeNull();
  });

  it('maps plan material from lifecycle runtime when client user present', () => {
    jest.spyOn(React, 'useContext').mockReturnValue({
      user: { role: 'ROLE_CLIENT', client_id: 'cli-1' },
    });
    const { result } = renderHook(() => usePortfolioUsageContext());
    expect(clientAPI.getEntitlementsContext).not.toHaveBeenCalled();
    expect(result.current.usageContext).toMatchObject({
      plan: 'PLAN_1_SOLO',
      plan_name: 'Solo',
      max_properties: 2,
    });
    React.useContext.mockRestore();
  });
});
