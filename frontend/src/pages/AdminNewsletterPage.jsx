import React, { useState, useEffect } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Mail, Download } from 'lucide-react';

const AdminNewsletterPage = () => {
  const [subs, setSubs] = useState([]);
  const [loading, setLoading] = useState(true);
  const API = process.env.REACT_APP_BACKEND_URL;

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch(`${API}/api/admin/newsletter/subscribers`, { headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } });
        if (cancelled) return;
        if (res.ok) setSubs(await res.json());
      } catch (e) {}
      finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [API]);

  const exportCSV = () => {
    const csv = ['Email,Status,Source,Subscribed Date\n', ...subs.map(s => `${s.email},${s.status},${s.source},${s.subscribed_at}`)].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'newsletter_subscribers.csv';
    a.click();
  };

  return (
    <UnifiedAdminLayout>
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h1 className="text-3xl font-bold">Newsletter Subscribers</h1>
            <p className="text-gray-600 mt-2">{subs.length} total subscribers</p>
          </div>
          <Button onClick={exportCSV}><Download className="w-4 h-4 mr-2"/>Export CSV</Button>
        </div>
        
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <p className="text-sm text-blue-800">
            ℹ️ <strong>Email campaigns are sent via Kit.</strong> This dashboard manages subscriber intake and Kit sync status only.
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
              {loading ? <tr><td colSpan="5" className="px-4 py-8 text-center">Loading...</td></tr> :
              subs.length === 0 ? <tr><td colSpan="5" className="px-4 py-8 text-center">No subscribers</td></tr> :
              subs.map(s => (
                <tr key={s.subscriber_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">{s.email}</td>
                  <td className="px-4 py-3"><Badge>{s.status}</Badge></td>
                  <td className="px-4 py-3 text-sm text-gray-600">{s.source}</td>
                  <td className="px-4 py-3">
                    <Badge className={s.kit_sync_status === 'SYNCED' ? 'bg-green-100 text-green-700' : s.kit_sync_status === 'FAILED' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'}>
                      {s.kit_sync_status || 'PENDING'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{new Date(s.subscribed_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminNewsletterPage;
