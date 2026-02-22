import React, { useState, useEffect } from 'react';
import { clientAPI } from '../api/client';
import { History, FileText, Mail, Shield, Activity } from 'lucide-react';

export default function ClientAuditLogPage() {
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    clientAPI
      .getAuditTimeline(80)
      .then((res) => {
        if (!cancelled && res?.data?.timeline) setTimeline(res.data.timeline);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || 'Failed to load audit log');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const iconForAction = (action) => {
    if (action?.includes('DOCUMENT')) return <FileText className="w-5 h-5" />;
    if (action?.includes('EMAIL') || action?.includes('MESSAGE') || action?.includes('REMINDER') || action?.includes('DIGEST')) return <Mail className="w-5 h-5" />;
    if (action?.includes('LOGIN') || action?.includes('PASSWORD') || action?.includes('PORTAL_INVITE')) return <Shield className="w-5 h-5" />;
    return <Activity className="w-5 h-5" />;
  };

  const badgeClass = (action) => {
    if (action?.includes('SUCCESS') || action?.includes('COMPLETE')) return 'bg-green-100 text-green-600';
    if (action?.includes('FAILED')) return 'bg-red-100 text-red-600';
    return 'bg-electric-teal/10 text-electric-teal';
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-midnight-blue flex items-center gap-2">
          <History className="w-7 h-7" />
          Audit Log
        </h2>
        <p className="text-gray-600 mt-1">Recent activity for your account (read-only).</p>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-10 w-10 border-2 border-electric-teal border-t-transparent" />
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3">
          {error}
        </div>
      )}

      {!loading && !error && (
        <div className="space-y-3">
          {timeline.length === 0 ? (
            <p className="text-gray-500 text-center py-8">No audit events found</p>
          ) : (
            timeline.map((event, idx) => (
              <div key={idx} className="flex gap-4 p-4 bg-gray-50 rounded-lg">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${badgeClass(event.action)}`}
                >
                  {iconForAction(event.action)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-midnight-blue">
                    {event.action?.replace(/_/g, ' ')}
                  </p>
                  <p className="text-sm text-gray-500">
                    {event.timestamp ? new Date(event.timestamp).toLocaleString() : '—'}
                  </p>
                  {event.metadata && Object.keys(event.metadata).length > 0 && (
                    <div className="mt-2 text-xs text-gray-400 bg-white p-2 rounded max-h-24 overflow-auto">
                      {JSON.stringify(event.metadata)}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
