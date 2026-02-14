import React, { useState, useEffect, useCallback } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Search, Eye } from 'lucide-react';

const AdminTalentPoolPage = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [stats, setStats] = useState({});
  const API = process.env.REACT_APP_BACKEND_URL;

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (filter && filter !== 'all') params.append('status', filter);
      if (search) params.append('search', search);
      const res = await fetch(`${API}/api/talent-pool/admin/list?${params}`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (res.ok) setData(await res.json());
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  }, [API, filter, search]);

  const loadStats = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/talent-pool/admin/stats`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (res.ok) setStats(await res.json());
    } catch(e) {}
  }, [API]);

  useEffect(() => {
    load();
    loadStats();
  }, [filter, load, loadStats]);

  const colors = {'NEW':'bg-blue-100 text-blue-700','REVIEWED':'bg-gray-100 text-gray-700','SHORTLISTED':'bg-green-100 text-green-700','ARCHIVED':'bg-gray-100 text-gray-500'};

  return (
    <UnifiedAdminLayout>
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-2">Talent Pool</h1>
        <p className="text-gray-600 mb-8">Career applications</p>

        <div className="grid grid-cols-5 gap-4 mb-8">
          <Card className="p-4"><div className="text-sm text-gray-600">Total</div><div className="text-2xl font-bold">{stats.total || 0}</div></Card>
          <Card className="p-4"><div className="text-sm text-gray-600">New</div><div className="text-2xl font-bold text-blue-600">{stats.new || 0}</div></Card>
          <Card className="p-4"><div className="text-sm text-gray-600">Reviewed</div><div className="text-2xl font-bold">{stats.reviewed || 0}</div></Card>
          <Card className="p-4"><div className="text-sm text-gray-600">Shortlisted</div><div className="text-2xl font-bold text-green-600">{stats.shortlisted || 0}</div></Card>
          <Card className="p-4"><div className="text-sm text-gray-600">Archived</div><div className="text-2xl font-bold text-gray-400">{stats.archived || 0}</div></Card>
        </div>

        <div className="flex gap-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <Input placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)} className="pl-10" />
          </div>
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-48"><SelectValue placeholder="All statuses" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="NEW">New</SelectItem>
              <SelectItem value="REVIEWED">Reviewed</SelectItem>
              <SelectItem value="SHORTLISTED">Shortlisted</SelectItem>
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
                <th className="px-4 py-3 text-left text-xs font-semibold">Name</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Email</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Country</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loading ? <tr><td colSpan="6" className="px-4 py-8 text-center">Loading...</td></tr> :
              data.length === 0 ? <tr><td colSpan="6" className="px-4 py-8 text-center">No submissions</td></tr> :
              data.map(s => (
                <tr key={s.submission_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">{new Date(s.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-sm font-medium">{s.full_name}</td>
                  <td className="px-4 py-3 text-sm">{s.email}</td>
                  <td className="px-4 py-3 text-sm">{s.country}</td>
                  <td className="px-4 py-3"><Badge className={colors[s.status]}>{s.status}</Badge></td>
                  <td className="px-4 py-3"><Button size="sm" variant="outline" onClick={() => window.location.href=`/admin/talent-pool/${s.submission_id}`}><Eye className="w-4 h-4"/></Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminTalentPoolPage;
