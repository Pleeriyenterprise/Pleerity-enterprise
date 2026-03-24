import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useEntitlements } from '../contexts/EntitlementsContext';
import api, { clientAPI, authAPI } from '../api/client';
import { Button } from './ui/button';
import { SUPPORT_EMAIL } from '../config';
import { branding, BRAND_LOGO_URL } from '../config/branding';
import { toast } from 'sonner';
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
} from 'lucide-react';

// Operations sub-items (feature-gated). Shown under Operations group; no standalone Maintenance/Contractors.
const OPERATIONS_CHILDREN = [
  { path: '/operations/issues', label: 'Issues', icon: AlertCircle, feature: 'maintenance_workflows' },
  { path: '/operations/work-orders', label: 'Work Orders', icon: Wrench, feature: 'maintenance_workflows' },
  { path: '/operations/contractors', label: 'Contractors', icon: Briefcase, feature: 'contractor_network' },
  { path: '/operations/risk-signals', label: 'Risk Signals', icon: TrendingUp, feature: 'predictive_maintenance' },
  { path: '/operations/approvals', label: 'Approvals', icon: ClipboardCheck, feature: 'invoicing' },
];

const PORTAL_TABS = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/tasks', label: 'Tasks', icon: ListTodo },
  { path: '/properties', label: 'Properties', icon: Building2 },
  { path: '/requirements', label: 'Compliance', icon: FileCheck },
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
  { path: '/settings/notifications', label: 'Notifications', icon: Bell },
  { path: '/settings/billing', label: 'Billing', icon: CreditCard },
];

export default function ClientPortalLayout({ children, crn: crnProp = null }) {
  const { user, logout, isClient } = useAuth();
  const { hasFeature } = useEntitlements();
  const navigate = useNavigate();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [operationsDropdownOpen, setOperationsDropdownOpen] = useState(false);
  const [crnState, setCrnState] = useState(crnProp);
  const [profile, setProfile] = useState(null);
  const [headerAvatarUrl, setHeaderAvatarUrl] = useState(null);
  const [impersonation, setImpersonation] = useState(null);

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
  const showReports = hasFeature('reports_pdf') || hasFeature('reports_csv');
  const isTenant = user?.role === 'ROLE_TENANT';

  // Build tabs: filter by feature; for Operations group, show only if at least one child is enabled and filter children
  const tabs = isTenant
    ? TENANT_PORTAL_TABS
    : PORTAL_TABS.map((t) => {
        if (t.type === 'group' && t.children) {
          const children = t.children.filter((c) => (c.feature ? hasFeature(c.feature) : true));
          if (children.length === 0) return null;
          return { ...t, children };
        }
        if (t.path === '/reports') return showReports ? t : null;
        if (t.feature) return hasFeature(t.feature) ? t : null;
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
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header: navy, CRN right, Ask Assistant + Logout right */}
      <header className="bg-midnight-blue text-white shadow-sm sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex justify-between items-center gap-4">
            <div className="flex items-center gap-4">
              <NavLink to="/dashboard" className="flex items-center gap-2 shrink-0">
                <img src={BRAND_LOGO_URL} alt="" className="h-8 w-auto" />
                <h1 className="text-xl font-bold">{branding.productName}</h1>
                <span className="text-sm text-gray-300 hidden sm:inline">{branding.tagline}</span>
              </NavLink>
              {crn && !isTenant && (
                <div className="flex items-center gap-1">
                  <span
                    className="px-2.5 py-1 bg-electric-teal/20 text-electric-teal rounded-lg font-mono text-sm"
                    data-testid="client-crn-badge"
                    title="Customer Reference Number"
                  >
                    {crn}
                  </span>
                  <button
                    type="button"
                    onClick={handleCopyCRN}
                    className="p-1 rounded hover:bg-white/10 text-electric-teal"
                    title="Copy CRN"
                  >
                    <Copy className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/assistant')}
                className="text-white hover:bg-white/10 hover:text-white"
                data-testid="ask-assistant-btn"
              >
                <MessageSquare className="w-4 h-4 mr-1.5" />
                <span className="hidden sm:inline">Ask Assistant</span>
              </Button>
              <div className="flex items-center gap-2">
                {headerAvatarUrl && (
                  <div className="w-8 h-8 rounded-full overflow-hidden border border-white/30 flex-shrink-0">
                    <img src={headerAvatarUrl} alt="" className="w-full h-full object-cover" />
                  </div>
                )}
                <span className="text-sm text-gray-300 truncate max-w-[120px] sm:max-w-[200px]" title={user?.email}>
                  {profile?.full_name || user?.email}
                </span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={logout}
                className="text-white hover:bg-white/10 hover:text-white"
              >
                <LogOut className="w-4 h-4 sm:mr-1.5" />
                <span className="hidden sm:inline">Logout</span>
              </Button>
              <button
                type="button"
                className="lg:hidden p-2 rounded hover:bg-white/10"
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
                        className={`flex items-center px-3 py-3 lg:py-4 text-sm font-medium border-b-2 transition-colors w-full lg:w-auto ${
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
                      `flex items-center px-3 py-3 lg:py-4 text-sm font-medium border-b-2 lg:border-b-2 transition-colors ${
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

      {impersonation?.active && (
        <div className="bg-amber-100 border-y border-amber-300 px-4 py-2">
          <div className="max-w-7xl mx-auto flex items-center justify-between gap-3">
            <p className="text-sm text-amber-900">
              You are viewing this account as user{impersonation.client_name ? `: ${impersonation.client_name}` : ''}. Actions are audited.
            </p>
            <button
              type="button"
              onClick={handleStopImpersonation}
              className="px-3 py-1.5 rounded-md text-sm font-medium bg-amber-900 text-white hover:bg-amber-950"
            >
              Stop impersonation
            </button>
          </div>
        </div>
      )}

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
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
  );
}
