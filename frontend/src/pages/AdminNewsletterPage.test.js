import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import AdminNewsletterPage from './AdminNewsletterPage';

jest.mock('../components/admin/UnifiedAdminLayout', () => ({ children }) => <div>{children}</div>);

const mockListNewsletterSubscribers = jest.fn();

jest.mock('../api/client', () => ({
  adminAPI: {
    listNewsletterSubscribers: (...args) => mockListNewsletterSubscribers(...args),
  },
}));

describe('AdminNewsletterPage', () => {
  beforeEach(() => {
    mockListNewsletterSubscribers.mockReset();
  });

  it('renders subscribers from authenticated admin API', async () => {
    mockListNewsletterSubscribers.mockResolvedValue({
      data: [
        {
          subscriber_id: 's1',
          email: 'audit@yopmail.com',
          status: 'SUBSCRIBED',
          source: 'newsletter_page',
          kit_sync_status: 'SYNCED',
          subscribed_at: '2026-06-06T12:00:00Z',
        },
      ],
    });
    render(<AdminNewsletterPage />);
    await waitFor(() => {
      expect(screen.getByText('audit@yopmail.com')).toBeInTheDocument();
    });
    expect(screen.getByText(/1 total subscribers/i)).toBeInTheDocument();
  });

  it('shows auth error instead of empty state on 401', async () => {
    mockListNewsletterSubscribers.mockRejectedValue({
      response: { status: 401, data: { detail: 'Unauthorized' } },
    });
    render(<AdminNewsletterPage />);
    await waitFor(() => {
      expect(screen.getByText(/session expired/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/no subscribers yet/i)).not.toBeInTheDocument();
  });
});
