import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { clientAPI } from '../api/client';
import { Button } from './ui/button';
import { SUPPORT_EMAIL } from '../config';
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
} from 'lucide-react';

const PORTAL_TABS = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/properties', label: 'Properties', icon: Building2 },
  { path: '/requirements', label: 'Requirements', icon: FileCheck },
  { path: '/documents', label: 'Documents', icon: FileText },
  { path: '/calendar', label: 'Calendar', icon: Calendar },
  { path: '/reports', label: 'Reports', icon: BarChart3 },
  { path: '/settings', label: 'Settings', icon: Settings },
];

const SETTINGS_SUB = [
  { path: '/settings/profile', label: 'Profile', icon: User },
  { path: '/settings/notifications', label: 'Notifications', icon: Bell },
  { path: '/settings/billing', label: 'Billing', icon: CreditCard },
];

export default function ClientPortalLayout({ children, crn: crnProp = null }) {
  const { user, logout } = useAuth();
  const { hasFeature } = useEntitlements();
  const navigate = useNavigate();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [crnState, setCrnState] = useState(crnProp);

  useEffect(() => {
    if (crnProp) {
      setCrnState(crnProp);
      return;
    }
    clientAPI.getDashboard().then((r) => {
      const ref = r.data?.client?.customer_reference;
      if (ref) setCrnState(ref);
    }).catch(() => {});
  }, [crnProp]);

  const crn = crnState || crnProp;

  const handleCopyCRN = () => {
    if (!crn) return;
    navigator.clipboard.writeText(crn).then(
      () => toast.success('CRN copied'),
      () => toast.error('Copy failed')
    );
  };

  const location = useLocation();
  const isSettingsActive = (pathname) => {
    const p = pathname || location.pathname;
    return p === '/settings' || p.startsWith('/settings/');
  };

  const showReports = hasFeature('reports_pdf') || hasFeature('reports_csv');
  const tabs = PORTAL_TABS.filter((t) => t.path !== '/reports' || showReports);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header: navy, CRN right, Ask Assistant + Logout right */}
      <header className="bg-midnight-blue text-white shadow-sm sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex justify-between items-center gap-4">
            <div className="flex items-center gap-4">
              <NavLink to="/dashboard" className="flex items-center gap-2 shrink-0">
                <h1 className="text-xl font-bold">Compliance Vault Pro</h1>
                <span className="text-sm text-gray-300 hidden sm:inline">AI-Driven Solutions & Compliance</span>
              </NavLink>
              {crn && (
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
              <span className="text-sm text-gray-300 truncate max-w-[120px] sm:max-w-[200px]" title={user?.email}>
                {user?.email}
              </span>
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
            <div className="flex flex-col lg:flex-row lg:space-x-1">
              {tabs.map(({ path, label, icon: Icon }) => (
                <NavLink
                  key={path}
                  to={path}
                  onClick={() => setMobileNavOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center px-3 py-3 lg:py-4 text-sm font-medium border-b-2 lg:border-b-2 transition-colors ${
                      isActive || (path === '/settings' && isSettingsActive(location.pathname))
                        ? 'border-electric-teal text-electric-teal'
                        : 'border-transparent text-gray-300 hover:text-white hover:border-gray-400'
                    }`
                  }
                >
                  <Icon className="w-4 h-4 mr-2" />
                  {label}
                </NavLink>
              ))}
            </div>
          </div>
        </nav>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </main>

      {/* Footer: Support + Help */}
      <footer className="border-t border-gray-200 bg-white py-4 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm text-gray-500">Compliance Vault Pro</span>
          <div className="flex items-center gap-4">
            <a
              href={`mailto:${SUPPORT_EMAIL}`}
              className="text-sm text-electric-teal hover:underline"
            >
              Support
            </a>
            <NavLink to="/help" className="text-sm text-electric-teal hover:underline flex items-center gap-1">
              <HelpCircle className="w-4 h-4" />
              Help
            </NavLink>
          </div>
        </div>
      </footer>
    </div>
  );
}
