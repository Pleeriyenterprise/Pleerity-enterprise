/**
 * Resolve in-app notification navigation target (admin vs client portal).
 * Prefer server-provided primary_cta_path / link; fall back to related_entity_*.
 */

export function resolveNotificationTarget(notification, isAdmin) {
  const n = notification || {};
  const path = n.primary_cta_path || n.link;
  if (path && /^https?:\/\//i.test(path)) {
    return { href: path, external: true };
  }
  if (path && typeof path === 'string' && path.startsWith('/')) {
    return { href: path, external: false };
  }

  const type = String(n.related_entity_type || '').toLowerCase();
  const id = n.related_entity_id || n.order_id;

  if (isAdmin) {
    if (type === 'order' && id) {
      return { href: `/admin/orders?order=${encodeURIComponent(id)}`, external: false };
    }
    if (type === 'provisioning_job') {
      return { href: '/admin/dashboard', external: false };
    }
    if (type === 'work_order' && id) {
      return {
        href: `/admin/ops/maintenance/work-orders/${encodeURIComponent(id)}`,
        external: false,
      };
    }
    if (type === 'admin_communication') {
      return { href: '/admin/dashboard', external: false };
    }
    return { href: '/admin/dashboard', external: false };
  }

  if (type === 'order' && id) {
    return { href: `/orders?order=${encodeURIComponent(id)}`, external: false };
  }
  if (type === 'work_order') {
    return { href: '/operations/work-orders', external: false };
  }
  if (type === 'invoice' || type === 'billing') {
    return { href: '/settings/billing', external: false };
  }
  if (type === 'requirement' || type === 'compliance') {
    return { href: '/requirements', external: false };
  }
  if (type === 'document') {
    return { href: '/documents', external: false };
  }
  return { href: '/dashboard', external: false };
}

export function severityBadgeClass(severity) {
  const s = String(severity || 'medium').toLowerCase();
  if (s === 'critical') return 'bg-red-100 text-red-800 border-red-200';
  if (s === 'high') return 'bg-orange-100 text-orange-800 border-orange-200';
  if (s === 'low' || s === 'info') return 'bg-slate-100 text-slate-700 border-slate-200';
  return 'bg-blue-100 text-blue-800 border-blue-200';
}
