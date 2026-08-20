import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import InAppNotificationCenter from './InAppNotificationCenter';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
}));

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

jest.mock('../ui/button', () => ({
  Button: ({ children, ...props }) => <button {...props}>{children}</button>,
}));

const item = {
  notification_id: 'N1',
  title: 'Quote ready',
  message: 'A quote needs review',
  is_read: false,
  created_at: '2026-08-19T12:00:00Z',
  severity: 'medium',
};

describe('InAppNotificationCenter', () => {
  it('renders list items when fetch succeeds', async () => {
    render(
      <InAppNotificationCenter
        variant="client"
        fetchList={() => Promise.resolve({ data: { items: [item], unread_count: 1 } })}
        fetchUnreadCount={() => Promise.resolve({ data: { unread_count: 1 } })}
        markRead={jest.fn()}
        markAllRead={jest.fn()}
        dismiss={jest.fn()}
      />,
    );
    expect(await screen.findByText('Quote ready')).toBeInTheDocument();
  });

  it('does not use empty-state copy when list fetch fails', async () => {
    render(
      <InAppNotificationCenter
        variant="client"
        fetchList={() => Promise.reject(new Error('fail'))}
        fetchUnreadCount={() => Promise.resolve({ data: { unread_count: 1 } })}
        markRead={jest.fn()}
        markAllRead={jest.fn()}
        dismiss={jest.fn()}
      />,
    );
    expect(await screen.findByText(/couldn't load notifications/i)).toBeInTheDocument();
    expect(screen.queryByText('No notifications')).not.toBeInTheDocument();
  });

  it('marks one notification read', async () => {
    const markRead = jest.fn(() => Promise.resolve({}));
    render(
      <InAppNotificationCenter
        variant="client"
        fetchList={() => Promise.resolve({ data: { items: [item], unread_count: 1 } })}
        fetchUnreadCount={() => Promise.resolve({ data: { unread_count: 1 } })}
        markRead={markRead}
        markAllRead={jest.fn()}
        dismiss={jest.fn()}
      />,
    );
    fireEvent.click(await screen.findByText('Quote ready'));
    await waitFor(() => expect(markRead).toHaveBeenCalledWith('N1'));
  });

  it('dismisses an unread item', async () => {
    const dismiss = jest.fn(() => Promise.resolve({}));
    render(
      <InAppNotificationCenter
        variant="client"
        fetchList={() => Promise.resolve({ data: { items: [item], unread_count: 1 } })}
        fetchUnreadCount={() => Promise.resolve({ data: { unread_count: 0 } })}
        markRead={jest.fn()}
        markAllRead={jest.fn()}
        dismiss={dismiss}
      />,
    );
    fireEvent.click(await screen.findByTitle('Dismiss'));
    await waitFor(() => expect(dismiss).toHaveBeenCalledWith('N1'));
  });
});
