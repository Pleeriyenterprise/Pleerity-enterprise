import React, { useState, useEffect, useRef } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useEntitlements } from '../contexts/EntitlementsContext';
import api, { clientAPI, authAPI } from '../api/client';
import { Button } from './ui/button';
import { SUPPORT_EMAIL } from '../config';
import { branding, BRAND_LOGO_URL } from '../config/branding';
import { toast } from 'sonner';
import SessionIdleGuard from './SessionIdleGuard';
import {
  LayoutDashboard,
  Building2,
  FileCheck,
  FileText,
  Calendar,
  BarChart3,
  Settings,
  MessageSquare,
  LogOut,
  Copy,
  Menu,
  X,
  User,
  Bell,
  CreditCard,
  HelpCircle,
  ChevronDown,
  ChevronRight,
  History,
  Users,
  Wrench,
  Briefcase,
  AlertCircle,
  TrendingUp,
  ClipboardCheck,
  ListTodo,
  Inbox,
  Gauge,
} from 'lucide-react';
import { resolveNotificationTarget } from '../utils/notificationDeepLink';
import { PORTAL_COPY } from '../utils/clientPortalCopy';
import {
  COMPLIANCE_REPORT_HINT_COOLDOWN_MS,
  shouldSuggestComplianceReportHint,
  complianceReportNudgeToastCopy,
} from '../utils/confidenceUxCopy';

// Operations sub-items (feature-gated). Shown under Operations group; no standalone Maintenance/Contractors.
const OPERATIONS_CHILDREN = [
  { path: '/operations/issues', label: 'Issues', icon: AlertCircle, feature: 'maintenance_workflows' },
  { path: '/operations/work-orders', label: PORTAL_COPY.jobs, icon: Wrench, feature: 'maintenance_workflows' },
  { path: '/operations/contractors', label: 'Contractors', icon: Briefcase, feature: 'contractor_network' },
  { path: '/operations/risk-signals', label: 'Flagged issues', icon: TrendingUp, feature: 'predictive_maintenance' },
  { path: '/operations/approvals', label: 'Approvals', icon: ClipboardCheck, feature: 'invoicing' },
];

const PORTAL_TABS = [
  { path: '/today', label: 'Today', icon: ListTodo },
  { path: '/command-center', label: 'Command center', icon: Gauge },
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/properties', label: 'Properties', icon: Building2 },
  { path: '/requirements', label: 'Requirements', icon: FileCheck },
  { path: '/documents', label: 'Documents', icon: FileText },
  { path: '/calendar', label: 'Calendar', icon: Calendar },
  { path: '/reports', label: 'Reports', icon: BarChart3 },
  { type: 'group', label: 'Operations', icon: Wrench, children: OPERATIONS_CHILDREN },
  { path: '/tenants', label: 'Tenants', icon: Users, feature: 'tenant_portal' },
  { path: '/settings/billing', label: 'Billing', icon: CreditCard, feature: 'invoicing' },
  { path: '/settings', label: 'Settings', icon: Settings, end: true },
];

const TENANT_PORTAL_TABS = [
  { path: '/tenant', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { path: '/tenant/properties', label: 'Properties', icon: Building2 },
  { path: '/tenant/settings', label: 'Settings', icon: Settings },
];

const SETTINGS_SUB = [
  { path: '/settings/profile', label: 'Profile', icon: User },
  { path: '/settings/inbox', label: 'Inbox', icon: Inbox },
  { path: '/settings/notifications', label: 'Notifications', icon: Bell },
  { path: '/settings/billing', label: 'Billing', icon: CreditCard },
];

export default function ClientPortalLayout({ children, crn: crnProp = null }) {
  const { user, logout, isClient } = useAuth();
  const { hasFeature, entitlementsLoadFailed } = useEntitlements();
  /** While entitlements failed to load, keep gated nav visible so users are not misled into thinking features are absent; route gates show retry. */
  const navHasFeature = (key) => entitlementsLoadFailed || hasFeature(key);
  const navigate = useNavigate();
  const isTenant = user?.role === 'ROLE_TENANT';
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [operationsDropdownOpen, setOperationsDropdownOpen] = useState(false);
  const [crnState, setCrnState] = useState(crnProp);
  const [profile, setProfile] = useState(null);
  const [headerAvatarUrl, setHeaderAvatarUrl] = useState(null);
  const [impersonation, setImpersonation] = useState(null);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifItems, setNotifItems] = useState([]);
  const [notifLoading, setNotifLoading] = useState(false);
  const [notifUnreadCount, setNotifUnreadCount] = useState(0);
  const [portalTrust, setPortalTrust] = useState(null);
  const [portalTrustLoading, setPortalTrustLoading] = useState(false);
  const [portalTrustError, setPortalTrustError] = useState(false);
  const complianceReportHintCooldownRef = useRef(0);

  const loadInAppNotifications = () => {
    if (isTenant || !isClient) return;
    setNotifLoading(true);
    Promise.all([
      clientAPI.getInAppNotifications({ limit: 30, inbox_filter: 'all' }),
      clientAPI.getInAppNotificationsUnreadCount(),
    ])
      .then(([listRes, countRes]) => {
        setNotifItems(listRes.data.items || []);
        const n = countRes.data?.unread_count;
        setNotifUnreadCount(typeof n === 'number' ? n : 0);
      })
      .catch(() => {})
      .finally(() => setNotifLoading(false));
  };

  const loadPortalTrust = async () => {
    if (isTenant || !isClient) return;
    setPortalTrustLoading(true);
    setPortalTrustError(false);
    const maxAttempts = 4;
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        const r = await clientAPI.getPortalContext();
        setPortalTrust(r.data || null);
        setPortalTrustError(false);
        setPortalTrustLoading(false);
        return;
      } catch {
        setPortalTrustError(true);
        if (attempt < maxAttempts - 1) {
          await sleep(600 * (attempt + 1));
        }
      }
    }
    setPortalTrustLoading(false);
  };

  useEffect(() => {
    if (!isClient || isTenant) return;
    loadInAppNotifications();
    loadPortalTrust();
    const t = setInterval(loadInAppNotifications, 120000);
    const t2 = setInterval(loadPortalTrust, 180000);
    return () => {
      clearInterval(t);
      clearInterval(t2);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isClient, isTenant, user?.portal_user_id]);

  useEffect(() => {
    if (!isClient || isTenant) return undefined;
    const reportsUnlocked = hasFeature('reports_pdf') || hasFeature('reports_csv');
    if (!reportsUnlocked) return undefined;
    const onOutcome = (ev) => {
      const detail = ev && typeof ev === 'object' ? ev.detail : undefined;
      if (!detail || !shouldSuggestComplianceReportHint(detail)) return;
      const now = Date.now();
      if (now - complianceReportHintCooldownRef.current < COMPLIANCE_REPORT_HINT_COOLDOWN_MS) return;
      complianceReportHintCooldownRef.current = now;
      const { title, description } = complianceReportNudgeToastCopy(detail);
      toast.info(title, { description, duration: 9000 });
    };
    window.addEventListener('compliance-outcome', onOutcome);
    return () => window.removeEventListener('compliance-outcome', onOutcome);
  }, [isClient, isTenant, hasFeature]);

  useEffect(() => {
    if (notifOpen) loadInAppNotifications();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notifOpen]);

  useEffect(() => {
    const raw = localStorage.getItem('impersonation_context');
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw);
      if (parsed?.active) setImpersonation(parsed);
    } catch (_) {
      // ignore malformed local storage
    }
  }, []);

  useEffect(() => {
    if (crnProp) {
      setCrnState(crnProp);
      return;
    }
    if (user?.role === 'ROLE_TENANT') return;
    clientAPI.getDashboard().then((r) => {
      const ref = r.data?.client?.customer_reference;
      if (ref) setCrnState(ref);
    }).catch(() => {});
  }, [crnProp, user?.role]);

  const fetchProfile = () => {
    if (!user?.client_id) return;
    if (!['ROLE_CLIENT', 'ROLE_CLIENT_ADMIN', 'ROLE_TENANT'].includes(user?.role)) return;
    api.get('/profile/me').then((r) => {
      setProfile(r.data);
      if (r.data.has_avatar) {
        api.get('/profile/me/avatar', { responseType: 'blob' })
          .then((av) => {
            setHeaderAvatarUrl((prev) => {
              if (prev) URL.revokeObjectURL(prev);
              return URL.createObjectURL(av.data);
            });
          })
          .catch(() => setHeaderAvatarUrl((prev) => {
            if (prev) URL.revokeObjectURL(prev);
            return null;
          }));
      } else {
        setHeaderAvatarUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return null;
        });
      }
    }).catch(() => {});
  };

  useEffect(() => {
    fetchProfile();
    const onUpdated = () => fetchProfile();
    window.addEventListener('profile-updated', onUpdated);
    return () => {
      window.removeEventListener('profile-updated', onUpdated);
      setHeaderAvatarUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchProfile intentionally omitted; deps are user identity only
  }, [user?.client_id, user?.role]);

  const crn = crnState || crnProp;

  const handleCopyCRN = () => {
    if (!crn) return;
    navigator.clipboard.writeText(crn).then(
      () => toast.success('CRN copied'),
      () => toast.error('Copy failed')
    );
  };

  const location = useLocation();
  const showReports = navHasFeature('reports_pdf') || navHasFeature('reports_csv');

  // Build tabs: filter by feature; for Operations group, show only if at least one child is enabled and filter children
  const tabs = isTenant
    ? TENANT_PORTAL_TABS
    : PORTAL_TABS.map((t) => {
        if (t.type === 'group' && t.children) {
          const children = t.children.filter((c) => (c.feature ? navHasFeature(c.feature) : true));
          if (children.length === 0) return null;
          return { ...t, children };
        }
        if (t.path === '/reports') return showReports ? t : null;
        if (t.feature) return navHasFeature(t.feature) ? t : null;
        return t;
      }).filter(Boolean);

  const operationsOpen = location.pathname.startsWith('/operations');
  const hasOperationsAccess = tabs.some((t) => t.type === 'group' && t.label === 'Operations');

  const isOperationsActive = (pathname) => {
    const p = pathname || location.pathname;
    return p.startsWith('/operations');
  };

  const isSettingsActive = (pathname) => {
    const p = pathname || location.pathname;
    if (isTenant) return p === '/tenant/settings' || p.startsWith('/tenant/settings/');
    // When Billing has its own top-level tab (invoicing enabled), don't mark Settings active on /settings/billing
    if (hasFeature('invoicing') && (p === '/settings/billing' || p.startsWith('/settings/billing/'))) {
      return false;
    }
    return p === '/settings' || p.startsWith('/settings/');
  };

  const handleStopImpersonation = async () => {
    try {
      await authAPI.stopImpersonation();
    } catch (_) {
      // Audit call is best effort; still restore local admin session.
    }
    const adminToken = sessionStorage.getItem('impersonation_admin_token');
    const adminUser = sessionStorage.getItem('impersonation_admin_user');
    localStorage.removeItem('impersonation_context');
    sessionStorage.removeItem('impersonation_admin_token');
    sessionStorage.removeItem('impersonation_admin_user');
    if (adminToken && adminUser) {
      localStorage.setItem('auth_token', adminToken);
      localStorage.setItem('user', adminUser);
      window.location.href = '/admin/dashboard';
      return;
    }
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
    window.location.href = '/login/admin?impersonation_expired=1';
  };

  return (
    <SessionIdleGuard>
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header: navy, CRN right, Ask Assistant + Logout right */}
      <header className="bg-midnight-blue text-white shadow-sm sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-2 sm:py-3">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between lg:gap-4 min-w-0">
            <div className="flex flex-col gap-2 min-w-0 sm:flex-row sm:items-center sm:flex-wrap sm:gap-x-4 sm:gap-y-2">
              <NavLink to="/dashboard" className="flex items-center gap-2 min-w-0 max-w-full shrink-0">
                <img src={BRAND_LOGO_URL} alt="" className="h-8 w-auto shrink-0" />
                <div className="min-w-0 flex flex-col">
                  <span className="text-lg sm:text-xl font-bold truncate leading-tight">{branding.productName}</span>
                  <span className="text-xs text-gray-300 truncate hidden md:block">{branding.tagline}</span>
                </div>
              </NavLink>
              {crn && !isTenant && (
                <div className="flex items-center gap-1 flex-wrap shrink-0">
                  <span
                    className="px-2 py-1 sm:px-2.5 sm:py-1 bg-electric-teal/20 text-electric-teal rounded-lg font-mono text-xs sm:text-sm max-w-full truncate inline-block align-middle"
                    data-testid="client-crn-badge"
                    title={`Customer reference: ${crn}`}
                  >
                    {crn}
                  </span>
                  <button
                    type="button"
                    onClick={handleCopyCRN}
                    className="tap-target min-w-0 min-h-0 h-9 w-9 sm:h-8 sm:w-8 shrink-0 inline-flex items-center justify-center rounded-md hover:bg-white/10 text-electric-teal"
                    title="Copy CRN"
                  >
                    <Copy className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2 justify-between sm:justify-end lg:shrink-0 min-w-0">
              {!isTenant && isClient && (
                <div className="relative shrink-0">
                  <button
                    type="button"
                    onClick={() => setNotifOpen((o) => !o)}
                    className="tap-target h-10 w-10 inline-flex items-center justify-center rounded-md hover:bg-white/10 text-white relative"
                    aria-label="Notifications"
                    aria-expanded={notifOpen}
                  >
                    <Bell className="w-5 h-5" />
                    {notifUnreadCount > 0 && (
                      <span
                        className="absolute -top-0.5 -right-0.5 min-w-[1.125rem] h-[1.125rem] px-0.5 rounded-full bg-amber-400 text-[10px] font-bold text-midnight-blue flex items-center justify-center leading-none"
                        aria-label={`${notifUnreadCount} unread`}
                      >
                        {notifUnreadCount > 99 ? '99+' : notifUnreadCount}
                      </span>
                    )}
                  </button>
                  {notifOpen && (
                    <>
                      <button
                        type="button"
                        className="fixed inset-0 z-40 bg-black/20 lg:bg-transparent"
                        aria-label="Close notifications"
                        onClick={() => setNotifOpen(false)}
                      />
                      <div className="fixed z-50 right-2 top-[3.5rem] w-[min(100vw-1rem,24rem)] max-h-[min(70vh,28rem)] overflow-hidden rounded-lg border border-gray-200 bg-white text-gray-900 shadow-xl flex flex-col">
                        <div className="px-3 py-2 border-b border-gray-100 flex items-center justify-between gap-2">
                          <span className="text-sm font-semibold">Notifications</span>
                          <div className="flex items-center gap-2 shrink-0">
                            <button
                              type="button"
                              className="text-xs text-electric-teal hover:underline"
                              onClick={() => {
                                setNotifOpen(false);
                                navigate('/settings/inbox');
                              }}
                            >
                              View all
                            </button>
                            <button type="button" className="text-xs text-gray-500 hover:underline" onClick={() => setNotifOpen(false)}>
                              Close
                            </button>
                          </div>
                        </div>
                        <div className="overflow-y-auto flex-1">
                          {notifLoading && <p className="p-3 text-sm text-gray-500">Loading…</p>}
                          {!notifLoading && notifItems.length === 0 && (
                            <p className="p-3 text-sm text-gray-500">No notifications yet.</p>
                          )}
                          {!notifLoading &&
                            notifItems.map((n) => (
                              <button
                                key={n.notification_id}
                                type="button"
                                className={`w-full text-left px-3 py-2 border-b border-gray-50 hover:bg-gray-50 text-sm ${n.is_read ? 'opacity-80' : 'bg-slate-50/80'}`}
                                onClick={async () => {
                                  try {
                                    await clientAPI.markInAppNotificationRead(n.notification_id);
                                    const wasUnread = !n.is_read;
                                    setNotifItems((prev) =>
                                      prev.map((x) =>
                                        x.notification_id === n.notification_id ? { ...x, is_read: true } : x
                                      )
                                    );
                                    if (wasUnread) {
                                      setNotifUnreadCount((c) => Math.max(0, c - 1));
                                    }
                                  } catch (_) {
                                    /* ignore */
                                  }
                                  const { href, external } = resolveNotificationTarget(n, false);
                                  if (external) window.open(href, '_blank', 'noopener,noreferrer');
                                  else navigate(href);
                                  setNotifOpen(false);
                                }}
                              >
                                <div className="font-medium text-gray-900 line-clamp-2">{n.title}</div>
                                {n.message && <div className="text-gray-600 text-xs mt-0.5 line-clamp-3">{n.message}</div>}
                                {n.created_at && (
                                  <div className="text-[10px] text-gray-400 mt-1">{String(n.created_at).slice(0, 16)}</div>
                                )}
                              </button>
                            ))}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/assistant')}
                className="text-white hover:bg-white/10 hover:text-white h-10 px-3 shrink-0"
                data-testid="ask-assistant-btn"
              >
                <MessageSquare className="w-4 h-4 sm:mr-1.5 shrink-0" />
                <span className="hidden sm:inline">Ask Assistant</span>
              </Button>
              <div className="flex items-center gap-2 min-w-0 flex-1 sm:flex-initial justify-end">
                {headerAvatarUrl && (
                  <div className="w-9 h-9 rounded-full overflow-hidden border border-white/30 shrink-0">
                    <img src={headerAvatarUrl} alt="" className="w-full h-full object-cover" />
                  </div>
                )}
                <span
                  className="text-sm text-gray-200 truncate min-w-0 max-w-[min(56vw,14rem)] sm:max-w-[200px] lg:max-w-[240px]"
                  title={profile?.full_name || user?.email || ''}
                >
                  {profile?.full_name || user?.email}
                </span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={logout}
                className="text-white hover:bg-white/10 hover:text-white h-10 px-3 shrink-0"
              >
                <LogOut className="w-4 h-4 sm:mr-1.5 shrink-0" />
                <span className="hidden sm:inline">Logout</span>
              </Button>
              <button
                type="button"
                className="lg:hidden tap-target h-10 w-10 shrink-0 inline-flex items-center justify-center rounded-md hover:bg-white/10"
                onClick={() => setMobileNavOpen((o) => !o)}
                aria-label="Toggle menu"
              >
                {mobileNavOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>

        {/* Tabs: visible on desktop; collapsible on mobile */}
        <nav className={`border-t border-white/10 ${mobileNavOpen ? 'block' : 'hidden'} lg:block`}>
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col lg:flex-row lg:items-stretch lg:space-x-1">
              {tabs.map((tab) => {
                if (tab.type === 'group' && tab.children?.length > 0) {
                  const Icon = tab.icon;
                  const isActive = isOperationsActive(location.pathname);
                  return (
                    <div
                      key="operations-group"
                      className="relative"
                      onMouseEnter={() => setOperationsDropdownOpen(true)}
                      onMouseLeave={() => setOperationsDropdownOpen(false)}
                    >
                      <button
                        type="button"
                        onClick={() => setOperationsDropdownOpen((o) => !o)}
                        className={`flex items-center min-h-[44px] px-3 py-3 lg:py-4 text-sm font-medium border-b-2 transition-colors w-full lg:w-auto ${
                          isActive
                            ? 'border-electric-teal text-electric-teal'
                            : 'border-transparent text-gray-300 hover:text-white hover:border-gray-400'
                        }`}
                      >
                        <Icon className="w-4 h-4 mr-2" />
                        {tab.label}
                        <ChevronDown className={`w-4 h-4 ml-1 transition-transform ${operationsDropdownOpen ? 'rotate-180' : ''}`} />
                      </button>
                      <div
                        className={`lg:absolute lg:left-0 lg:top-full lg:pt-0 lg:bg-midnight-blue lg:border lg:border-white/10 lg:rounded-b-lg lg:shadow-lg lg:min-w-[180px] z-40 ${
                          operationsDropdownOpen ? 'block' : 'hidden'
                        }`}
                      >
                        {tab.children.map((child) => {
                          const ChildIcon = child.icon;
                          return (
                            <NavLink
                              key={child.path}
                              to={child.path}
                              onClick={() => {
                                setMobileNavOpen(false);
                                setOperationsDropdownOpen(false);
                              }}
                              className={({ isActive: childActive }) =>
                                `flex items-center px-3 py-2.5 text-sm border-l-2 lg:border-l-0 lg:border-b-0 transition-colors ${
                                  childActive
                                    ? 'border-electric-teal text-electric-teal bg-white/10'
                                    : 'border-transparent text-gray-300 hover:text-white hover:bg-white/5'
                                }`
                              }
                            >
                              <ChildIcon className="w-4 h-4 mr-2 shrink-0" />
                              {child.label}
                            </NavLink>
                          );
                        })}
                      </div>
                    </div>
                  );
                }
                const { path, label, icon: Icon, end } = tab;
                return (
                  <NavLink
                    key={path}
                    to={path}
                    end={end}
                    onClick={() => setMobileNavOpen(false)}
                    className={({ isActive }) =>
                      `flex items-center min-h-[44px] px-3 py-3 lg:py-4 text-sm font-medium border-b-2 lg:border-b-2 transition-colors ${
                        isActive || ((path === '/settings' || path === '/tenant/settings') && isSettingsActive(location.pathname))
                          ? 'border-electric-teal text-electric-teal'
                          : 'border-transparent text-gray-300 hover:text-white hover:border-gray-400'
                      }`
                    }
                  >
                    <Icon className="w-4 h-4 mr-2" />
                    {label}
                  </NavLink>
                );
              })}
            </div>
          </div>
        </nav>
      </header>

      {!isTenant && isClient && (
        <div className="border-b border-gray-200 bg-gray-50">
          <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-1.5 text-xs text-gray-600">
            {portalTrustLoading && !portalTrust ? (
              <span className="text-gray-600">
                {portalTrustError
                  ? 'Unable to sync portal status. Retrying…'
                  : 'Syncing portal status…'}
              </span>
            ) : portalTrustError && !portalTrust ? (
              <span className="text-amber-800">
                Status line temporarily unavailable. We&apos;ll keep retrying in the background — refresh if this persists.
              </span>
            ) : (
              <>
                <span title="Server time when this snapshot was taken">
                  Last updated:{' '}
                  {portalTrust?.server_time
                    ? new Date(portalTrust.server_time).toLocaleString()
                    : '—'}
                </span>
                {portalTrust?.last_recorded_activity_at && (
                  <span className="block sm:inline sm:ml-3 mt-0.5 sm:mt-0" title="Latest audited activity for your organisation">
                    · Last recorded activity: {new Date(portalTrust.last_recorded_activity_at).toLocaleString()}
                  </span>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {impersonation?.active && (
        <div className="bg-amber-100 border-y border-amber-300 px-3 sm:px-4 py-2">
          <div className="max-w-7xl mx-auto flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-amber-900 min-w-0 break-words">
              You are viewing this account as user{impersonation.client_name ? `: ${impersonation.client_name}` : ''}. Actions are audited.
            </p>
            <button
              type="button"
              onClick={handleStopImpersonation}
              className="shrink-0 px-3 py-2.5 sm:py-1.5 rounded-md text-sm font-medium bg-amber-900 text-white hover:bg-amber-950 min-h-[44px] sm:min-h-0"
            >
              Stop impersonation
            </button>
          </div>
        </div>
      )}

      <main className="client-portal-main client-portal-prose flex-1 max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 pb-8">
        {children}
      </main>

      {/* Footer: Support email, CRN copy, Audit log, Help */}
      <footer className="border-t border-gray-200 bg-white py-4 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm text-gray-500">{branding.productName}</span>
          <div className="flex items-center gap-4 flex-wrap">
            <a
              href={`mailto:${SUPPORT_EMAIL}`}
              className="text-sm text-electric-teal hover:underline"
            >
              {SUPPORT_EMAIL}
            </a>
            {crn && !isTenant && (
              <div className="flex items-center gap-1">
                <span className="text-sm text-gray-600">CRN: {crn}</span>
                <button
                  type="button"
                  onClick={handleCopyCRN}
                  className="p-0.5 rounded hover:bg-gray-100 text-electric-teal"
                  title="Copy CRN"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
            <NavLink to="/audit-log" className="text-sm text-electric-teal hover:underline flex items-center gap-1">
              <History className="w-4 h-4" />
              Audit log
            </NavLink>
            <NavLink to="/help" className="text-sm text-electric-teal hover:underline flex items-center gap-1">
              <HelpCircle className="w-4 h-4" />
              Help Centre
            </NavLink>
          </div>
        </div>
      </footer>
    </div>
    </SessionIdleGuard>
  );
}
