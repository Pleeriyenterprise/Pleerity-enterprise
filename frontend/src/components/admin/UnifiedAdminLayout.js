import React, { useState, useEffect } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Button } from '../ui/button';
import NotificationBell from './NotificationBell';
import api from '../../api/client';
import {
  LayoutDashboard,
  ClipboardCheck,
  CreditCard,
  Sparkles,
  LogOut,
  ChevronRight,
  ChevronDown,
  Package,
  FileText,
  Users,
  BookOpen,
  MessageSquare,
  Settings,
  BarChart3,
  Mail,
  Truck,
  HeadphonesIcon,
  Zap,
  Shield,
  History,
  Menu,
  Bell,
  Search,
  HelpCircle,
  PenTool,
  Target,
} from 'lucide-react';
import { cn } from '../../lib/utils';

/**
 * UnifiedAdminLayout - Enterprise-grade admin console with consolidated navigation
 */

const navSections = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: LayoutDashboard,
    items: [
      { href: '/admin/dashboard', label: 'Overview', icon: LayoutDashboard },
      { href: '/admin/analytics', label: 'Analytics', icon: BarChart3 },
    ],
  },
  {
    id: 'customers',
    label: 'Customers',
    icon: Users,
    items: [
      { href: '/admin/leads', label: 'Lead Management', icon: Target, badge: 'leads' },
      { href: '/admin/dashboard', label: 'Clients', icon: Users, tabTarget: 'clients' },
      { href: '/admin/orders', label: 'Orders Pipeline', icon: ClipboardCheck },
    ],
  },
  {
    id: 'products',
    label: 'Products & Services',
    icon: Package,
    items: [
      { href: '/admin/services', label: 'Service Catalogue', icon: Package },
      { href: '/admin/intake-schema', label: 'Intake Schema', icon: PenTool },
      { href: '/admin/billing', label: 'Pricing & Billing', icon: CreditCard },
    ],
  },
  {
    id: 'content',
    label: 'Content Management',
    icon: FileText,
    items: [
      { href: '/admin/knowledge-base', label: 'Knowledge Base', icon: BookOpen },
      { href: '/admin/blog', label: 'Blog / Insights', icon: FileText },
      { href: '/admin/support/responses', label: 'Canned Responses', icon: MessageSquare },
    ],
  },
  {
    id: 'support',
    label: 'Support',
    icon: HeadphonesIcon,
    items: [
      { href: '/admin/support', label: 'Support Dashboard', icon: HeadphonesIcon },
      { href: '/admin/postal-tracking', label: 'Postal Tracking', icon: Truck, badge: 'postal' },
    ],
  },
  {
    id: 'settings',
    label: 'Settings & System',
    icon: Settings,
    items: [
      { href: '/admin/dashboard', label: 'Team Management', icon: Shield, tabTarget: 'admins' },
      { href: '/admin/dashboard', label: 'Automation Rules', icon: Zap, tabTarget: 'rules' },
      { href: '/admin/dashboard', label: 'Email Templates', icon: Mail, tabTarget: 'templates' },
      { href: '/admin/dashboard', label: 'Audit Logs', icon: History, tabTarget: 'audit' },
      { href: '/admin/notifications/preferences', label: 'Notifications', icon: Bell },
    ],
  },
];

// Sidebar content component - defined outside to avoid re-creation
const SidebarContent = ({ 
  sidebarOpen, 
  expandedSections, 
  toggleSection, 
  handleNavClick, 
  isActive, 
  badges, 
  navigate, 
  user, 
  handleLogout 
}) => (
  <div className="flex flex-col h-full">
    {/* Logo */}
    <div className="p-4 border-b border-gray-200">
      <Link to="/admin/dashboard" className="flex items-center space-x-2">
        <div className="w-9 h-9 bg-gradient-to-br from-electric-teal to-teal-600 rounded-xl flex items-center justify-center shadow-lg">
          <span className="text-white font-bold text-lg">P</span>
        </div>
        {sidebarOpen && (
          <div className="flex flex-col">
            <span className="text-lg font-bold text-midnight-blue">Pleerity</span>
            <span className="text-[10px] font-medium text-gray-500 uppercase tracking-wider">Admin Console</span>
          </div>
        )}
      </Link>
    </div>

    {/* Navigation */}
    <nav className="flex-1 overflow-y-auto py-4 px-3">
      {navSections.map((section) => (
        <div key={section.id} className="mb-2">
          {/* Section Header */}
          <button
            onClick={() => toggleSection(section.id)}
            className={cn(
              "w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-colors",
              expandedSections.includes(section.id)
                ? "bg-gray-100 text-midnight-blue"
                : "text-gray-600 hover:bg-gray-50"
            )}
          >
            <div className="flex items-center gap-2">
              <section.icon className="w-4 h-4" />
              {sidebarOpen && <span>{section.label}</span>}
            </div>
            {sidebarOpen && (
              expandedSections.includes(section.id) 
                ? <ChevronDown className="w-4 h-4" />
                : <ChevronRight className="w-4 h-4" />
            )}
          </button>

          {/* Section Items */}
          {expandedSections.includes(section.id) && sidebarOpen && (
            <div className="mt-1 ml-4 space-y-1">
              {section.items.map((item) => (
                <button
                  key={item.href + (item.tabTarget || '')}
                  onClick={() => handleNavClick(item)}
                  data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
                  className={cn(
                    "w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors",
                    isActive(item.href, item.tabTarget)
                      ? "bg-electric-teal text-white"
                      : "text-gray-600 hover:bg-gray-100"
                  )}
                >
                  <div className="flex items-center gap-2">
                    <item.icon className="w-4 h-4" />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && badges[item.badge] > 0 && (
                    <span className={cn(
                      "px-2 py-0.5 text-xs font-bold rounded-full",
                      isActive(item.href, item.tabTarget)
                        ? "bg-white/20 text-white"
                        : "bg-red-500 text-white"
                    )}>
                      {badges[item.badge]}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </nav>

    {/* AI Assistant Quick Access */}
    <div className="p-4 border-t border-gray-200">
      <button
        onClick={() => navigate('/admin/assistant')}
        className="w-full flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-purple-500 to-indigo-600 text-white rounded-xl hover:from-purple-600 hover:to-indigo-700 transition-all shadow-lg"
      >
        <Sparkles className="w-5 h-5" />
        {sidebarOpen && (
          <div className="text-left">
            <span className="font-medium block">AI Assistant</span>
            <span className="text-xs opacity-80">Ask anything</span>
          </div>
        )}
      </button>
    </div>

    {/* User Info */}
    {sidebarOpen && (
      <div className="p-4 border-t border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center">
              <span className="text-sm font-medium text-gray-600">
                {user?.email?.[0]?.toUpperCase() || 'A'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">
                {user?.full_name || 'Admin'}
              </p>
              <p className="text-xs text-gray-500 truncate">{user?.email}</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            className="text-gray-500 hover:text-red-600"
          >
            <LogOut className="w-4 h-4" />
          </Button>
        </div>
      </div>
    )}
  </div>
);

const UnifiedAdminLayout = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, user } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [expandedSections, setExpandedSections] = useState(['dashboard', 'customers']);
  const [badges, setBadges] = useState({ leads: 0, postal: 0 });

  // Fetch badge counts
  useEffect(() => {
    const fetchBadges = async () => {
      try {
        const [leadsRes, postalRes] = await Promise.all([
          api.get('/admin/leads/notifications').catch(() => ({ data: { total_alerts: 0 } })),
          api.get('/admin/orders/postal/pending').catch(() => ({ data: { total: 0 } })),
        ]);
        setBadges({
          leads: leadsRes.data?.total_alerts || 0,
          postal: postalRes.data?.total || 0,
        });
      } catch (err) {
        console.error('Failed to fetch badges:', err);
      }
    };
    fetchBadges();
    const interval = setInterval(fetchBadges, 60000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const toggleSection = (sectionId) => {
    setExpandedSections(prev => 
      prev.includes(sectionId) 
        ? prev.filter(id => id !== sectionId)
        : [...prev, sectionId]
    );
  };

  const isActive = (path, tabTarget) => {
    if (tabTarget) {
      return location.pathname === path && location.search.includes(`tab=${tabTarget}`);
    }
    return location.pathname === path;
  };

  const handleNavClick = (item) => {
    if (item.tabTarget) {
      navigate(`${item.href}?tab=${item.tabTarget}`);
    } else {
      navigate(item.href);
    }
    setMobileMenuOpen(false);
  };

  const sidebarProps = {
    sidebarOpen,
    expandedSections,
    toggleSection,
    handleNavClick,
    isActive,
    badges,
    navigate,
    user,
    handleLogout,
  };

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Desktop Sidebar */}
      <aside
        className={cn(
          "hidden lg:flex flex-col bg-white border-r border-gray-200 transition-all duration-300",
          sidebarOpen ? "w-64" : "w-20"
        )}
      >
        <SidebarContent {...sidebarProps} />
      </aside>

      {/* Mobile Sidebar Overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="fixed inset-0 bg-black/50" onClick={() => setMobileMenuOpen(false)} />
          <aside className="fixed left-0 top-0 bottom-0 w-72 bg-white shadow-xl">
            <SidebarContent {...sidebarProps} />
          </aside>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header */}
        <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
          <div className="flex items-center justify-between h-16 px-4 lg:px-6">
            {/* Left: Menu Toggle & Search */}
            <div className="flex items-center gap-4">
              <button
                onClick={() => {
                  if (window.innerWidth >= 1024) {
                    setSidebarOpen(!sidebarOpen);
                  } else {
                    setMobileMenuOpen(!mobileMenuOpen);
                  }
                }}
                className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                <Menu className="w-5 h-5" />
              </button>
              
              {/* Quick Search */}
              <div className="hidden md:flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg w-64">
                <Search className="w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search clients, orders..."
                  className="bg-transparent border-none outline-none text-sm w-full"
                />
                <kbd className="text-xs text-gray-400 bg-white px-1.5 py-0.5 rounded border">⌘K</kbd>
              </div>
            </div>

            {/* Right: Actions */}
            <div className="flex items-center gap-2">
              <NotificationBell />
              
              <Link
                to="/support/knowledge-base"
                target="_blank"
                className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
                title="Help Center"
              >
                <HelpCircle className="w-5 h-5" />
              </Link>
              
              <div className="hidden lg:block">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleLogout}
                  className="text-gray-500 hover:text-red-600"
                >
                  <LogOut className="w-4 h-4 mr-2" />
                  Logout
                </Button>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-4 lg:p-6 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
};

export default UnifiedAdminLayout;
