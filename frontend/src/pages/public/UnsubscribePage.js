/**
 * Public unsubscribe page for lead marketing emails.
 * URL: /unsubscribe?lead=LEAD-xxx
 * Calls POST /api/leads/unsubscribe/:lead_id and shows confirmation.
 */

import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import client from '../../api/client';

export default function UnsubscribePage() {
  const [searchParams] = useSearchParams();
  const leadId = searchParams.get('lead');
  const [status, setStatus] = useState('loading'); // 'loading' | 'success' | 'error' | 'missing'
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!leadId) {
      setStatus('missing');
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const { data } = await client.post(`/leads/unsubscribe/${leadId}`);
        if (!cancelled) {
          setStatus('success');
          setMessage(data?.message || 'You have been unsubscribed from marketing emails.');
        }
      } catch (err) {
        if (!cancelled) {
          setStatus('error');
          setMessage(err.response?.data?.detail || err.message || 'Something went wrong.');
        }
      }
    })();
    return () => { cancelled = true; };
  }, [leadId]);

  return (
    <PublicLayout>
      <SEOHead
        title="Unsubscribe"
        description="Unsubscribe from marketing emails."
        canonicalUrl="/unsubscribe"
      />
      <div className="min-h-[50vh] flex flex-col items-center justify-center px-4 py-16">
        <div className="max-w-md mx-auto text-center">
          {status === 'loading' && (
            <p className="text-gray-600">Processing your request…</p>
          )}
          {status === 'missing' && (
            <>
              <h1 className="text-xl font-bold text-midnight-blue mb-2">Invalid link</h1>
              <p className="text-gray-600">This unsubscribe link is invalid or has expired.</p>
            </>
          )}
          {status === 'success' && (
            <>
              <h1 className="text-xl font-bold text-midnight-blue mb-2">You're unsubscribed</h1>
              <p className="text-gray-600">{message}</p>
            </>
          )}
          {status === 'error' && (
            <>
              <h1 className="text-xl font-bold text-midnight-blue mb-2">Unable to unsubscribe</h1>
              <p className="text-gray-600">{message}</p>
            </>
          )}
        </div>
      </div>
    </PublicLayout>
  );
}
