/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import ClientTenantComplianceDeliveryPage from './ClientTenantComplianceDeliveryPage';

const mockHasFeature = jest.fn();
const mockApiGet = jest.fn();

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

jest.mock('../contexts/EntitlementsContext', () => ({
  useEntitlements: () => ({
    hasFeature: (...args) => mockHasFeature(...args),
    entitlementsLoadFailed: false,
    loading: false,
  }),
}));

jest.mock('../components/UpgradePrompt', () => ({
  UpgradeRequired: ({ feature }) => <div data-testid="upgrade-required">upgrade:{feature}</div>,
}));

describe('ClientTenantComplianceDeliveryPage entitlements', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApiGet.mockResolvedValue({ data: { properties: [], tenants: [], items: [], provider_evidence_notice: '' } });
  });

  it('gates page by tenant_portal entitlement', () => {
    mockHasFeature.mockImplementation((f) => f !== 'tenant_portal');
    render(<ClientTenantComplianceDeliveryPage />);

    expect(screen.getByTestId('upgrade-required')).toHaveTextContent('upgrade:tenant_portal');
  });

  it('keeps send action disabled without reports_pdf even when tenant_portal exists', async () => {
    mockHasFeature.mockImplementation((f) => f === 'tenant_portal');
    render(<ClientTenantComplianceDeliveryPage />);

    expect(await screen.findByText(/same as the governed email payload/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send compliance pack/i })).toBeDisabled();
  });
});
