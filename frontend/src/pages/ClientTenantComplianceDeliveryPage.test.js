/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import ClientTenantComplianceDeliveryPage from './ClientTenantComplianceDeliveryPage';

const mockApiGet = jest.fn();
const mockCanViewTenantDeliveries = jest.fn(() => true);
const mockCanSendTenantDelivery = jest.fn(() => false);

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useSearchParams: () => [new URLSearchParams(''), jest.fn()],
  };
});

jest.mock('../api/client', () => ({
  __esModule: true,
  default: {
    get: (...args) => mockApiGet(...args),
    post: jest.fn(),
  },
}));

jest.mock('../contexts/LifecycleRuntimeContext', () => ({
  useLifecycleRuntime: () => ({
    loading: false,
    capabilityAllowed: () => true,
  }),
}));

jest.mock('../utils/tenantCapabilityAccess', () => ({
  useTenantCapabilities: () => ({
    canViewTenantDeliveries: mockCanViewTenantDeliveries(),
    canSendTenantDelivery: mockCanSendTenantDelivery(),
  }),
}));

jest.mock('../components/UpgradePrompt', () => ({
  UpgradeRequired: ({ feature }) => <div data-testid="upgrade-required">upgrade:{feature}</div>,
}));

describe('ClientTenantComplianceDeliveryPage capabilities', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCanViewTenantDeliveries.mockReturnValue(true);
    mockCanSendTenantDelivery.mockReturnValue(false);
    mockApiGet.mockResolvedValue({ data: { properties: [], tenants: [], items: [], provider_evidence_notice: '' } });
  });

  it('gates page when tenant manage read capability is denied', () => {
    mockCanViewTenantDeliveries.mockReturnValue(false);
    render(<ClientTenantComplianceDeliveryPage />);

    expect(screen.getByTestId('upgrade-required')).toHaveTextContent('upgrade:tenant_portal');
  });

  it('keeps send action disabled without report generate write even when tenant delivery read is allowed', async () => {
    render(<ClientTenantComplianceDeliveryPage />);

    expect(await screen.findByText(/PDF report generation/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send compliance pack/i })).toBeDisabled();
  });
});
