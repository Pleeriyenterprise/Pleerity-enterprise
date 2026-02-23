import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { BarChart3, Calendar, FileText, Shield } from 'lucide-react';

const DEMO_IMAGES = [
  { key: 'dashboard', src: '/demo/dashboard.png', title: 'Dashboard Overview', icon: Shield },
  { key: 'calendar', src: '/demo/calendar.png', title: 'Compliance Calendar', icon: Calendar },
  { key: 'documents', src: '/demo/documents.png', title: 'Documents & AI Scanner', icon: FileText },
  { key: 'score', src: '/demo/score.png', title: 'Compliance Score Breakdown', icon: BarChart3 },
];

/**
 * Platform demo page (MVP, no auth). Four image panels + fallback when assets are missing.
 * CTA: Start Your Setup → /intake/start.
 */
const DemoPage = () => {
  const [loaded, setLoaded] = useState({});
  const [failed, setFailed] = useState({});

  const handleLoad = (key) => () => setLoaded((p) => ({ ...p, [key]: true }));
  const handleError = (key) => () => setFailed((p) => ({ ...p, [key]: true }));

  return (
    <PublicLayout>
      <SEOHead
        title="Compliance Vault Pro – Platform Demo"
        description="See how Compliance Vault Pro helps UK landlords track certificate expiry dates, monitor compliance, and generate audit-ready reports. Dashboard, calendar, documents, and score overview."
        canonicalUrl="/demo"
      />

      <section className="py-16 lg:py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl sm:text-4xl font-bold text-midnight-blue mb-4 text-center">
            Compliance Vault Pro – Platform Demo
          </h1>
          <p className="text-lg text-gray-600 text-center mb-12 max-w-2xl mx-auto">
            A quick look at the platform: track certificates, see expiries, store documents, and view your compliance score. 
            This is a tracking and organisation tool — not legal advice.
          </p>

          {DEMO_IMAGES.map((item) => (
            <div key={item.key} className="mb-12">
              <h2 className="text-xl font-semibold text-midnight-blue mb-4 flex items-center gap-2">
                <item.icon className="w-5 h-5 text-electric-teal" />
                {item.title}
              </h2>
              <div className="rounded-xl border border-gray-200 shadow-md overflow-hidden bg-white max-w-4xl">
                {failed[item.key] ? (
                  <div className="aspect-video flex flex-col items-center justify-center bg-gray-50 text-gray-500 p-8">
                    <item.icon className="w-12 h-12 mb-3 opacity-50" />
                    <p className="font-medium">Demo assets coming soon</p>
                    <p className="text-sm mt-1">Add {item.key}.png to public/demo/ for a preview image.</p>
                  </div>
                ) : (
                  <div className="relative bg-gray-50">
                    {!loaded[item.key] && (
                      <div className="aspect-video animate-pulse flex items-center justify-center">
                        <span className="text-sm text-gray-400">Loading…</span>
                      </div>
                    )}
                    <img
                      src={item.src}
                      alt={item.title}
                      className={`w-full h-auto max-h-[480px] object-contain object-top ${loaded[item.key] ? 'block' : 'absolute inset-0 opacity-0'}`}
                      onLoad={handleLoad(item.key)}
                      onError={handleError(item.key)}
                    />
                  </div>
                )}
              </div>
            </div>
          ))}

          <div className="text-center pt-8 border-t border-gray-200">
            <p className="text-gray-600 mb-6">Ready to set up your own portfolio?</p>
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
              asChild
            >
              <Link to="/intake/start">Start Your Setup</Link>
            </Button>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default DemoPage;
