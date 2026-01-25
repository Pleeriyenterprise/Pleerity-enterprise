/**
 * ClearForm Admin Page - Documents Tab
 * 
 * Admin view for managing ClearForm documents.
 */

import React, { useState, useEffect } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { 
  FileText, 
  Search,
  Loader2,
  RefreshCw,
  Download,
  Eye,
  CheckCircle,
  XCircle,
  Clock
} from 'lucide-react';
import api from '../api/client';

const AdminClearFormDocumentsPage = () => {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [stats, setStats] = useState({
    total: 0,
    completed: 0,
    failed: 0,
    pending: 0
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      // Note: These endpoints would need to be created in the backend
      const docsRes = await api.get('/admin/clearform/documents').catch(() => ({ data: { documents: [] } }));
      const statsRes = await api.get('/admin/clearform/documents/stats').catch(() => ({ 
        data: { total: 0, completed: 0, failed: 0, pending: 0 } 
      }));
      
      setDocuments(docsRes.data?.documents || []);
      setStats(statsRes.data || {});
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'FAILED':
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-yellow-500" />;
    }
  };

  const getStatusBadgeVariant = (status) => {
    switch (status) {
      case 'COMPLETED':
        return 'default';
      case 'FAILED':
        return 'destructive';
      default:
        return 'secondary';
    }
  };

  const filteredDocuments = documents.filter(doc => 
    !searchQuery || 
    doc.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    doc.user_email?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <UnifiedAdminLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">ClearForm Documents</h1>
            <p className="text-gray-500">View and manage generated documents</p>
          </div>
          <Button onClick={loadData} disabled={loading} variant="outline">
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>

        {/* Stats */}
        <div className="grid md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-500">Total Documents</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-500">Completed</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{stats.completed}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-500">Failed</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">{stats.failed}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-500">Pending</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-600">{stats.pending}</div>
            </CardContent>
          </Card>
        </div>

        {/* Search */}
        <Card>
          <CardContent className="py-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                placeholder="Search documents by title or user email..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
          </CardContent>
        </Card>

        {/* Documents List */}
        <Card>
          <CardHeader>
            <CardTitle>Documents</CardTitle>
            <CardDescription>
              {filteredDocuments.length} document{filteredDocuments.length !== 1 ? 's' : ''} found
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
              </div>
            ) : filteredDocuments.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <FileText className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p>No documents found</p>
                <p className="text-sm mt-2">Documents will appear here when users generate them</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-3 px-4 font-medium text-gray-500">Document</th>
                      <th className="text-left py-3 px-4 font-medium text-gray-500">Type</th>
                      <th className="text-left py-3 px-4 font-medium text-gray-500">User</th>
                      <th className="text-left py-3 px-4 font-medium text-gray-500">Status</th>
                      <th className="text-left py-3 px-4 font-medium text-gray-500">Credits</th>
                      <th className="text-left py-3 px-4 font-medium text-gray-500">Created</th>
                      <th className="text-left py-3 px-4 font-medium text-gray-500">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredDocuments.map((doc) => (
                      <tr key={doc.document_id} className="border-b hover:bg-gray-50">
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            {getStatusIcon(doc.status)}
                            <span className="font-medium">{doc.title}</span>
                          </div>
                        </td>
                        <td className="py-3 px-4 capitalize">
                          {doc.document_type?.replace(/_/g, ' ') || 'N/A'}
                        </td>
                        <td className="py-3 px-4 text-sm text-gray-500">
                          {doc.user_email || 'N/A'}
                        </td>
                        <td className="py-3 px-4">
                          <Badge variant={getStatusBadgeVariant(doc.status)}>
                            {doc.status}
                          </Badge>
                        </td>
                        <td className="py-3 px-4">{doc.credits_used || 1}</td>
                        <td className="py-3 px-4 text-sm text-gray-500">
                          {doc.created_at ? new Date(doc.created_at).toLocaleString() : 'N/A'}
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex gap-2">
                            <Button variant="ghost" size="sm" title="View">
                              <Eye className="w-4 h-4" />
                            </Button>
                            {doc.status === 'COMPLETED' && (
                              <Button variant="ghost" size="sm" title="Download">
                                <Download className="w-4 h-4" />
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminClearFormDocumentsPage;
