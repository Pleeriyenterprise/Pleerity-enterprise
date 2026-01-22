/**
 * Client Orders Page - View and download documents for completed orders.
 * Provides a document library view for clients to access their deliverables.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, Download, Clock, CheckCircle2, AlertCircle,
  Package, Eye, RefreshCw, Search, Filter, Calendar
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from '../components/ui/select';
import { toast } from 'sonner';
import client from '../api/client';

const STATUS_CONFIG = {
  CREATED: { label: 'Created', color: 'bg-gray-100 text-gray-700', icon: Clock },
  PAID: { label: 'Paid', color: 'bg-blue-100 text-blue-700', icon: CheckCircle2 },
  QUEUED: { label: 'In Queue', color: 'bg-yellow-100 text-yellow-700', icon: Clock },
  IN_PROGRESS: { label: 'In Progress', color: 'bg-blue-100 text-blue-700', icon: RefreshCw },
  DRAFT_READY: { label: 'Draft Ready', color: 'bg-purple-100 text-purple-700', icon: FileText },
  INTERNAL_REVIEW: { label: 'Under Review', color: 'bg-orange-100 text-orange-700', icon: Eye },
  CLIENT_INPUT_REQUIRED: { label: 'Action Required', color: 'bg-red-100 text-red-700', icon: AlertCircle },
  FINALISING: { label: 'Finalising', color: 'bg-teal-100 text-teal-700', icon: Package },
  COMPLETED: { label: 'Completed', color: 'bg-green-100 text-green-700', icon: CheckCircle2 },
  CANCELLED: { label: 'Cancelled', color: 'bg-gray-100 text-gray-500', icon: AlertCircle },
};

function StatusBadge({ status }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.CREATED;
  const Icon = config.icon;
  
  return (
    <Badge className={`${config.color} flex items-center gap-1`}>
      <Icon className="h-3 w-3" />
      {config.label}
    </Badge>
  );
}

function OrderCard({ order, onViewDocuments }) {
  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  const isCompleted = order.status === 'COMPLETED';
  const requiresAction = order.status === 'CLIENT_INPUT_REQUIRED';

  return (
    <Card 
      className={`hover:shadow-md transition-shadow ${requiresAction ? 'border-red-300 bg-red-50/30' : ''}`}
      data-testid={`order-card-${order.order_id}`}
    >
      <CardContent className="p-4">
        <div className="flex justify-between items-start mb-3">
          <div>
            <h3 className="font-medium text-gray-900">{order.service_name}</h3>
            <p className="text-sm text-gray-500">{order.order_id}</p>
          </div>
          <StatusBadge status={order.status} />
        </div>
        
        <div className="grid grid-cols-2 gap-2 text-sm mb-4">
          <div>
            <span className="text-gray-500">Ordered:</span>
            <span className="ml-1 text-gray-700">{formatDate(order.created_at)}</span>
          </div>
          {order.completed_at && (
            <div>
              <span className="text-gray-500">Completed:</span>
              <span className="ml-1 text-gray-700">{formatDate(order.completed_at)}</span>
            </div>
          )}
          {order.pricing && (
            <div>
              <span className="text-gray-500">Total:</span>
              <span className="ml-1 text-gray-700">
                £{((order.pricing.total_pence || 0) / 100).toFixed(2)}
              </span>
            </div>
          )}
        </div>

        <div className="flex gap-2">
          {isCompleted && (
            <Button
              size="sm"
              onClick={() => onViewDocuments(order)}
              className="bg-teal-600 hover:bg-teal-700"
              data-testid={`view-documents-btn-${order.order_id}`}
            >
              <Download className="h-4 w-4 mr-1" />
              View Documents
            </Button>
          )}
          {requiresAction && (
            <Button
              size="sm"
              variant="destructive"
              onClick={() => window.location.href = `/app/orders/${order.order_id}/provide-info`}
              data-testid={`provide-info-btn-${order.order_id}`}
            >
              <AlertCircle className="h-4 w-4 mr-1" />
              Provide Information
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function DocumentsModal({ order, documents, onClose, onDownload }) {
  if (!order) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[80vh] overflow-hidden">
        <div className="p-4 border-b bg-gray-50">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Your Documents</h2>
              <p className="text-sm text-gray-500">{order.service_name}</p>
            </div>
            <Button variant="ghost" size="sm" onClick={onClose}>✕</Button>
          </div>
        </div>
        
        <div className="p-4 overflow-y-auto max-h-[60vh]">
          {documents.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <FileText className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>No documents available yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {documents.map((doc) => (
                <div
                  key={doc.version}
                  className="flex items-center justify-between p-3 border rounded-lg bg-gray-50"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="h-8 w-8 text-teal-600" />
                    <div>
                      <p className="font-medium text-gray-900">
                        Document v{doc.version}
                      </p>
                      <p className="text-sm text-gray-500">
                        {doc.generated_at 
                          ? new Date(doc.generated_at).toLocaleDateString('en-GB')
                          : 'Generated'}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {doc.has_pdf && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onDownload(order.order_id, doc.version, 'pdf')}
                        data-testid={`download-pdf-v${doc.version}`}
                      >
                        PDF
                      </Button>
                    )}
                    {doc.has_docx && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onDownload(order.order_id, doc.version, 'docx')}
                        data-testid={`download-docx-v${doc.version}`}
                      >
                        DOCX
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        
        <div className="p-4 border-t bg-gray-50 flex justify-end">
          <Button variant="outline" onClick={onClose}>Close</Button>
        </div>
      </div>
    </div>
  );
}

export default function ClientOrdersPage() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [stats, setStats] = useState({ total: 0, action_required: 0 });
  const navigate = useNavigate();

  const fetchOrders = useCallback(async () => {
    try {
      setLoading(true);
      const response = await client.get('/api/client/orders/');
      setOrders(response.data.orders || []);
      setStats({
        total: response.data.total || 0,
        action_required: response.data.action_required || 0,
      });
    } catch (error) {
      console.error('Failed to fetch orders:', error);
      toast.error('Failed to load orders');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const handleViewDocuments = async (order) => {
    try {
      const response = await client.get(`/api/client/orders/${order.order_id}/documents`);
      setDocuments(response.data.documents || []);
      setSelectedOrder(order);
    } catch (error) {
      console.error('Failed to fetch documents:', error);
      toast.error('Failed to load documents');
    }
  };

  const handleDownload = async (orderId, version, format) => {
    try {
      const response = await client.get(
        `/api/client/orders/${orderId}/documents/${version}/download?format=${format}`,
        { responseType: 'blob' }
      );
      
      const blob = new Blob([response.data], {
        type: format === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      });
      
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${orderId}_v${version}.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success('Download started');
    } catch (error) {
      console.error('Download failed:', error);
      toast.error('Download failed. Please try again.');
    }
  };

  const filteredOrders = orders.filter(order => {
    const matchesSearch = 
      order.service_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      order.order_id?.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || order.status === statusFilter;
    
    return matchesSearch && matchesStatus;
  });

  const completedOrders = orders.filter(o => o.status === 'COMPLETED').length;

  return (
    <div className="min-h-screen bg-gray-50 py-8" data-testid="client-orders-page">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">My Orders</h1>
          <p className="text-gray-600 mt-1">
            View your orders and download completed documents
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <Card>
            <CardContent className="p-4 flex items-center gap-4">
              <div className="p-3 rounded-full bg-blue-100">
                <Package className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
                <p className="text-sm text-gray-500">Total Orders</p>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4 flex items-center gap-4">
              <div className="p-3 rounded-full bg-green-100">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{completedOrders}</p>
                <p className="text-sm text-gray-500">Completed</p>
              </div>
            </CardContent>
          </Card>
          
          <Card className={stats.action_required > 0 ? 'border-red-300' : ''}>
            <CardContent className="p-4 flex items-center gap-4">
              <div className={`p-3 rounded-full ${stats.action_required > 0 ? 'bg-red-100' : 'bg-gray-100'}`}>
                <AlertCircle className={`h-5 w-5 ${stats.action_required > 0 ? 'text-red-600' : 'text-gray-400'}`} />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{stats.action_required}</p>
                <p className="text-sm text-gray-500">Action Required</p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search orders..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
              data-testid="search-orders-input"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-full sm:w-48" data-testid="status-filter">
              <Filter className="h-4 w-4 mr-2" />
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="COMPLETED">Completed</SelectItem>
              <SelectItem value="IN_PROGRESS">In Progress</SelectItem>
              <SelectItem value="CLIENT_INPUT_REQUIRED">Action Required</SelectItem>
              <SelectItem value="INTERNAL_REVIEW">Under Review</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            onClick={fetchOrders}
            data-testid="refresh-orders-btn"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>

        {/* Orders List */}
        {loading ? (
          <div className="text-center py-12">
            <RefreshCw className="h-8 w-8 animate-spin mx-auto text-gray-400" />
            <p className="mt-2 text-gray-500">Loading orders...</p>
          </div>
        ) : filteredOrders.length === 0 ? (
          <Card>
            <CardContent className="text-center py-12">
              <Package className="h-12 w-12 mx-auto text-gray-300 mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Orders Found</h3>
              <p className="text-gray-500 mb-4">
                {searchQuery || statusFilter !== 'all'
                  ? 'Try adjusting your filters'
                  : "You haven't placed any orders yet"}
              </p>
              <Button
                onClick={() => navigate('/services/catalogue')}
                className="bg-teal-600 hover:bg-teal-700"
              >
                Browse Services
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredOrders.map((order) => (
              <OrderCard
                key={order.order_id}
                order={order}
                onViewDocuments={handleViewDocuments}
              />
            ))}
          </div>
        )}

        {/* Documents Modal */}
        {selectedOrder && (
          <DocumentsModal
            order={selectedOrder}
            documents={documents}
            onClose={() => setSelectedOrder(null)}
            onDownload={handleDownload}
          />
        )}
      </div>
    </div>
  );
}
