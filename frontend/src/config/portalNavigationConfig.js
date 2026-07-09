import {
  LayoutDashboard,
  Building2,
  FileCheck,
  FileText,
  Calendar,
  BarChart3,
  Settings,
  Users,
  Wrench,
  Briefcase,
  AlertCircle,
  TrendingUp,
  ClipboardCheck,
  ListTodo,
  Gauge,
  PoundSterling,
  CreditCard,
} from 'lucide-react';
import { PORTAL_COPY } from '../utils/clientPortalCopy';

/** Navigation tier — primary operational vs secondary support/admin. */
export const NAV_TIER = {
  PRIMARY: 'primary',
  SECONDARY: 'secondary',
};

/** Operations sub-routes (feature-gated at render). */
export const OPERATIONS_NAV_CHILDREN = [
  { path: '/operations/issues', label: 'Issues', icon: AlertCircle, feature: 'maintenance_workflows' },
  { path: '/operations/work-orders', label: PORTAL_COPY.jobs, icon: Wrench, feature: 'maintenance_workflows' },
  { path: '/operations/contractors', label: 'Contractors', icon: Briefcase, feature: 'contractor_network' },
  { path: '/operations/risk-signals', label: 'Risk signals', icon: TrendingUp, feature: 'predictive_maintenance' },
  { path: '/operations/rent', label: 'Rent Operations', icon: PoundSterling, feature: 'rent_operations' },
  { path: '/operations/approvals', label: 'Approvals', icon: ClipboardCheck, feature: 'invoicing' },
];

/**
 * Primary operational navigation — always visible on desktop.
 * Order reflects operational priority (highest-frequency first).
 */
export const PORTAL_PRIMARY_NAV_ITEMS = [
  { path: '/today', label: 'Today', icon: ListTodo, tier: NAV_TIER.PRIMARY },
  { path: '/command-center', label: 'Command center', icon: Gauge, tier: NAV_TIER.PRIMARY },
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, tier: NAV_TIER.PRIMARY },
  { path: '/properties', label: 'Properties', icon: Building2, tier: NAV_TIER.PRIMARY },
  { path: '/requirements', label: 'Requirements', icon: FileCheck, tier: NAV_TIER.PRIMARY },
  { path: '/documents', label: 'Documents', icon: FileText, tier: NAV_TIER.PRIMARY },
  {
    type: 'group',
    id: 'operations',
    label: 'Operations',
    icon: Wrench,
    tier: NAV_TIER.PRIMARY,
    children: OPERATIONS_NAV_CHILDREN,
  },
];

/**
 * Secondary navigation — grouped under "More" on desktop; sectioned on mobile.
 */
export const PORTAL_SECONDARY_NAV_ITEMS = [
  { path: '/calendar', label: 'Calendar', icon: Calendar, tier: NAV_TIER.SECONDARY, calendarGate: true },
  { path: '/reports', label: 'Reports', icon: BarChart3, tier: NAV_TIER.SECONDARY, reportsGate: true },
  { path: '/tenants', label: 'Tenants', icon: Users, tier: NAV_TIER.SECONDARY, feature: 'tenant_portal' },
  { path: '/settings/billing', label: 'Billing', icon: CreditCard, tier: NAV_TIER.SECONDARY, billingGate: true },
  { path: '/settings', label: 'Settings', icon: Settings, tier: NAV_TIER.SECONDARY, end: true },
];

/**
 * Flat legacy export for compatibility and regression checks.
 * Preserves pre-hierarchy label set for tests and external references.
 */
export const PORTAL_TABS = [
  ...PORTAL_PRIMARY_NAV_ITEMS.filter((item) => item.type !== 'group'),
  PORTAL_SECONDARY_NAV_ITEMS[0],
  PORTAL_SECONDARY_NAV_ITEMS[1],
  PORTAL_PRIMARY_NAV_ITEMS.find((item) => item.type === 'group'),
  PORTAL_SECONDARY_NAV_ITEMS[2],
  PORTAL_SECONDARY_NAV_ITEMS[3],
  PORTAL_SECONDARY_NAV_ITEMS[4],
].filter(Boolean);

export const TENANT_PORTAL_TABS = [
  { path: '/tenant', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { path: '/tenant/properties', label: 'Properties', icon: Building2 },
  { path: '/tenant/settings', label: 'Settings', icon: Settings },
];

function filterOperationsChildren(children, { navHasFeature, userRole }) {
  return (children || []).filter((child) => {
    if (child.orgReviewerOnly && String(userRole || '').toUpperCase() !== 'ROLE_CLIENT_ADMIN') {
      return false;
    }
    return child.feature ? navHasFeature(child.feature) : true;
  });
}

function filterLinkItem(item, { navHasFeature, showReports, showBilling, showCalendar }) {
  if (item.reportsGate && !showReports) return null;
  if (item.billingGate && !showBilling) return null;
  if (item.calendarGate && !showCalendar) return null;
  if (item.feature && !navHasFeature(item.feature)) return null;
  return item;
}

/**
 * Build hierarchy-aware navigation model for client portal rendering.
 * @returns {{ primaryLinks: object[], operationsGroup: object|null, secondaryItems: object[] }}
 */
export function buildPortalNavigationModel({ navHasFeature, showReports, showBilling, showCalendar, userRole }) {
  const filterCtx = { navHasFeature, showReports, showBilling, showCalendar, userRole };

  const primaryLinks = [];
  let operationsGroup = null;

  for (const item of PORTAL_PRIMARY_NAV_ITEMS) {
    if (item.type === 'group') {
      const children = filterOperationsChildren(item.children, filterCtx);
      if (children.length > 0) {
        operationsGroup = { ...item, children };
      }
      continue;
    }
    const filtered = filterLinkItem(item, filterCtx);
    if (filtered) primaryLinks.push(filtered);
  }

  const secondaryItems = PORTAL_SECONDARY_NAV_ITEMS.map((item) => filterLinkItem(item, filterCtx)).filter(Boolean);

  return { primaryLinks, operationsGroup, secondaryItems };
}

/** Whether pathname is under any operations child route. */
export function isOperationsPath(pathname) {
  return String(pathname || '').startsWith('/operations');
}

/** Whether pathname matches a secondary nav item (incl. settings subtree). */
export function isSecondaryNavPath(pathname) {
  const p = String(pathname || '');
  return (
    p === '/calendar' ||
    p.startsWith('/calendar/') ||
    p === '/reports' ||
    p.startsWith('/reports/') ||
    p === '/tenants' ||
    p.startsWith('/tenants/') ||
    p === '/settings' ||
    p.startsWith('/settings/')
  );
}

export function isSettingsPath(pathname, { isTenant = false, invoicingEnabled = false } = {}) {
  const p = String(pathname || '');
  if (isTenant) return p === '/tenant/settings' || p.startsWith('/tenant/settings/');
  if (invoicingEnabled && (p === '/settings/billing' || p.startsWith('/settings/billing/'))) {
    return false;
  }
  return p === '/settings' || p.startsWith('/settings/');
}
