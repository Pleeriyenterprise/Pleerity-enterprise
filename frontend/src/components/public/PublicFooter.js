import React from 'react';
import { Link } from 'react-router-dom';
import { Facebook, MessageCircle } from 'lucide-react';

const PublicFooter = () => {
  const currentYear = new Date().getFullYear();

  const contactInfo = {
    company: 'Pleerity Enterprise Ltd',
    tagline: 'AI-Driven Solutions & Compliance',
    email: 'info@pleerityenterprise.co.uk',
    phone: '020 3337 6060',
  };

  const platformLinks = [
    { href: '/', label: 'Compliance Vault Pro' },
    { href: '/clearform', label: 'ClearForm' },
    { href: '/products/assurestack', label: 'AssureStack' },
  ];

  const serviceLinks = [
    { href: '/services/ai-automation', label: 'AI & Automation' },
    { href: '/services/market-research', label: 'Market Research' },
    { href: '/services/document-packs', label: 'Document Automation' },
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
    { href: '/legal/cookies', label: 'Cookie Policy' },
    { href: '/accessibility', label: 'Accessibility' },
  ];

  const supportLinks = [
    { href: '/newsletter', label: 'Newsletter' },
    { href: '/faq', label: 'FAQ' },
    { href: '/pricing', label: 'Pricing' },
    { href: '/login', label: 'Portal Login' },
  ];

  return (
    <footer className="bg-midnight-blue text-white">
      {/* Main Footer Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-8">
          {/* Column 1: Contact */}
          <div className="col-span-2 md:col-span-3 lg:col-span-1">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-300 mb-4">
              Contact
            </h3>
            <div className="space-y-3 text-sm text-gray-400">
              <p className="font-semibold text-white">{contactInfo.company}</p>
              <p className="text-xs text-gray-500">{contactInfo.tagline}</p>
              <p className="hover:text-electric-teal transition-colors">
                <a href={`mailto:${contactInfo.email}`}>{contactInfo.email}</a>
              </p>
              <p>{contactInfo.phone}</p>
              <div className="flex items-center gap-3 pt-2">
                <a 
                  href="https://www.facebook.com/pleerityenterpriseltd" 
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-8 h-8 rounded-full bg-white/10 hover:bg-electric-teal flex items-center justify-center transition-colors"
                  aria-label="Facebook"
                >
                  <Facebook className="w-4 h-4" />
                </a>
                <a 
                  href="https://whatsapp.com/channel/0029Vb607bG4SpkA6x2wFx07" 
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-8 h-8 rounded-full bg-white/10 hover:bg-electric-teal flex items-center justify-center transition-colors"
                  aria-label="WhatsApp"
                >
                  <MessageCircle className="w-4 h-4" />
                </a>
              </div>
            </div>
          </div>

          {/* Column 2: Platforms */}
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-300 mb-4">
              Platforms
            </h3>
            <ul className="space-y-3">
              {platformLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    to={link.href}
                    className="text-gray-400 hover:text-electric-teal transition-colors text-sm block"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Column 3: Services */}
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-300 mb-4">
              Services
            </h3>
            <ul className="space-y-3">
              {serviceLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    to={link.href}
                    className="text-gray-400 hover:text-electric-teal transition-colors text-sm block"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Column 4: Company */}
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-300 mb-4">
              Company
            </h3>
            <ul className="space-y-3">
              {companyLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    to={link.href}
                    className="text-gray-400 hover:text-electric-teal transition-colors text-sm block"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Column 5: Legal */}
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-300 mb-4">
              Legal
            </h3>
            <ul className="space-y-3">
              {legalLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    to={link.href}
                    className="text-gray-400 hover:text-electric-teal transition-colors text-sm block"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Column 6: Support */}
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-300 mb-4">
              Support
            </h3>
            <ul className="space-y-3">
              {supportLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    to={link.href}
                    className="text-gray-400 hover:text-electric-teal transition-colors text-sm block"
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
          <div className="flex flex-col md:flex-row justify-between items-center space-y-2 md:space-y-0">
            <p className="text-gray-500 text-sm">
              &copy; {currentYear} Pleerity Enterprise Ltd. All rights reserved.
            </p>
            <p className="text-gray-500 text-xs">
              Registered in Scotland | Company No. SC855023
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default PublicFooter;
