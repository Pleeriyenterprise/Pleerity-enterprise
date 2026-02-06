import React, { useState, useEffect } from 'react';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { ChevronDown, HelpCircle, Mail, Phone } from 'lucide-react';

const FAQPage = () => {
  const [faqs, setFaqs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState({});

  useEffect(() => {
    fetch(`${process.env.REACT_APP_BACKEND_URL}/api/faqs`)
      .then(res => res.json())
      .then(data => setFaqs(data))
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  const grouped = faqs.reduce((acc, faq) => {
    if (!acc[faq.category]) acc[faq.category] = [];
    acc[faq.category].push(faq);
    return acc;
  }, {});

  return (
    <PublicLayout>
      <SEOHead title="FAQ" canonicalUrl="/faq" />
      <div className="max-w-4xl mx-auto px-4 py-16">
        <div className="text-center mb-12">
          <HelpCircle className="w-12 h-12 text-electric-teal mx-auto mb-4" />
          <h1 className="text-4xl font-bold text-midnight-blue mb-4">Clear Answers. No Guesswork.</h1>
          <p className="text-lg text-gray-600">
            We believe transparency builds trust. Here are the questions clients ask most before starting with Pleerity.
          </p>
        </div>

        {loading ? <div className="text-center">Loading...</div> : (
          <div className="space-y-12">
            {Object.keys(grouped).map(cat => (
              <div key={cat}>
                <h2 className="text-2xl font-bold text-midnight-blue mb-6 pb-3 border-b-2 border-electric-teal">{cat}</h2>
                <div className="space-y-3">
                  {grouped[cat].map(faq => (
                    <div key={faq.faq_id} className="border rounded-lg hover:border-electric-teal transition-colors">
                      <button
                        onClick={() => setOpen({...open, [faq.faq_id]: !open[faq.faq_id]})}
                        className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-gray-50"
                      >
                        <h3 className="text-lg font-semibold text-midnight-blue pr-4">{faq.question}</h3>
                        <ChevronDown className={`w-5 h-5 text-electric-teal transition-transform ${open[faq.faq_id] ? 'rotate-180' : ''}`} />
                      </button>
                      {open[faq.faq_id] && (
                        <div className="px-6 py-4 bg-gray-50 border-t">
                          <p className="text-gray-700">{faq.answer}</p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="mt-16 bg-gray-50 rounded-lg p-8 text-center">
          <h3 className="text-2xl font-bold text-midnight-blue mb-3">Still Have Questions?</h3>
          <p className="text-gray-600 mb-6">Contact us:</p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <div className="flex items-center gap-2">
              <Mail className="w-5 h-5 text-electric-teal" />
              <a href="mailto:info@pleerityenterprise.co.uk" className="hover:text-electric-teal">info@pleerityenterprise.co.uk</a>
            </div>
            <div className="flex items-center gap-2">
              <Phone className="w-5 h-5 text-electric-teal" />
              <span>020 3337 6060</span>
            </div>
          </div>
        </div>
      </div>
    </PublicLayout>
  );
};

export default FAQPage;
