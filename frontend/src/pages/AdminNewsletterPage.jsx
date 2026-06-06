import React, { useMemo } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import AdminFetchStatePanel from '../components/admin/AdminFetchStatePanel';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Mail, Download, RefreshCw } from 'lucide-react';
import { adminAPI } from '../api/client';
import { useAuthenticatedQuery } from '../hooks/useAuthenticatedQuery';

const AdminNewsletterPage = () => {
  const { data, loading, error, reload } = useAuthenticatedQuery(
    () => adminAPI.listNewsletterSubscribers(),
    [],
  );
  const subs = useMemo(() => (Array.isArray(data) ? data : []), [data]);

  const exportCSV = () => {
    const csv = ['Email,Status,Source,Kit Sync,Subscribed Date\n', ...subs.map((s) => `${s.email},${s.status},${s.source},${s.kit_sync_status || 'PENDING'},${s.subscribed_at}`)].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'newsletter_subscribers.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <UnifiedAdminLayout>
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h1 className="text-3xl font-bold">Newsletter Subscribers</h1>
            <p className="text-gray-600 mt-2">
              {loading ? 'Loading…' : error ? '—' : `${subs.length} total subscribers`}
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={reload} disabled={loading}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
            <Button onClick={exportCSV} disabled={loading || Boolean(error) || subs.length === 0}>
              <Download className="w-4 h-4 mr-2" />
              Export CSV
            </Button>
          </div>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <p className="text-sm text-blue-800">
            <Mail className="w-4 h-4 inline mr-1" />
            <strong>Email campaigns are sent via Kit.</strong> This dashboard manages subscriber intake and Kit sync status only.
          </p>
        </div>

        <Card>
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold">Email</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Source</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Kit Sync</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Subscribed</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              <AdminFetchStatePanel
                loading={loading}
                error={error}
                isEmpty={!loading && !error && subs.length === 0}
                emptyMessage="No subscribers yet."
                colSpan={5}
                onRetry={reload}
              >
                {subs.map((s) => (
                  <tr key={s.subscriber_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm">{s.email}</td>
                    <td className="px-4 py-3">
                      <Badge>{s.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{s.source}</td>
                    <td className="px-4 py-3">
                      <Badge
                        className={
                          s.kit_sync_status === 'SYNCED'
                            ? 'bg-green-100 text-green-700'
                            : s.kit_sync_status === 'FAILED'
                              ? 'bg-red-100 text-red-700'
                              : 'bg-gray-100 text-gray-600'
                        }
                      >
                        {s.kit_sync_status || 'PENDING'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {s.subscribed_at ? new Date(s.subscribed_at).toLocaleDateString() : '—'}
                    </td>
                  </tr>
                ))}
              </AdminFetchStatePanel>
            </tbody>
          </table>
        </Card>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminNewsletterPage;
