import React, { useState, useEffect, useRef } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { usePortalNavigationCapabilities, useProfileCapabilities } from '../utils/accountCapabilityAccess';
import api, { clientAPI, authAPI } from '../api/client';
import { Button } from './ui/button';
import { SUPPORT_EMAIL } from '../config';
import { branding, BRAND_LOGO_URL } from '../config/branding';
import { toast } from '@/utils/portalNotifications';
import SessionIdleGuard from './SessionIdleGuard';
import {
  MessageSquare,
  LogOut,
  Copy,
  Menu,
  X,
  Bell,
  HelpCircle,
  History,
} from 'lucide-react';
import { resolveNotificationTarget } from '../utils/notificationDeepLink';
import {
  COMPLIANCE_REPORT_HINT_COOLDOWN_MS,
  shouldSuggestComplianceReportHint,
  complianceReportNudgeToastCopy,
} from '../utils/confidenceUxCopy';
import {
  PORTAL_TABS,
  TENANT_PORTAL_TABS,
  buildPortalNavigationModel,
  isOperationsPath,
  isSecondaryNavPath,
} from '../config/portalNavigationConfig';
import { annotateNavWithLifecyclePolicy } from '../utils/portalNavigationPolicy';
import { usePortalMode } from '../contexts/LifecycleRuntimeContext';
import LifecycleShell from './lifecycle/LifecycleShell';
import LifecycleRuntimeDiagnostics from './lifecycle/LifecycleRuntimeDiagnostics';
import {
  PortalNavDropdown,
  PortalNavLink,
  PortalMobileNavLink,
  PortalMobileNavSection,
} from './portal/PortalNavPrimitives';
import {
  fetchOperational,
  peekOperationalCache,
  OPERATIONAL_CACHE_KEYS,
} from '../utils/clientOperationalFetch';

export { PORTAL_TABS };

export default function ClientPortalLayout({ children, crn: crnProp = null }) {
  const { user, logout, isClient } = useAuth();
  const { navHasFeature, showReports, showBilling, showCalendar, showAssistant, invoicingEnabled } = usePortalNavigationCapabilities();
  const { canEditProfile } = useProfileCapabilities();
  const { navigationPolicy } = usePortalMode();
  const navigate = useNavigate();
  const isTenant = user?.role === 'ROLE_TENANT';
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [operationsDropdownOpen, setOperationsDropdownOpen] = useState(false);
  const [moreDropdownOpen, setMoreDropdownOpen] = useState(false);
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
  const portalTrustFailuresRef = useRef(0);
  const portalTrustCircuitUntilRef = useRef(0);

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
    const now = Date.now();
    if (portalTrustCircuitUntilRef.current > now) {
      setPortalTrustError(true);
      return;
    }
    setPortalTrustLoading(true);
    setPortalTrustError(false);
    const maxAttempts = 2;
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        const r = await clientAPI.getPortalContext();
        setPortalTrust(r.data || null);
        setPortalTrustError(false);
        portalTrustFailuresRef.current = 0;
        portalTrustCircuitUntilRef.current = 0;
        setPortalTrustLoading(false);
        return;
      } catch {
        setPortalTrustError(true);
        if (attempt < maxAttempts - 1) {
          await sleep(1200 * (attempt + 1));
        }
      }
    }
    portalTrustFailuresRef.current += 1;
    if (portalTrustFailuresRef.current >= 3) {
      portalTrustCircuitUntilRef.current = Date.now() + 5 * 60 * 1000;
    }
    setPortalTrustLoading(false);
  };

  useEffect(() => {
    if (!isClient || isTenant) return;
    loadInAppNotifications();
    loadPortalTrust();
    const t = setInterval(loadInAppNotifications, 120000);
    const t2 = setInterval(() => {
      if (portalTrustCircuitUntilRef.current <= Date.now()) {
        loadPortalTrust();
      }
    }, 180000);
    return () => {
      clearInterval(t);
      clearInterval(t2);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isClient, isTenant, user?.portal_user_id]);

  useEffect(() => {
    if (!isClient || isTenant) return undefined;
    if (!showReports) return undefined;
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
  }, [isClient, isTenant, showReports]);

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
    const cached = peekOperationalCache(OPERATIONAL_CACHE_KEYS.dashboard);
    const cachedRef = cached?.client?.customer_reference;
    if (cachedRef) {
      setCrnState(cachedRef);
      return;
    }
    fetchOperational(OPERATIONAL_CACHE_KEYS.dashboard, () =>
      clientAPI.getDashboard().then((r) => r.data),
    )
      .then((hit) => {
        const ref = hit.data?.client?.customer_reference;
        if (ref) setCrnState(ref);
      })
      .catch(() => {});
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
  const tenantTabs = isTenant ? TENANT_PORTAL_TABS : null;
  const navModel = isTenant
    ? null
    : annotateNavWithLifecyclePolicy(
        buildPortalNavigationModel({
          navHasFeature,
          showReports,
          showBilling,
          showCalendar,
          userRole: user?.role,
        }),
        navigationPolicy,
      );
  const { primaryLinks = [], operationsGroup = null, secondaryItems = [] } = navModel || {};

  const closeNavMenus = () => {
    setMobileNavOpen(false);
    setOperationsDropdownOpen(false);
    setMoreDropdownOpen(false);
  };

  useEffect(() => {
    closeNavMenus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  const operationsActive = isOperationsPath(location.pathname);
  const moreActive = isSecondaryNavPath(location.pathname);

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

  const impersonationRemainingText = (() => {
    const expiresAt = impersonation?.expires_at;
    if (!expiresAt) return 'Session expiry not provided.';
    const ms = new Date(expiresAt).getTime() - Date.now();
    if (Number.isNaN(ms)) return 'Session expiry unavailable.';
    if (ms <= 0) return 'Session has expired. Exit impersonation now.';
    const mins = Math.ceil(ms / 60000);
    return `${mins} minute${mins === 1 ? '' : 's'} remaining`;
  })();

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
                                    if (canEditProfile && !n.is_read) {
                                      await clientAPI.markInAppNotificationRead(n.notification_id);
                                      setNotifItems((prev) =>
                                        prev.map((x) =>
                                          x.notification_id === n.notification_id ? { ...x, is_read: true } : x
                                        )
                                      );
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
              {showAssistant && (
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
              )}
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

        {/* Hierarchy nav: desktop single-line (no horizontal scroll); mobile drawer sections */}
        <nav
          className={`border-t border-white/10 ${mobileNavOpen ? 'block' : 'hidden'} lg:block`}
          aria-label="Portal navigation"
          data-testid="portal-main-nav"
        >
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            {isTenant ? (
              <div className="flex flex-col divide-y divide-white/10 lg:divide-y-0 lg:flex-row lg:items-stretch lg:gap-0.5 lg:overflow-visible">
                {tenantTabs.map((tab) => (
                  <PortalNavLink
                    key={tab.path}
                    to={tab.path}
                    label={tab.label}
                    icon={tab.icon}
                    end={tab.end}
                    isTenant
                    onNavigate={closeNavMenus}
                  />
                ))}
              </div>
            ) : (
              <>
                {/* Desktop: primary + Operations + More — no overflow scroll */}
                <div
                  className="hidden lg:flex lg:items-stretch lg:gap-0.5 lg:overflow-visible lg:flex-nowrap"
                  data-testid="portal-desktop-nav"
                >
                  {primaryLinks.map((item) => (
                    <PortalNavLink
                      key={item.path}
                      to={item.path}
                      label={item.label}
                      icon={item.icon}
                      invoicingEnabled={invoicingEnabled}
                      onNavigate={closeNavMenus}
                      lifecycleNavHint={item.lifecycleNavHint}
                    />
                  ))}
                  {operationsGroup ? (
                    <PortalNavDropdown
                      menuId="portal-operations"
                      label={operationsGroup.label}
                      icon={operationsGroup.icon}
                      isActive={operationsActive}
                      isOpen={operationsDropdownOpen}
                      onOpenChange={setOperationsDropdownOpen}
                      items={[{ type: 'group', children: operationsGroup.children }]}
                      invoicingEnabled={invoicingEnabled}
                      onNavigate={closeNavMenus}
                    />
                  ) : null}
                  {secondaryItems.length > 0 ? (
                    <PortalNavDropdown
                      menuId="portal-more"
                      label="More"
                      isActive={moreActive}
                      isOpen={moreDropdownOpen}
                      onOpenChange={setMoreDropdownOpen}
                      items={secondaryItems}
                      invoicingEnabled={invoicingEnabled}
                      onNavigate={closeNavMenus}
                    />
                  ) : null}
                </div>

                {/* Mobile/tablet: sectioned drawer — intentional hierarchy, not overflow inheritance */}
                <div className="lg:hidden max-h-[min(70vh,32rem)] overflow-y-auto overscroll-y-contain" data-testid="portal-mobile-nav">
                  {primaryLinks.map((item) => (
                    <PortalMobileNavLink
                      key={item.path}
                      to={item.path}
                      label={item.label}
                      icon={item.icon}
                      invoicingEnabled={invoicingEnabled}
                      onNavigate={closeNavMenus}
                    />
                  ))}
                  {operationsGroup ? (
                    <PortalMobileNavSection title="Operations" isActiveSection={operationsActive} defaultOpen={operationsActive}>
                      {operationsGroup.children.map((child) => (
                        <PortalMobileNavLink
                          key={child.path}
                          to={child.path}
                          label={child.label}
                          icon={child.icon}
                          invoicingEnabled={invoicingEnabled}
                          onNavigate={closeNavMenus}
                        />
                      ))}
                    </PortalMobileNavSection>
                  ) : null}
                  {secondaryItems.length > 0 ? (
                    <PortalMobileNavSection title="More" isActiveSection={moreActive} defaultOpen={moreActive}>
                      {secondaryItems.map((item) => (
                        <PortalMobileNavLink
                          key={item.path}
                          to={item.path}
                          label={item.label}
                          icon={item.icon}
                          end={item.end}
                          invoicingEnabled={invoicingEnabled}
                          onNavigate={closeNavMenus}
                        />
                      ))}
                    </PortalMobileNavSection>
                  ) : null}
                </div>
              </>
            )}
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
              <span className="text-slate-800 font-medium">
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
            <div className="min-w-0 break-words space-y-0.5">
              <p className="text-sm text-amber-900">
                You are viewing this account as user{impersonation.client_name ? `: ${impersonation.client_name}` : ''}. Actions are audited.
              </p>
              <p className="text-xs text-amber-950">
                {impersonation.client_id ? `Client ID: ${impersonation.client_id}` : null}
                {impersonation.target_email_masked ? ` · User: ${impersonation.target_email_masked}` : null}
              </p>
              <p className="text-xs text-amber-950">
                <span className="font-semibold">Impersonation active.</span> {impersonationRemainingText}
              </p>
            </div>
            <button
              type="button"
              onClick={handleStopImpersonation}
              className="shrink-0 px-3 py-2.5 sm:py-1.5 rounded-md text-sm font-medium bg-amber-900 text-white hover:bg-amber-950 min-h-[44px] sm:min-h-0"
            >
              Exit impersonation
            </button>
          </div>
        </div>
      )}

      <main className="client-portal-main client-portal-prose flex-1 max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8 py-5 sm:py-7 pb-10">
        <LifecycleRuntimeDiagnostics />
        <LifecycleShell />
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
