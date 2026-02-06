import React, { useState, useEffect } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Users, Search, Eye, Filter } from 'lucide-react';

const AdminTalentPoolPage = () => {
  const [submissions, setSubmissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [stats, setStats] = useState({});

  const API_URL = process.env.REACT_APP_BACKEND_URL;

  useEffect(() => {
    loadSubmissions();
    loadStats();
  }, [statusFilter]);

  const loadSubmissions = async () => {
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.append('status', statusFilter);
      if (search) params.append('search', search);

      const response = await fetch(`${API_URL}/api/talent-pool/admin/list?${params}`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });

      if (response.ok) {
        const data = await response.json();
        setSubmissions(data);
      }
    } catch (error) {
      console.error('Failed to load submissions:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/talent-pool/admin/stats`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });

      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      'NEW': 'bg-blue-100 text-blue-700',
      'REVIEWED': 'bg-gray-100 text-gray-700',
      'SHORTLISTED': 'bg-green-100 text-green-700',
      'ARCHIVED': 'bg-gray-100 text-gray-500'
    };
    return colors[status] || 'bg-gray-100';
  };

  return (
    <UnifiedAdminLayout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-midnight-blue">Talent Pool</h1>
          <p className="text-gray-600 mt-2">Manage career applications and recruitment pipeline</p>
        </div>

        {/* Stats Cards */}
        <div className=\"grid grid-cols-2 md:grid-cols-5 gap-4 mb-8\">
          <Card className=\"p-4\">
            <div className=\"text-sm text-gray-600\">Total</div>
            <div className=\"text-2xl font-bold\">{stats.total || 0}</div>
          </Card>
          <Card className=\"p-4\">
            <div className=\"text-sm text-gray-600\">New</div>
            <div className=\"text-2xl font-bold text-blue-600\">{stats.new || 0}</div>
          </Card>
          <Card className=\"p-4\">
            <div className=\"text-sm text-gray-600\">Reviewed</div>
            <div className=\"text-2xl font-bold\">{stats.reviewed || 0}</div>
          </Card>
          <Card className=\"p-4\">
            <div className=\"text-sm text-gray-600\">Shortlisted</div>
            <div className=\"text-2xl font-bold text-green-600\">{stats.shortlisted || 0}</div>
          </Card>
          <Card className=\"p-4\">
            <div className=\"text-sm text-gray-600\">Archived</div>
            <div className=\"text-2xl font-bold text-gray-400\">{stats.archived || 0}</div>
          </Card>
        </div>

        {/* Filters */}
        <div className=\"flex gap-4 mb-6\">
          <div className=\"flex-1 relative\">
            <Search className=\"absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4\" />
            <Input
              placeholder=\"Search by name or email...\"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className=\"pl-10\"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className=\"w-48\">
              <Filter className=\"w-4 h-4 mr-2\" />
              <SelectValue placeholder=\"All statuses\" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value=\"\">All statuses</SelectItem>
              <SelectItem value=\"NEW\">New</SelectItem>
              <SelectItem value=\"REVIEWED\">Reviewed</SelectItem>
              <SelectItem value=\"SHORTLISTED\">Shortlisted</SelectItem>
              <SelectItem value=\"ARCHIVED\">Archived</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={loadSubmissions}>Apply</Button>
        </div>

        {/* Submissions Table */}
        <Card>
          <div className=\"overflow-x-auto\">
            <table className=\"w-full\">
              <thead className=\"bg-gray-50 border-b\">
                <tr>
                  <th className=\"px-4 py-3 text-left text-xs font-semibold text-gray-600\">Date</th>
                  <th className=\"px-4 py-3 text-left text-xs font-semibold text-gray-600\">Name</th>
                  <th className=\"px-4 py-3 text-left text-xs font-semibold text-gray-600\">Email</th>
                  <th className=\"px-4 py-3 text-left text-xs font-semibold text-gray-600\">Country</th>
                  <th className=\"px-4 py-3 text-left text-xs font-semibold text-gray-600\">Interests</th>
                  <th className=\"px-4 py-3 text-left text-xs font-semibold text-gray-600\">Experience</th>
                  <th className=\"px-4 py-3 text-left text-xs font-semibold text-gray-600\">Status</th>
                  <th className=\"px-4 py-3 text-left text-xs font-semibold text-gray-600\">Actions</th>
                </tr>
              </thead>
              <tbody className=\"divide-y\">
                {loading ? (
                  <tr><td colSpan=\"8\" className=\"px-4 py-8 text-center text-gray-500\">Loading...</td></tr>
                ) : submissions.length === 0 ? (
                  <tr><td colSpan=\"8\" className=\"px-4 py-8 text-center text-gray-500\">No submissions found</td></tr>
                ) : (
                  submissions.map(sub => (
                    <tr key={sub.submission_id} className=\"hover:bg-gray-50\">
                      <td className=\"px-4 py-3 text-sm text-gray-600\">
                        {new Date(sub.created_at).toLocaleDateString()}
                      </td>
                      <td className=\"px-4 py-3 text-sm font-medium\">{sub.full_name}</td>
                      <td className=\"px-4 py-3 text-sm text-gray-600\">{sub.email}</td>
                      <td className=\"px-4 py-3 text-sm text-gray-600\">{sub.country}</td>
                      <td className="px-4 py-3 text-xs">
                        {sub.interest_areas.slice(0, 2).map(area => (
                          <div key={area} className="text-gray-600">{area}</div>
                        ))}
                        {sub.interest_areas.length > 2 && <div className="text-gray-400">+{sub.interest_areas.length - 2} more</div>}
                      </td>
                      <td className=\"px-4 py-3 text-sm text-gray-600\">{sub.years_experience}</td>
                      <td className=\"px-4 py-3\">
                        <Badge className={getStatusColor(sub.status)}>{sub.status}</Badge>
                      </td>
                      <td className=\"px-4 py-3\">
                        <Button
                          size=\"sm\"
                          variant=\"outline\"
                          onClick={() => window.location.href = `/admin/talent-pool/${sub.submission_id}`}
                        >
                          <Eye className=\"w-4 h-4 mr-1\" />
                          View
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminTalentPoolPage;
