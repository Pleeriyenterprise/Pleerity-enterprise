/**
 * NotificationBell - Admin notification bell with dropdown
 * 
 * Features:
 * - Shows unread count badge
 * - Dropdown with recent notifications
 * - Mark as read functionality
 * - Click to navigate to related order
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '../ui/popover';
import {
  Bell,
  Check,
  CheckCheck,
  Package,
  AlertTriangle,
  Clock,
} from 'lucide-react';
import { cn } from '../../lib/utils';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Polling interval for notifications (30 seconds)
const POLL_INTERVAL = 30000;

/**
 * Format date for display
 */
const formatTimeAgo = (dateString) => {
  if (!dateString) return '';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
};

/**
 * Get icon component based on notification priority/type
 */
const NotificationIcon = ({ notification }) => {
  const priority = notification.priority;
  if (priority === 'urgent' || priority === 'high') {
    return <AlertTriangle className="h-4 w-4" />;
  }
  if (notification.order_id) {
    return <Package className="h-4 w-4" />;
  }
  return <Bell className="h-4 w-4" />;
};

/**
 * Get priority color
 */
const getPriorityClass = (priority) => {
  switch (priority) {
    case 'urgent':
      return 'bg-red-100 text-red-800 border-red-200';
    case 'high':
      return 'bg-orange-100 text-orange-800 border-orange-200';
    case 'medium':
      return 'bg-blue-100 text-blue-800 border-blue-200';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-200';
  }
};

/**
 * Single notification item
 */
const NotificationItem = ({ notification, onRead, onClick }) => {
  const priorityClass = getPriorityClass(notification.priority);

  return (
    <div
      className={cn(
        'p-3 border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors',
        !notification.is_read && 'bg-blue-50/50'
      )}
      onClick={() => {
        if (!notification.is_read) onRead(notification.notification_id);
        onClick(notification);
      }}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
            priorityClass
          )}
        >
          <NotificationIcon notification={notification} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <p
              className={cn(
                'text-sm font-medium truncate',
                !notification.is_read && 'text-gray-900',
                notification.is_read && 'text-gray-600'
              )}
            >
              {notification.title}
            </p>
            {!notification.is_read && (
              <span className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0" />
            )}
          </div>
          <p className="text-xs text-gray-500 truncate mt-0.5">
            {notification.message}
          </p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-gray-400 flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatTimeAgo(notification.created_at)}
            </span>
            {notification.order_id && (
              <Badge variant="outline" className="text-xs py-0">
                {notification.order_id}
              </Badge>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * Main NotificationBell component
 */
const NotificationBell = () => {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const getAuthHeaders = () => {
    const token = localStorage.getItem('auth_token');
    return {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
    };
  };

  const fetchNotifications = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/admin/notifications/?limit=20`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setNotifications(data.notifications || []);
        setUnreadCount(data.unread_count || 0);
      }
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
    }
  }, []);

  const fetchUnreadCount = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/admin/notifications/unread-count`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setUnreadCount(data.unread_count || 0);
      }
    } catch (error) {
      console.error('Failed to fetch unread count:', error);
    }
  }, []);

  const markAsRead = async (notificationId) => {
    try {
      await fetch(`${API_URL}/api/admin/notifications/${notificationId}/read`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      setUnreadCount((prev) => Math.max(0, prev - 1));
      setNotifications((prev) =>
        prev.map((n) =>
          n.notification_id === notificationId ? { ...n, is_read: true } : n
        )
      );
    } catch (error) {
      console.error('Failed to mark notification as read:', error);
    }
  };

  const markAllAsRead = async () => {
    try {
      await fetch(`${API_URL}/api/admin/notifications/read-all`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      setUnreadCount(0);
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch (error) {
      console.error('Failed to mark all as read:', error);
    }
  };

  const handleNotificationClick = (notification) => {
    setIsOpen(false);
    if (notification.order_id) {
      navigate(`/admin/orders?order=${notification.order_id}`);
    }
  };

  // Fetch on mount and when popover opens
  useEffect(() => {
    fetchUnreadCount();
  }, [fetchUnreadCount]);

  useEffect(() => {
    if (isOpen) {
      fetchNotifications();
    }
  }, [isOpen, fetchNotifications]);

  // Poll for unread count
  useEffect(() => {
    const interval = setInterval(fetchUnreadCount, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="relative text-gray-300 hover:text-white hover:bg-white/10"
          data-testid="notification-bell"
        >
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 h-5 w-5 bg-red-500 text-white text-xs font-medium rounded-full flex items-center justify-center">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0" align="end">
        <div className="p-3 border-b border-gray-200 flex items-center justify-between">
          <h4 className="font-semibold text-sm">Notifications</h4>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 text-xs text-blue-600 hover:text-blue-700"
              onClick={markAllAsRead}
            >
              <CheckCheck className="h-3 w-3 mr-1" />
              Mark all read
            </Button>
          )}
        </div>

        <ScrollArea className="h-[350px]">
          {notifications.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <Bell className="h-8 w-8 mx-auto mb-2 opacity-40" />
              <p className="text-sm">No notifications</p>
            </div>
          ) : (
            notifications.map((notification) => (
              <NotificationItem
                key={notification.notification_id}
                notification={notification}
                onRead={markAsRead}
                onClick={handleNotificationClick}
              />
            ))
          )}
        </ScrollArea>

        {notifications.length > 0 && (
          <div className="p-2 border-t border-gray-200">
            <Button
              variant="ghost"
              className="w-full text-sm text-gray-600 hover:text-gray-900"
              onClick={() => {
                setIsOpen(false);
                navigate('/admin/notifications');
              }}
            >
              View all notifications
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
};

export default NotificationBell;
