import React from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import InAppNotificationCenter from '../components/notifications/InAppNotificationCenter';
import { adminAPI } from '../api/client';

export default function AdminNotificationInboxPage() {
  return (
    <UnifiedAdminLayout>
      <InAppNotificationCenter
        variant="admin"
        fetchList={(inboxFilter) =>
          adminAPI.getInAppNotifications({ limit: 100, inbox_filter: inboxFilter })
        }
        fetchUnreadCount={() => adminAPI.getInAppNotificationsUnreadCount()}
        markRead={(id) => adminAPI.markInAppNotificationRead(id)}
        markAllRead={() => adminAPI.markAllInAppNotificationsRead()}
        dismiss={(id) => adminAPI.dismissInAppNotification(id)}
      />
    </UnifiedAdminLayout>
  );
}
