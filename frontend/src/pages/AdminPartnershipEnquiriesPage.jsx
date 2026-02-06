import React, { useState, useEffect } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Search, Eye } from 'lucide-react';

const AdminPartnershipEnquiriesPage = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('');
  const [stats, setStats] = useState({});
  const API = process.env.REACT_APP_BACKEND_URL;

  useEffect(() => { load(); loadStats(); }, [filter]);

  const load = async () => {
    try {
      const params = new URLSearchParams();
      if (filter) params.append('status', filter);
      if (search) params.append('search', search);
      const res = await fetch(`${API}/api/partnerships/admin/list?${params}`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (res.ok) setData(await res.json());
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  };

  const loadStats = async () => {
    try {
      const res = await fetch(`${API}/api/partnerships/admin/stats`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (res.ok) setStats(await res.json());
    } catch(e) {}
  };

  const colors = {'NEW':'bg-blue-100 text-blue-700','REVIEWED':'bg-gray-100 text-gray-700','APPROVED':'bg-green-100 text-green-700','REJECTED':'bg-red-100 text-red-700','ARCHIVED':'bg-gray-100 text-gray-500'};

  return (
    <UnifiedAdminLayout>
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-2">Partnership Enquiries</h1>
        <p className="text-gray-600 mb-8">Manage partnership proposals</p>

        <div className="grid grid-cols-6 gap-4 mb-8">
          <Card className="p-4"><div className="text-sm text-gray-600">Total</div><div className="text-2xl font-bold">{stats.total || 0}</div></Card>
          <Card className="p-4"><div className="text-sm text-gray-600">New</div><div className="text-2xl font-bold text-blue-600">{stats.new || 0}</div></Card>
          <Card className="p-4"><div className="text-sm text-gray-600">Reviewed</div><div className="text-2xl font-bold">{stats.reviewed || 0}</div></Card>
          <Card className="p-4"><div className="text-sm text-gray-600">Approved</div><div className="text-2xl font-bold text-green-600">{stats.approved || 0}</div></Card>
          <Card className="p-4"><div className="text-sm text-gray-600">Rejected</div><div className="text-2xl font-bold text-red-600">{stats.rejected || 0}</div></Card>
          <Card className="p-4"><div className="text-sm text-gray-600">Archived</div><div className="text-2xl font-bold text-gray-400">{stats.archived || 0}</div></Card>
        </div>

        <div className="flex gap-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <Input placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)} className="pl-10" />
          </div>
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-48"><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="">All</SelectItem>
              <SelectItem value="NEW">New</SelectItem>
              <SelectItem value="REVIEWED">Reviewed</SelectItem>
              <SelectItem value="APPROVED">Approved</SelectItem>
              <SelectItem value="REJECTED">Rejected</SelectItem>
              <SelectItem value="ARCHIVED">Archived</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={load}>Apply</Button>
        </div>

        <Card>
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold">Date</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Contact</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Company</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Email</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Type</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Country</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loading ? <tr><td colSpan="8" className="px-4 py-8 text-center">Loading...</td></tr> :
              data.length === 0 ? <tr><td colSpan="8" className="px-4 py-8 text-center">No enquiries</td></tr> :
              data.map(e => (
                <tr key={e.enquiry_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">{new Date(e.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-sm font-medium">{e.first_name} {e.last_name}</td>
                  <td className="px-4 py-3 text-sm">{e.company_name}</td>
                  <td className="px-4 py-3 text-sm">{e.work_email}</td>
                  <td className="px-4 py-3 text-xs">{e.partnership_type}</td>
                  <td className="px-4 py-3 text-sm">{e.country_region}</td>
                  <td className="px-4 py-3"><Badge className={colors[e.status]}>{e.status}</Badge></td>
                  <td className="px-4 py-3"><Button size="sm" variant="outline" onClick={() => window.location.href=`/admin/partnership-enquiries/${e.enquiry_id}`}><Eye className="w-4 h-4"/></Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminPartnershipEnquiriesPage;
