import React, { useState, useEffect, useCallback } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Search, Eye, Download } from 'lucide-react';

const STATUS_OPTIONS = [
  { value: '__all__', label: 'All' },
  { value: 'NEW', label: 'NEW' },
  { value: 'IN_PROGRESS', label: 'IN_PROGRESS' },
  { value: 'RESPONDED', label: 'RESPONDED' },
  { value: 'CLOSED', label: 'CLOSED' },
  { value: 'SPAM', label: 'SPAM' },
];

const AdminContactEnquiriesPage = () => {
  const [result, setResult] = useState({ items: [], total: 0, page: 1, page_size: 20 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [q, setQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('__all__');
  const [searchInput, setSearchInput] = useState('');
  const API = process.env.REACT_APP_BACKEND_URL || '';

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ type: 'contact', page: 1, page_size: 50 });
      if (q) params.set('q', q);
      if (statusFilter && statusFilter !== '__all__') params.set('status', statusFilter);
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${API}/api/admin/submissions?${params}`, {
        headers: { ...(token && { Authorization: `Bearer ${token}` }) },
      });
      if (!res.ok) {
        if (res.status === 401) {
          setError('Session expired. Please sign in again.');
          return;
        }
        setError('Unable to load enquiries. Please try again.');
        return;
      }
      const data = await res.json();
      setResult(Array.isArray(data?.items) ? data : { items: [], total: 0, page: 1, page_size: 20 });
    } catch (e) {
      setError('Unable to load enquiries. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [API, q, statusFilter]);

  useEffect(() => { load(); }, [load]);

  const handleExportCsv = async () => {
    const params = new URLSearchParams({ type: 'contact' });
    if (q) params.set('q', q);
    if (statusFilter && statusFilter !== '__all__') params.set('status', statusFilter);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${API}/api/admin/submissions/export/csv?${params}`, {
        headers: { ...(token && { Authorization: `Bearer ${token}` }) },
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

  const handleSearch = () => setQ(searchInput.trim());

  const colors = { NEW: 'bg-blue-100 text-blue-700', IN_PROGRESS: 'bg-yellow-100 text-yellow-700', RESPONDED: 'bg-green-100 text-green-700', CLOSED: 'bg-gray-100 text-gray-500', SPAM: 'bg-red-100 text-red-700' };
  const items = result.items || [];

  return (
    <UnifiedAdminLayout>
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-2">Contact Enquiries</h1>
        <p className="text-gray-600 mb-6">Manage and respond to contact form submissions</p>

        {error && (
          <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-sm flex items-center justify-between">
            <span>{error}</span>
            <Button variant="outline" size="sm" onClick={() => window.location.href = '/login/admin'}>
              Go to sign in
            </Button>
          </div>
        )}

        <div className="flex flex-wrap gap-4 mb-4 items-center">
          <div className="flex gap-2 flex-1 min-w-[200px]">
            <Input
              placeholder="Search name, email, subject..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="max-w-xs"
            />
            <Button variant="secondary" size="sm" onClick={handleSearch}>
              <Search className="w-4 h-4 mr-1" /> Search
            </Button>
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-40"><SelectValue placeholder="Status" /></SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
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
              {loading ? (
                <tr><td colSpan="6" className="px-4 py-8 text-center">Loading...</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan="6" className="px-4 py-8 text-center">No enquiries</td></tr>
              ) : (
                items.map((e, idx) => {
                  const id = e.composite_id ? String(e.composite_id).replace(/^contact-/, '') : e.composite_id;
                  const rowKey = e.composite_id || `row-${idx}`;
                  return (
                    <tr key={rowKey} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm">{e.date ? new Date(e.date).toLocaleDateString() : '-'}</td>
                      <td className="px-4 py-3 text-sm font-medium">{e.name ?? '-'}</td>
                      <td className="px-4 py-3 text-sm">{e.email ?? '-'}</td>
                      <td className="px-4 py-3 text-sm">{e.subject ?? e.source ?? '-'}</td>
                      <td className="px-4 py-3"><Badge className={colors[e.status] || ''}>{e.status}</Badge></td>
                      <td className="px-4 py-3">
                        <Button size="sm" variant="outline" onClick={() => window.location.href = `/admin/submissions/contact/${id}`}>
                          <Eye className="w-4 h-4" />
                        </Button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </Card>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminContactEnquiriesPage;
