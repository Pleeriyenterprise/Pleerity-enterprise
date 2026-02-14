/**
 * ClearForm Document Vault Page
 * 
 * Full document listing with filtering and search.
 */

import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  FileText, 
  Search,
  Filter,
  Download,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  ChevronLeft,
  ChevronRight,
  ArrowLeft
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { useClearFormAuth } from '../contexts/ClearFormAuthContext';
import { documentsApi } from '../api/clearformApi';

const ClearFormVaultPage = () => {
  const navigate = useNavigate();
  const { user } = useClearFormAuth();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 20,
    total: 0,
    hasMore: false
  });

  useEffect(() => {
    let cancelled = false;
    const loadDocuments = async () => {
      setLoading(true);
      try {
        const page = pagination.page;
        const pageSize = pagination.pageSize;
        const data = await documentsApi.getVault(page, pageSize);
        if (cancelled) return;
        setDocuments(data.items || []);
        setPagination(prev => ({
          ...prev,
          total: data.total || 0,
          hasMore: data.has_more || false
        }));
      } catch (error) {
        if (!cancelled) console.error('Failed to load documents:', error);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadDocuments();
    return () => { cancelled = true; };
  }, [pagination.page, pagination.pageSize, statusFilter, typeFilter]);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle className="w-4 h-4 text-emerald-500" />;
      case 'FAILED':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'GENERATING':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      default:
        return <Clock className="w-4 h-4 text-yellow-500" />;
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      COMPLETED: 'bg-emerald-100 text-emerald-700',
      FAILED: 'bg-red-100 text-red-700',
      GENERATING: 'bg-blue-100 text-blue-700',
      PENDING: 'bg-yellow-100 text-yellow-700'
    };
    return styles[status] || 'bg-gray-100 text-gray-700';
  };

  const filteredDocuments = documents.filter(doc => {
    if (searchQuery && !doc.title.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (statusFilter !== 'all' && doc.status !== statusFilter) {
      return false;
    }
    if (typeFilter !== 'all' && doc.document_type !== typeFilter) {
      return false;
    }
    return true;
  });

  const uniqueTypes = [...new Set(documents.map(d => d.document_type))];

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/clearform/dashboard" className="flex items-center gap-3">
            <img 
              src="/pleerity-logo.jpg" 
              alt="Pleerity" 
              className="h-8 w-auto"
            />
            <div className="flex flex-col">
              <span className="text-lg font-bold text-slate-900">ClearForm</span>
              <span className="text-xs text-slate-500">by Pleerity</span>
            </div>
          </Link>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm font-medium text-slate-900">{user?.full_name}</p>
              <p className="text-xs text-slate-500">{user?.credit_balance || 0} credits</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        {/* Back Link */}
        <Button 
          variant="ghost" 
          className="mb-6"
          onClick={() => navigate('/clearform/dashboard')}
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Dashboard
        </Button>

        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Document Vault</h1>
            <p className="text-slate-500">
              {pagination.total} document{pagination.total !== 1 ? 's' : ''} in your vault
            </p>
          </div>
          <Button onClick={() => navigate('/clearform/create')} data-testid="create-doc-btn">
            <FileText className="w-4 h-4 mr-2" />
            New Document
          </Button>
        </div>

        {/* Filters */}
        <Card className="mb-6">
          <CardContent className="py-4">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <Input
                    placeholder="Search documents..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                    data-testid="search-input"
                  />
                </div>
              </div>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[150px]" data-testid="status-filter">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="COMPLETED">Completed</SelectItem>
                  <SelectItem value="PENDING">Pending</SelectItem>
                  <SelectItem value="GENERATING">Generating</SelectItem>
                  <SelectItem value="FAILED">Failed</SelectItem>
                </SelectContent>
              </Select>
              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-[180px]" data-testid="type-filter">
                  <SelectValue placeholder="Document Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  {uniqueTypes.map(type => (
                    <SelectItem key={type} value={type}>
                      {type.replace(/_/g, ' ')}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Document List */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
          </div>
        ) : filteredDocuments.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-500 mb-4">
                {searchQuery || statusFilter !== 'all' || typeFilter !== 'all'
                  ? 'No documents match your filters'
                  : 'No documents yet'}
              </p>
              {!searchQuery && statusFilter === 'all' && typeFilter === 'all' && (
                <Button onClick={() => navigate('/clearform/create')}>
                  Create Your First Document
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="p-0">
              <div className="divide-y">
                {filteredDocuments.map((doc) => (
                  <div 
                    key={doc.document_id} 
                    className="flex items-center justify-between p-4 hover:bg-slate-50 cursor-pointer transition-colors"
                    onClick={() => navigate(`/clearform/document/${doc.document_id}`)}
                    data-testid={`vault-doc-${doc.document_id}`}
                  >
                    <div className="flex items-center gap-4">
                      {getStatusIcon(doc.status)}
                      <div>
                        <p className="font-medium text-slate-900">{doc.title}</p>
                        <div className="flex items-center gap-2 text-sm text-slate-500">
                          <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                          <span>•</span>
                          <span className="capitalize">{doc.document_type.replace(/_/g, ' ')}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`text-xs px-2 py-1 rounded-full capitalize ${getStatusBadge(doc.status)}`}>
                        {doc.status.toLowerCase()}
                      </span>
                      <span className="text-sm text-slate-400">
                        {doc.credits_used} credit{doc.credits_used !== 1 ? 's' : ''}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Pagination */}
        {pagination.total > pagination.pageSize && (
          <div className="flex items-center justify-between mt-6">
            <p className="text-sm text-slate-500">
              Showing {((pagination.page - 1) * pagination.pageSize) + 1} to{' '}
              {Math.min(pagination.page * pagination.pageSize, pagination.total)} of {pagination.total}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={pagination.page === 1}
                onClick={() => setPagination(p => ({ ...p, page: p.page - 1 }))}
              >
                <ChevronLeft className="w-4 h-4" />
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={!pagination.hasMore}
                onClick={() => setPagination(p => ({ ...p, page: p.page + 1 }))}
              >
                Next
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default ClearFormVaultPage;
