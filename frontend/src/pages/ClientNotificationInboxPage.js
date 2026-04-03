import React from 'react';
import InAppNotificationCenter from '../components/notifications/InAppNotificationCenter';
import { clientAPI } from '../api/client';

export default function ClientNotificationInboxPage() {
  return (
    <InAppNotificationCenter
      variant="client"
      fetchList={(inboxFilter) =>
        clientAPI.getInAppNotifications({ limit: 100, inbox_filter: inboxFilter })
      }
      fetchUnreadCount={() => clientAPI.getInAppNotificationsUnreadCount()}
      markRead={(id) => clientAPI.markInAppNotificationRead(id)}
      markAllRead={() => clientAPI.markAllInAppNotificationsRead()}
      dismiss={(id) => clientAPI.dismissInAppNotification(id)}
    />
  );
}
