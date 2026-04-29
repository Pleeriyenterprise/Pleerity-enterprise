import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AdminClientSupportSearch from './AdminClientSupportSearch';
import * as client from '../../api/client';

jest.mock('./AccountEnvironmentBadge', () => () => null);

const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('AdminClientSupportSearch', () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    mockNavigate.mockClear();
  });

  function renderSearch(ui) {
    return render(<MemoryRouter>{ui}</MemoryRouter>);
  }

  it('shows too-short hint and does not call API', async () => {
    const spy = jest.spyOn(client.adminAPI, 'globalSearch').mockResolvedValue({ data: { results: [] } });
    renderSearch(<AdminClientSupportSearch variant="panel" limit={5} />);
    const input = screen.getByTestId('admin-client-support-search-input');
    fireEvent.change(input, { target: { value: 'a' } });
    expect(await screen.findByTestId('admin-client-support-search-too-short')).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it('calls globalSearch and invokes navigate to control panel on row select', async () => {
    const spy = jest.spyOn(client.adminAPI, 'globalSearch').mockResolvedValue({
      data: {
        results: [
          {
            client_id: 'c-1',
            full_name: 'Test User',
            email: 't@example.com',
            customer_reference: 'PLE-CVP-2026-00001',
            billing_plan: 'PLAN_1_SOLO',
            subscription_status: 'ACTIVE',
            onboarding_status: 'PROVISIONED',
            primary_support_url: '/admin/clients/c-1',
            property_count: 1,
            current_plan_label: 'Solo',
          },
        ],
      },
    });
    renderSearch(<AdminClientSupportSearch variant="panel" limit={5} />);
    const input = screen.getByTestId('admin-client-support-search-input');
    fireEvent.change(input, { target: { value: 'ab' } });
    await waitFor(() => expect(spy).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId('admin-client-support-search-results')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('admin-client-support-search-row-c-1'));
    expect(mockNavigate).toHaveBeenCalledWith('/admin/clients/c-1');
  });

  it('shows error state on API failure', async () => {
    const spy = jest.spyOn(client.adminAPI, 'globalSearch').mockRejectedValue({
      response: { data: { detail: 'Search failed' } },
    });
    renderSearch(<AdminClientSupportSearch variant="panel" limit={5} />);
    fireEvent.change(screen.getByTestId('admin-client-support-search-input'), { target: { value: 'ok' } });
    await waitFor(() => expect(spy).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId('admin-client-support-search-error')).toHaveTextContent('Search failed'));
  });
});
