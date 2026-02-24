import React, { useState, useEffect } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Mail, Search, Eye, Send, Download } from 'lucide-react';

const AdminContactEnquiriesPage = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const API = process.env.REACT_APP_BACKEND_URL;

  const handleExportCsv = async () => {
    try {
      const res = await fetch(`${API}/api/admin/submissions/export/csv?type=contact`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      if (!res.ok) return;
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'submissions_contact.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) {}
  };

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch(`${API}/api/admin/contact/enquiries`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if (cancelled) return;
        if (res.ok) setData(await res.json());
      } catch (e) {}
      finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [API]);

  const colors = {'NEW':'bg-blue-100 text-blue-700','IN_PROGRESS':'bg-yellow-100 text-yellow-700','RESPONDED':'bg-green-100 text-green-700','CLOSED':'bg-gray-100 text-gray-500','SPAM':'bg-red-100 text-red-700'};

  return (
    <UnifiedAdminLayout>
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-2">Contact Enquiries</h1>
        <p className="text-gray-600 mb-8">Manage and respond to contact form submissions</p>

        <div className="mb-4">
          <Button variant="outline" size="sm" onClick={handleExportCsv}>
            <Download className="w-4 h-4 mr-2" /> Export CSV
          </Button>
        </div>

        <Card>
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold">Date</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Name</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Email</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Subject</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loading ? <tr><td colSpan="6" className="px-4 py-8 text-center">Loading...</td></tr> :
              data.length === 0 ? <tr><td colSpan="6" className="px-4 py-8 text-center">No enquiries</td></tr> :
              data.map(e => (
                <tr key={e.enquiry_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">{new Date(e.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-sm font-medium">{e.full_name}</td>
                  <td className="px-4 py-3 text-sm">{e.email}</td>
                  <td className="px-4 py-3 text-sm">{e.subject}</td>
                  <td className="px-4 py-3"><Badge className={colors[e.status]}>{e.status}</Badge></td>
                  <td className="px-4 py-3"><Button size="sm" variant="outline" onClick={() => window.location.href=`/admin/submissions/contact/${e.enquiry_id}`}><Eye className="w-4 h-4"/></Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminContactEnquiriesPage;
