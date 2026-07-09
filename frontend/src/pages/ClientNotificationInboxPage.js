import React from 'react';
import InAppNotificationCenter from '../components/notifications/InAppNotificationCenter';
import { clientAPI } from '../api/client';
import { useProfileCapabilities } from '../utils/accountCapabilityAccess';

export default function ClientNotificationInboxPage() {
  const { canEditProfile } = useProfileCapabilities();

  return (
    <InAppNotificationCenter
      variant="client"
      canMarkRead={canEditProfile}
      canDismiss={canEditProfile}
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
