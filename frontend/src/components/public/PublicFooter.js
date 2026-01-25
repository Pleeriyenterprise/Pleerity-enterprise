import React from 'react';
import { Link } from 'react-router-dom';

const PublicFooter = () => {
  const currentYear = new Date().getFullYear();

  const platformLinks = [
    { href: '/compliance-vault-pro', label: 'Compliance Vault Pro' },
    { href: '/pricing', label: 'Pricing' },
    { href: '/booking', label: 'Book a Demo' },
  ];

  const serviceLinks = [
    { href: '/services/ai-automation', label: 'AI & Automation' },
    { href: '/services/market-research', label: 'Market Research' },
    { href: '/services/document-packs', label: 'Document Packs' },
    { href: '/services/compliance-audits', label: 'Compliance Audits' },
  ];

  const companyLinks = [
    { href: '/about', label: 'About Us' },
    { href: '/careers', label: 'Careers' },
    { href: '/partnerships', label: 'Partnerships' },
    { href: '/contact', label: 'Contact' },
  ];

  const legalLinks = [
    { href: '/legal/privacy', label: 'Privacy Policy' },
    { href: '/legal/terms', label: 'Terms of Service' },
  ];

  return (
    <footer className="bg-midnight-blue text-white">
      {/* Main Footer Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-8">
          {/* Brand Column */}
          <div className="col-span-2 md:col-span-4 lg:col-span-1">
            <div className="flex items-center space-x-2 mb-4">
              <img 
                src="/pleerity-logo.jpg" 
                alt="Pleerity" 
                className="h-10 w-auto"
              />
            </div>
            <p className="text-gray-400 text-sm mb-4">
              AI-Driven Solutions & Compliance
            </p>
            <p className="text-gray-500 text-xs">
              Pleerity Enterprise Ltd
            </p>
          </div>

          {/* Platform Links */}
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-300 mb-4">
              Platform
            </h3>
            <ul className="space-y-3">
              {platformLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    to={link.href}
                    className="text-gray-400 hover:text-electric-teal transition-colors text-sm"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Services Links */}
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-300 mb-4">
              Services
            </h3>
            <ul className="space-y-3">
              {serviceLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    to={link.href}
                    className="text-gray-400 hover:text-electric-teal transition-colors text-sm"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Company Links */}
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-300 mb-4">
              Company
            </h3>
            <ul className="space-y-3">
              {companyLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    to={link.href}
                    className="text-gray-400 hover:text-electric-teal transition-colors text-sm"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Legal Links */}
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-300 mb-4">
              Legal
            </h3>
            <ul className="space-y-3">
              {legalLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    to={link.href}
                    className="text-gray-400 hover:text-electric-teal transition-colors text-sm"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="border-t border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
            <p className="text-gray-500 text-sm">
              &copy; {currentYear} Pleerity Enterprise Ltd. All rights reserved.
            </p>
            <p className="text-gray-500 text-xs">
              Registered in England and Wales
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default PublicFooter;
