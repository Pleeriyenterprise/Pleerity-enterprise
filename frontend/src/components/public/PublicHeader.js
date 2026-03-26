import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Button } from '../ui/button';
import { BRAND_LOGO_URL, branding } from '../../config/branding';
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

  // Platforms dropdown - Flagship products (comingSoon: greyed + unclickable)
  const platformLinks = [
    {
      href: '/compliance-vault-pro',
      label: 'Compliance Vault Pro',
      description: 'All-in-one compliance management for landlords',
      icon: Shield,
      badge: null,
      comingSoon: false,
    },
    {
      href: '/clearform',
      label: 'ClearForm',
      description: 'AI-powered document creation for individuals & small businesses',
      icon: FileText,
      badge: 'Coming Soon',
      comingSoon: true,
    },
    {
      href: '/products/assurestack',
      label: 'AssureStack',
      description: 'Always on. Always watching. (coming soon)',
      icon: Shield,
      badge: 'Coming Soon',
      comingSoon: true,
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
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-14 sm:h-16 gap-2">
          {/* Logo — slightly shorter on narrow phones to preserve nav tap target */}
          <Link
            to="/"
            className="flex items-center min-w-0 shrink-0 py-1 -my-1"
            data-testid="header-logo"
          >
            <img
              src={BRAND_LOGO_URL}
              alt={branding.companyName}
              className="h-7 w-auto max-h-8 sm:h-10 sm:max-h-none"
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
                        const content = (
                          <>
                            <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center flex-shrink-0">
                              <Icon className={cn("w-5 h-5", link.comingSoon ? "text-gray-400" : "text-emerald-600")} />
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <span className={cn("text-sm font-medium", link.comingSoon ? "text-gray-400" : "text-midnight-blue")}>{link.label}</span>
                                {link.badge && (
                                  <span className="text-xs bg-gray-300 text-gray-600 px-2 py-0.5 rounded-full">
                                    {link.badge}
                                  </span>
                                )}
                              </div>
                              <p className="text-sm text-gray-500 mt-1">{link.description}</p>
                            </div>
                          </>
                        );
                        return (
                          <li key={link.href + link.label}>
                            {link.comingSoon ? (
                              <div
                                className={cn(
                                  "flex items-start gap-3 select-none rounded-md p-3 leading-none cursor-not-allowed pointer-events-none opacity-75"
                                )}
                                aria-disabled="true"
                              >
                                {content}
                              </div>
                            ) : (
                              <NavigationMenuLink asChild>
                                <Link
                                  to={link.href}
                                  className={cn(
                                    "flex items-start gap-3 select-none rounded-md p-3 leading-none no-underline outline-none transition-colors hover:bg-gray-100",
                                    isActive(link.href) && "bg-gray-100"
                                  )}
                                >
                                  {content}
                                </Link>
                              </NavigationMenuLink>
                            )}
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

          {/* CTA + Portal Login */}
          <div className="hidden lg:flex items-center space-x-3">
            <Button asChild variant="default" className="bg-electric-teal hover:bg-electric-teal/90">
              <Link to="/risk-check">Check Your Compliance Risk</Link>
            </Button>
            <div className="flex items-center gap-2 text-sm">
              <Link
                to="/login"
                className="text-gray-700 hover:text-electric-teal font-medium transition-colors"
                data-testid="header-portal-login"
              >
                Portal login
              </Link>
              <span className="text-gray-300" aria-hidden>|</span>
              <Link
                to="/contractor/login"
                className="text-gray-600 hover:text-electric-teal font-medium transition-colors"
                data-testid="header-contractor-login"
              >
                Contractor
              </Link>
            </div>
          </div>

          {/* Mobile Menu Button */}
          <button
            className="lg:hidden p-2.5 rounded-md text-gray-700 hover:bg-gray-100 min-h-[44px] min-w-[44px]"
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
              {platformLinks.map((link) =>
                link.comingSoon ? (
                  <div
                    key={link.href + link.label}
                    className="flex items-center justify-between py-2 text-gray-400 cursor-not-allowed pointer-events-none"
                    aria-disabled="true"
                  >
                    <span>{link.label}</span>
                    {link.badge && (
                      <span className="text-xs bg-gray-300 text-gray-600 px-2 py-0.5 rounded-full">
                        {link.badge}
                      </span>
                    )}
                  </div>
                ) : (
                  <Link
                    key={link.href}
                    to={link.href}
                    className="flex items-center justify-between py-2.5 text-gray-700 hover:text-electric-teal min-h-[44px]"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <span>{link.label}</span>
                    {link.badge && (
                      <span className="text-xs bg-amber-500 text-white px-2 py-0.5 rounded-full">
                        {link.badge}
                      </span>
                    )}
                  </Link>
                )
              )}
            </div>

            {/* Services Section */}
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Services</div>
              {serviceLinks.map((link) => (
                <Link
                  key={link.href}
                  to={link.href}
                  className="block py-2.5 text-gray-700 hover:text-electric-teal min-h-[44px]"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  {link.label}
                </Link>
              ))}
            </div>

            {/* Other Links */}
            <div className="border-t border-gray-200 pt-4">
              <Link to="/pricing" className="block py-2.5 text-gray-700 hover:text-electric-teal min-h-[44px]" onClick={() => setMobileMenuOpen(false)}>
                Pricing
              </Link>
              <Link to="/insights" className="block py-2.5 text-gray-700 hover:text-electric-teal min-h-[44px]" onClick={() => setMobileMenuOpen(false)}>
                Insights
              </Link>
              <Link to="/about" className="block py-2.5 text-gray-700 hover:text-electric-teal min-h-[44px]" onClick={() => setMobileMenuOpen(false)}>
                About
              </Link>
              <Link to="/contact" className="block py-2.5 text-gray-700 hover:text-electric-teal min-h-[44px]" onClick={() => setMobileMenuOpen(false)}>
                Contact
              </Link>
            </div>

            {/* Mobile CTA + Portal Login */}
            <div className="border-t border-gray-200 pt-4 space-y-2">
              <Button className="w-full min-h-[48px] bg-electric-teal hover:bg-electric-teal/90" asChild>
                <Link to="/risk-check" onClick={() => setMobileMenuOpen(false)}>Check Your Compliance Risk</Link>
              </Button>
              <Button variant="outline" className="w-full min-h-[48px]" asChild>
                <Link to="/login" onClick={() => setMobileMenuOpen(false)}>Portal login</Link>
              </Button>
              <Button variant="outline" className="w-full min-h-[48px]" asChild>
                <Link to="/contractor/login" onClick={() => setMobileMenuOpen(false)}>Contractor login</Link>
              </Button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};

export default PublicHeader;
