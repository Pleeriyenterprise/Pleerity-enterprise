import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, CheckCheck, ExternalLink, Inbox, Trash2 } from 'lucide-react';
import { Button } from '../ui/button';
import { cn } from '../../lib/utils';
import { resolveNotificationTarget, severityBadgeClass } from '../../utils/notificationDeepLink';

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'unread', label: 'Unread' },
  { id: 'critical', label: 'Critical' },
  { id: 'compliance', label: 'Compliance' },
  { id: 'billing', label: 'Billing' },
  { id: 'operations', label: 'Operations' },
  { id: 'system', label: 'System' },
];

function formatTimeAgo(dateString) {
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
}

/**
 * @param {object} props
 * @param {'admin'|'client'} props.variant
 * @param {() => Promise<{ data: { notifications?: object[], items?: object[], unread_count?: number } }>} props.fetchList
 * @param {() => Promise<{ data: { unread_count: number } }>} props.fetchUnreadCount
 * @param {(id: string) => Promise<unknown>} props.markRead
 * @param {() => Promise<unknown>} props.markAllRead
 * @param {(id: string) => Promise<unknown>} props.dismiss
 */
export default function InAppNotificationCenter({
  variant,
  fetchList,
  fetchUnreadCount,
  markRead,
  markAllRead,
  dismiss,
  canMarkRead = true,
  canDismiss = true,
}) {
  const navigate = useNavigate();
  const isAdmin = variant === 'admin';
  const [filter, setFilter] = useState('all');
  const [items, setItems] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchList(filter);
      const raw = isAdmin ? res.data?.notifications : res.data?.items;
      setItems(Array.isArray(raw) ? raw : []);
      const uc = res.data?.unread_count;
      if (typeof uc === 'number') setUnreadCount(uc);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [fetchList, filter, isAdmin]);

  const refreshUnread = useCallback(async () => {
    try {
      const r = await fetchUnreadCount();
      const n = r.data?.unread_count;
      if (typeof n === 'number') setUnreadCount(n);
    } catch {
      /* ignore */
    }
  }, [fetchUnreadCount]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    refreshUnread();
  }, [refreshUnread, items]);

  const onOpen = async (n) => {
    const id = n.notification_id;
    if (!id) return;
    try {
      if (!n.is_read && canMarkRead) {
        await markRead(id);
        setItems((prev) => prev.map((x) => (x.notification_id === id ? { ...x, is_read: true } : x)));
        setUnreadCount((c) => Math.max(0, c - 1));
      }
    } catch {
      /* ignore */
    }
    const { href, external } = resolveNotificationTarget(n, isAdmin);
    if (external) window.open(href, '_blank', 'noopener,noreferrer');
    else navigate(href);
  };

  const onDismiss = async (e, n) => {
    e.preventDefault();
    e.stopPropagation();
    if (!canDismiss) return;
    const id = n.notification_id;
    if (!id) return;
    try {
      await dismiss(id);
      setItems((prev) => prev.filter((x) => x.notification_id !== id));
      if (!n.is_read) setUnreadCount((c) => Math.max(0, c - 1));
      refreshUnread();
    } catch {
      /* ignore */
    }
  };

  const onMarkAll = async () => {
    if (!canMarkRead) return;
    try {
      await markAllRead();
      setItems((prev) => prev.map((x) => ({ ...x, is_read: true })));
      setUnreadCount(0);
      refreshUnread();
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Inbox className="h-7 w-7 text-midnight-blue" />
            Notification center
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            {unreadCount > 0 ? `${unreadCount} unread` : 'You are up to date'}
          </p>
        </div>
        {unreadCount > 0 && canMarkRead && (
          <Button variant="outline" size="sm" onClick={onMarkAll} className="shrink-0">
            <CheckCheck className="h-4 w-4 mr-2" />
            Mark all as read
          </Button>
        )}
      </div>

      <div className="flex flex-wrap gap-2 mb-6">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setFilter(f.id)}
            className={cn(
              'px-3 py-1.5 rounded-full text-sm font-medium border transition-colors',
              filter === f.id
                ? 'bg-midnight-blue text-white border-midnight-blue'
                : 'bg-white text-gray-700 border-gray-200 hover:border-gray-300'
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-gray-500 text-sm">Loading…</p>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50/80 py-16 text-center text-gray-500">
          <Bell className="h-10 w-10 mx-auto mb-3 opacity-40" />
          <p className="font-medium text-gray-700">No notifications</p>
          <p className="text-sm mt-1">When something needs your attention, it will appear here.</p>
        </div>
      ) : (
        <ul className="space-y-2">
          {items.map((n) => (
            <li key={n.notification_id}>
              <div
                role="button"
                tabIndex={0}
                onClick={() => onOpen(n)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onOpen(n);
                  }
                }}
                className={cn(
                  'w-full text-left rounded-lg border p-4 transition-colors hover:bg-gray-50 flex gap-3 cursor-pointer',
                  !n.is_read ? 'border-electric-teal/40 bg-slate-50/60' : 'border-gray-100 bg-white'
                )}
              >
                <div className="shrink-0 pt-0.5">
                  <span
                    className={cn(
                      'inline-flex text-[10px] uppercase tracking-wide font-semibold px-2 py-0.5 rounded border',
                      severityBadgeClass(n.severity)
                    )}
                  >
                    {n.severity || 'medium'}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className={cn('font-medium text-gray-900', !n.is_read && 'text-gray-950')}>
                      {n.title || '—'}
                    </p>
                    {canDismiss ? (
                    <button
                      type="button"
                      className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 shrink-0"
                      title="Dismiss"
                      onClick={(e) => onDismiss(e, n)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                    ) : null}
                  </div>
                  {n.message ? (
                    <p className="text-sm text-gray-600 mt-1 line-clamp-3">{n.message}</p>
                  ) : null}
                  <div className="flex flex-wrap items-center gap-2 mt-2 text-xs text-gray-400">
                    <span>{formatTimeAgo(n.created_at)}</span>
                    {n.notification_category ? (
                      <span className="text-gray-500 capitalize">{n.notification_category}</span>
                    ) : null}
                  </div>
                  {(n.primary_cta_label || n.primary_cta_path || n.link) && (
                    <div className="mt-3 flex items-center gap-2 text-sm text-electric-teal font-medium pointer-events-none">
                      <span>{n.primary_cta_label || 'Open'}</span>
                      <ExternalLink className="h-3.5 w-3.5" />
                    </div>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
