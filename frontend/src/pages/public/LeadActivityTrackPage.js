/**
 * Lead activity tracking (for email links).
 * GET /track/lead-activity?lead_id=LEAD-xxx&activity_type=nurture_cta_clicked&redirect_url=https://...
 * Records the activity via POST /api/leads/activity then redirects to redirect_url or home.
 */
import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { recordLeadActivity } from '../../api/leadsApi';

const ALLOWED_TYPES = ['nurture_cta_clicked', 'nurture_email_opened', 'pricing_requested', 'consultation_request'];

export default function LeadActivityTrackPage() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState('loading'); // 'loading' | 'done' | 'error'

  useEffect(() => {
    const leadId = searchParams.get('lead_id');
    const activityType = searchParams.get('activity_type');
    const redirectUrl = searchParams.get('redirect_url');

    if (!leadId || !activityType) {
      setStatus('error');
      return;
    }
    if (!ALLOWED_TYPES.includes(activityType)) {
      setStatus('error');
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        await recordLeadActivity(leadId, activityType);
        if (!cancelled) setStatus('done');
      } catch {
        if (!cancelled) setStatus('error');
      }
      if (cancelled) return;
      const target = redirectUrl && redirectUrl.startsWith('http') ? redirectUrl : '/';
      window.location.href = target;
    })();
    return () => { cancelled = true; };
  }, [searchParams]);

  return (
    <div className="min-h-[40vh] flex items-center justify-center p-8">
      {status === 'loading' && (
        <p className="text-gray-500">Recording your click...</p>
      )}
      {status === 'done' && (
        <p className="text-gray-500">Redirecting...</p>
      )}
      {status === 'error' && (
        <p className="text-gray-500">Invalid link. <a href="/" className="text-teal-600 hover:underline">Go home</a></p>
      )}
    </div>
  );
}
