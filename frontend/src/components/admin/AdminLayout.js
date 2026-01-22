import React from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Button } from '../ui/button';
import NotificationBell from './NotificationBell';
import {
  LayoutDashboard,
  ClipboardCheck,
  CreditCard,
  Sparkles,
  LogOut,
  ChevronRight,
  Package,
  FileText,
} from 'lucide-react';

/**
 * AdminLayout - Shared layout for admin pages outside the main dashboard
 */
const AdminLayout = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { href: '/admin/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/admin/orders', label: 'Orders Pipeline', icon: ClipboardCheck },
    { href: '/admin/services', label: 'Service Catalogue', icon: Package },
    { href: '/admin/blog', label: 'Blog', icon: FileText },
    { href: '/admin/billing', label: 'Billing', icon: CreditCard },
    { href: '/admin/assistant', label: 'AI Assistant', icon: Sparkles },
  ];

  const isActive = (path) => location.pathname === path;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-midnight-blue text-white sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link to="/admin/dashboard" className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-electric-teal rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-lg">P</span>
              </div>
              <span className="text-xl font-bold">Pleerity</span>
              <span className="px-2 py-1 bg-white/10 rounded text-xs font-medium">ADMIN</span>
            </Link>
            
            <nav className="hidden md:flex items-center space-x-1">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  to={item.href}
                  className={`flex items-center px-4 py-2 rounded-lg transition-colors ${
                    isActive(item.href)
                      ? 'bg-white/20 text-white'
                      : 'text-gray-300 hover:bg-white/10 hover:text-white'
                  }`}
                >
                  <item.icon className="w-4 h-4 mr-2" />
                  {item.label}
                </Link>
              ))}
            </nav>

            <Button
              variant="ghost"
              className="text-gray-300 hover:text-white hover:bg-white/10"
              onClick={handleLogout}
            >
              <LogOut className="w-4 h-4 mr-2" />
              Logout
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
};

export default AdminLayout;
