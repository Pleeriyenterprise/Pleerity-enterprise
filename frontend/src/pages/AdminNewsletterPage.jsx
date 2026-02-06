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

  useEffect(() => { load(); }, []);

  const load = async () => {
    try {
      const res = await fetch(`${API}/api/admin/newsletter/subscribers`, { headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } });
      if (res.ok) setSubs(await res.json());
    } catch(e) {}
    finally { setLoading(false); }
  };

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
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold">Newsletter Subscribers</h1>
            <p className="text-gray-600 mt-2">{subs.length} total subscribers</p>
          </div>
          <Button onClick={exportCSV}><Download className="w-4 h-4 mr-2"/>Export CSV</Button>
        </div>

        <Card>
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold">Email</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Source</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Subscribed</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loading ? <tr><td colSpan="4" className="px-4 py-8 text-center">Loading...</td></tr> :
              subs.length === 0 ? <tr><td colSpan="4" className="px-4 py-8 text-center">No subscribers</td></tr> :
              subs.map(s => (
                <tr key={s.subscriber_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">{s.email}</td>
                  <td className="px-4 py-3"><Badge>{s.status}</Badge></td>
                  <td className="px-4 py-3 text-sm text-gray-600">{s.source}</td>
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
