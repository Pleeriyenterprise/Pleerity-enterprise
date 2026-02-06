import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Button } from '../ui/button';
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
} from '../ui/navigation-menu';
import { Menu, X, ChevronDown, FileText, Shield } from 'lucide-react';
import { cn } from '../../lib/utils';

const PublicHeader = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();

  const isActive = (path) => location.pathname === path || location.pathname.startsWith(path + '/');

  // Platforms dropdown - Flagship products
  const platformLinks = [
    { 
      href: '/', 
      label: 'Compliance Vault Pro', 
      description: 'All-in-one compliance management for landlords',
      icon: Shield,
      badge: null,
    },
    { 
      href: '/clearform', 
      label: 'ClearForm', 
      description: 'AI-powered document creation for individuals & small businesses',
      icon: FileText,
      badge: 'Coming Soon',
    },
    { 
      href: '/products/assurestack', 
      label: 'AssureStack', 
      description: 'Always on. Always watching. (coming soon)',
      icon: Shield,
      badge: 'Coming Soon',
    },
  ];

  const serviceLinks = [
    { href: '/services/ai-automation', label: 'AI & Automation', description: 'Automate repetitive tasks' },
    { href: '/services/market-research', label: 'Market Research', description: 'Property market insights' },
    { href: '/services/document-packs', label: 'Document Packs', description: 'Ready-to-use legal documents' },
    { href: '/services/compliance-audits', label: 'Compliance Audits', description: 'HMO and full property audits' },
  ];

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center space-x-2" data-testid="header-logo">
            <img 
              src="/pleerity-logo.jpg" 
              alt="Pleerity" 
              className="h-10 w-auto"
            />
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden lg:flex items-center space-x-1">
            <NavigationMenu>
              <NavigationMenuList>
                {/* Platforms Dropdown */}
                <NavigationMenuItem>
                  <NavigationMenuTrigger className="text-gray-700 hover:text-midnight-blue">
                    Platforms
                  </NavigationMenuTrigger>
                  <NavigationMenuContent>
                    <ul className="grid w-[450px] gap-3 p-4">
                      {platformLinks.map((link) => {
                        const Icon = link.icon;
                        return (
                          <li key={link.href}>
                            <NavigationMenuLink asChild>
                              <Link
                                to={link.href}
                                className={cn(
                                  "flex items-start gap-3 select-none rounded-md p-3 leading-none no-underline outline-none transition-colors hover:bg-gray-100",
                                  isActive(link.href) && "bg-gray-100"
                                )}
                              >
                                <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center flex-shrink-0">
                                  <Icon className="w-5 h-5 text-emerald-600" />
                                </div>
                                <div className="flex-1">
                                  <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-midnight-blue">{link.label}</span>
                                    {link.badge && (
                                      <span className="text-xs bg-emerald-500 text-white px-2 py-0.5 rounded-full">
                                        {link.badge}
                                      </span>
                                    )}
                                  </div>
                                  <p className="text-sm text-gray-500 mt-1">{link.description}</p>
                                </div>
                              </Link>
                            </NavigationMenuLink>
                          </li>
                        );
                      })}
                    </ul>
                  </NavigationMenuContent>
                </NavigationMenuItem>

                {/* Services Dropdown */}
                <NavigationMenuItem>
                  <NavigationMenuTrigger className="text-gray-700 hover:text-midnight-blue">
                    Services
                  </NavigationMenuTrigger>
                  <NavigationMenuContent>
                    <ul className="grid w-[500px] gap-3 p-4 md:grid-cols-2">
                      {serviceLinks.map((link) => (
                        <li key={link.href}>
                          <NavigationMenuLink asChild>
                            <Link
                              to={link.href}
                              className={cn(
                                "block select-none space-y-1 rounded-md p-3 leading-none no-underline outline-none transition-colors hover:bg-gray-100",
                                isActive(link.href) && "bg-gray-100"
                              )}
                            >
                              <div className="text-sm font-medium text-midnight-blue">{link.label}</div>
                              <p className="line-clamp-2 text-sm text-gray-500">{link.description}</p>
                            </Link>
                          </NavigationMenuLink>
                        </li>
                      ))}
                    </ul>
                  </NavigationMenuContent>
                </NavigationMenuItem>

                {/* Direct Links */}
                <NavigationMenuItem>
                  <Link
                    to="/pricing"
                    className={cn(
                      "px-4 py-2 text-sm font-medium rounded-md transition-colors",
                      isActive('/pricing') ? "text-electric-teal" : "text-gray-700 hover:text-midnight-blue"
                    )}
                  >
                    Pricing
                  </Link>
                </NavigationMenuItem>

                <NavigationMenuItem>
                  <Link
                    to="/insights"
                    className={cn(
                      "px-4 py-2 text-sm font-medium rounded-md transition-colors",
                      location.pathname.startsWith('/insights') ? "text-electric-teal" : "text-gray-700 hover:text-midnight-blue"
                    )}
                  >
                    Insights
                  </Link>
                </NavigationMenuItem>

                <NavigationMenuItem>
                  <Link
                    to="/about"
                    className={cn(
                      "px-4 py-2 text-sm font-medium rounded-md transition-colors",
                      isActive('/about') ? "text-electric-teal" : "text-gray-700 hover:text-midnight-blue"
                    )}
                  >
                    About
                  </Link>
                </NavigationMenuItem>
              </NavigationMenuList>
            </NavigationMenu>
          </nav>

          {/* Portal Login Link */}
          <div className="hidden lg:flex items-center space-x-3">
            <Link 
              to="/login" 
              className="text-gray-700 hover:text-electric-teal font-medium text-sm transition-colors"
              data-testid="header-portal-login"
            >
              Portal Login
            </Link>
          </div>

          {/* Mobile Menu Button */}
          <button
            className="lg:hidden p-2 rounded-md text-gray-700 hover:bg-gray-100"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            data-testid="mobile-menu-toggle"
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden bg-white border-t border-gray-200">
          <div className="px-4 py-4 space-y-4">
            {/* Platforms Section */}
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Platforms</div>
              {platformLinks.map((link) => (
                <Link
                  key={link.href}
                  to={link.href}
                  className="flex items-center justify-between py-2 text-gray-700 hover:text-electric-teal"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  <span>{link.label}</span>
                  {link.badge && (
                    <span className="text-xs bg-amber-500 text-white px-2 py-0.5 rounded-full">
                      {link.badge}
                    </span>
                  )}
                </Link>
              ))}
            </div>

            {/* Services Section */}
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Services</div>
              {serviceLinks.map((link) => (
                <Link
                  key={link.href}
                  to={link.href}
                  className="block py-2 text-gray-700 hover:text-electric-teal"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  {link.label}
                </Link>
              ))}
            </div>

            {/* Other Links */}
            <div className="border-t border-gray-200 pt-4">
              <Link to="/pricing" className="block py-2 text-gray-700 hover:text-electric-teal" onClick={() => setMobileMenuOpen(false)}>
                Pricing
              </Link>
              <Link to="/insights" className="block py-2 text-gray-700 hover:text-electric-teal" onClick={() => setMobileMenuOpen(false)}>
                Insights
              </Link>
              <Link to="/about" className="block py-2 text-gray-700 hover:text-electric-teal" onClick={() => setMobileMenuOpen(false)}>
                About
              </Link>
              <Link to="/contact" className="block py-2 text-gray-700 hover:text-electric-teal" onClick={() => setMobileMenuOpen(false)}>
                Contact
              </Link>
            </div>

            {/* Mobile Portal Login */}
            <div className="border-t border-gray-200 pt-4">
              <Button className="w-full bg-electric-teal hover:bg-electric-teal/90" asChild>
                <Link to="/login" onClick={() => setMobileMenuOpen(false)}>Portal Login</Link>
              </Button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};

export default PublicHeader;
