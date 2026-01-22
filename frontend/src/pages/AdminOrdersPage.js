import React, { useState, useEffect, useCallback } from 'react';
import AdminLayout from '../components/admin/AdminLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';
import {
  Search,
  RefreshCw,
  ChevronRight,
  Clock,
  User,
  Package,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileText,
  RotateCcw,
  MessageSquare,
} from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Status color mapping
const statusColors = {
  CREATED: 'bg-gray-100 text-gray-800',
  PAID: 'bg-blue-100 text-blue-800',
  QUEUED: 'bg-gray-100 text-gray-800',
  IN_PROGRESS: 'bg-yellow-100 text-yellow-800',
  DRAFT_READY: 'bg-purple-100 text-purple-800',
  INTERNAL_REVIEW: 'bg-orange-100 text-orange-800',
  REGEN_REQUESTED: 'bg-pink-100 text-pink-800',
  REGENERATING: 'bg-pink-100 text-pink-800',
  CLIENT_INPUT_REQUIRED: 'bg-pink-100 text-pink-800',
  FINALISING: 'bg-teal-100 text-teal-800',
  DELIVERING: 'bg-cyan-100 text-cyan-800',
  COMPLETED: 'bg-green-100 text-green-800',
  DELIVERY_FAILED: 'bg-red-100 text-red-800',
  FAILED: 'bg-red-100 text-red-800',
  CANCELLED: 'bg-gray-100 text-gray-500',
};

// Pipeline columns configuration
const pipelineColumns = [
  { status: 'PAID', label: 'Paid', color: 'border-blue-400' },
  { status: 'IN_PROGRESS', label: 'In Progress', color: 'border-yellow-400' },
  { status: 'DRAFT_READY', label: 'Draft Ready', color: 'border-purple-400' },
  { status: 'INTERNAL_REVIEW', label: 'Review', color: 'border-orange-400' },
  { status: 'CLIENT_INPUT_REQUIRED', label: 'Awaiting Client', color: 'border-pink-400' },
  { status: 'FINALISING', label: 'Finalising', color: 'border-teal-400' },
  { status: 'COMPLETED', label: 'Completed', color: 'border-green-400' },
  { status: 'FAILED', label: 'Failed', color: 'border-red-400' },
];

const AdminOrdersPage = () => {
  const [orders, setOrders] = useState([]);
  const [counts, setCounts] = useState({});
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [orderDetail, setOrderDetail] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Dialog states
  const [showDetailDialog, setShowDetailDialog] = useState(false);
  const [showActionDialog, setShowActionDialog] = useState(false);
  const [actionType, setActionType] = useState(null);
  const [actionNote, setActionNote] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchOrders = useCallback(async () => {
    setIsLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/admin/orders/pipeline`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (response.ok) {
        const data = await response.json();
        setOrders(data.orders || []);
        setCounts(data.counts || {});
      }
    } catch (error) {
      console.error('Failed to fetch orders:', error);
      toast.error('Failed to load orders');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const fetchOrderDetail = async (orderId) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/admin/orders/${orderId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (response.ok) {
        const data = await response.json();
        setOrderDetail(data);
        setShowDetailDialog(true);
      }
    } catch (error) {
      console.error('Failed to fetch order detail:', error);
      toast.error('Failed to load order details');
    }
  };

  const handleOrderClick = (order) => {
    setSelectedOrder(order);
    fetchOrderDetail(order.order_id);
  };

  const handleAction = (type) => {
    setActionType(type);
    setActionNote('');
    setShowActionDialog(true);
  };

  const submitAction = async () => {
    if (!selectedOrder || !actionType) return;
    
    setIsSubmitting(true);
    try {
      const token = localStorage.getItem('token');
      
      let endpoint = '';
      let body = {};
      
      switch (actionType) {
        case 'approve':
          endpoint = `/api/admin/orders/${selectedOrder.order_id}/approve`;
          break;
        case 'regen':
          endpoint = `/api/admin/orders/${selectedOrder.order_id}/request-regen`;
          body = { note: actionNote };
          break;
        case 'request_info':
          endpoint = `/api/admin/orders/${selectedOrder.order_id}/request-info`;
          body = { note: actionNote };
          break;
        default:
          return;
      }
      
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });
      
      if (response.ok) {
        toast.success('Action completed successfully');
        setShowActionDialog(false);
        setShowDetailDialog(false);
        fetchOrders();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Action failed');
      }
    } catch (error) {
      console.error('Action failed:', error);
      toast.error('Action failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const getOrdersForColumn = (status) => {
    return orders.filter((o) => o.status === status);
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getTimeInState = (order) => {
    const updated = new Date(order.updated_at);
    const now = new Date();
    const hours = Math.floor((now - updated) / (1000 * 60 * 60));
    if (hours < 1) return 'Just now';
    if (hours < 24) return `${hours}h`;
    return `${Math.floor(hours / 24)}d`;
  };

  return (
    <AdminLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-midnight-blue">Orders Pipeline</h1>
            <p className="text-gray-500">Manage and track order workflow</p>
          </div>
          <div className="flex items-center space-x-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                placeholder="Search orders..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 w-64"
                data-testid="orders-search"
              />
            </div>
            <Button variant="outline" onClick={fetchOrders} data-testid="refresh-orders">
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Pipeline View */}
        <div className="overflow-x-auto pb-4">
          <div className="flex space-x-4 min-w-max">
            {pipelineColumns.map((column) => (
              <div
                key={column.status}
                className={`w-72 flex-shrink-0 bg-gray-50 rounded-lg border-t-4 ${column.color}`}
                data-testid={`pipeline-column-${column.status.toLowerCase()}`}
              >
                <div className="p-4 border-b border-gray-200">
                  <div className="flex justify-between items-center">
                    <h3 className="font-semibold text-midnight-blue">{column.label}</h3>
                    <Badge variant="secondary">{counts[column.status] || 0}</Badge>
                  </div>
                </div>
                <div className="p-2 space-y-2 min-h-[400px] max-h-[600px] overflow-y-auto">
                  {isLoading ? (
                    <div className="animate-pulse space-y-2">
                      {[1, 2].map((i) => (
                        <div key={i} className="h-24 bg-gray-200 rounded-lg" />
                      ))}
                    </div>
                  ) : (
                    getOrdersForColumn(column.status).map((order) => (
                      <Card
                        key={order.order_id}
                        className="cursor-pointer hover:shadow-md transition-shadow"
                        onClick={() => handleOrderClick(order)}
                        data-testid={`order-card-${order.order_id}`}
                      >
                        <CardContent className="p-3">
                          <div className="flex justify-between items-start mb-2">
                            <span className="text-xs font-mono text-gray-500">
                              {order.order_id}
                            </span>
                            <span className="text-xs text-gray-400">
                              {getTimeInState(order)}
                            </span>
                          </div>
                          <p className="font-medium text-sm text-midnight-blue mb-1 truncate">
                            {order.service_name}
                          </p>
                          <p className="text-xs text-gray-500 truncate">
                            {order.customer?.full_name}
                          </p>
                          {order.sla_hours && (
                            <div className="flex items-center mt-2 text-xs text-gray-400">
                              <Clock className="w-3 h-3 mr-1" />
                              SLA: {order.sla_hours}h
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    ))
                  )}
                  {!isLoading && getOrdersForColumn(column.status).length === 0 && (
                    <div className="text-center py-8 text-gray-400 text-sm">
                      No orders
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Order Detail Dialog */}
        <Dialog open={showDetailDialog} onOpenChange={setShowDetailDialog}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            {orderDetail && (
              <>
                <DialogHeader>
                  <DialogTitle className="flex items-center justify-between">
                    <span>Order {orderDetail.order?.order_id}</span>
                    <Badge className={statusColors[orderDetail.order?.status]}>
                      {orderDetail.order?.status}
                    </Badge>
                  </DialogTitle>
                  <DialogDescription>
                    {orderDetail.order?.service_name}
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-6 py-4">
                  {/* Customer Info */}
                  <div className="grid grid-cols-2 gap-4">
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm flex items-center">
                          <User className="w-4 h-4 mr-2" />
                          Customer
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="text-sm">
                        <p className="font-medium">{orderDetail.order?.customer?.full_name}</p>
                        <p className="text-gray-500">{orderDetail.order?.customer?.email}</p>
                        {orderDetail.order?.customer?.phone && (
                          <p className="text-gray-500">{orderDetail.order?.customer?.phone}</p>
                        )}
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm flex items-center">
                          <Package className="w-4 h-4 mr-2" />
                          Service
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="text-sm">
                        <p className="font-medium">{orderDetail.order?.service_name}</p>
                        <p className="text-gray-500">Category: {orderDetail.order?.service_category}</p>
                        <p className="text-gray-500">
                          Total: £{((orderDetail.order?.pricing?.total_amount || 0) / 100).toFixed(2)}
                        </p>
                      </CardContent>
                    </Card>
                  </div>

                  {/* Admin Actions (only for INTERNAL_REVIEW) */}
                  {orderDetail.order?.status === 'INTERNAL_REVIEW' && (
                    <Card className="border-orange-200 bg-orange-50">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-orange-800">
                          Review Actions
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="flex space-x-3">
                          <Button
                            onClick={() => handleAction('approve')}
                            className="bg-green-600 hover:bg-green-700"
                            data-testid="action-approve"
                          >
                            <CheckCircle2 className="w-4 h-4 mr-2" />
                            Approve & Finalize
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => handleAction('regen')}
                            data-testid="action-regen"
                          >
                            <RotateCcw className="w-4 h-4 mr-2" />
                            Request Regeneration
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => handleAction('request_info')}
                            data-testid="action-request-info"
                          >
                            <MessageSquare className="w-4 h-4 mr-2" />
                            Request More Info
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Timeline */}
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center">
                        <FileText className="w-4 h-4 mr-2" />
                        Workflow Timeline
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-4">
                        {orderDetail.timeline?.map((entry, index) => (
                          <div key={entry.execution_id} className="flex">
                            <div className="flex flex-col items-center mr-4">
                              <div className={`w-3 h-3 rounded-full ${
                                index === orderDetail.timeline.length - 1
                                  ? 'bg-electric-teal'
                                  : 'bg-gray-300'
                              }`} />
                              {index < orderDetail.timeline.length - 1 && (
                                <div className="w-0.5 h-full bg-gray-200 mt-1" />
                              )}
                            </div>
                            <div className="flex-1 pb-4">
                              <div className="flex justify-between items-start">
                                <div>
                                  <span className="font-medium text-sm">
                                    {entry.previous_state || 'Created'} → {entry.new_state}
                                  </span>
                                  <span className="ml-2 text-xs text-gray-400">
                                    ({entry.transition_type})
                                  </span>
                                </div>
                                <span className="text-xs text-gray-400">
                                  {formatDate(entry.created_at)}
                                </span>
                              </div>
                              {entry.triggered_by?.user_email && (
                                <p className="text-xs text-gray-500 mt-1">
                                  By: {entry.triggered_by.user_email}
                                </p>
                              )}
                              {entry.reason && (
                                <p className="text-xs text-gray-600 mt-1 bg-gray-50 p-2 rounded">
                                  {entry.reason}
                                </p>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Internal Notes */}
                  {orderDetail.order?.internal_notes && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Internal Notes</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <pre className="text-xs text-gray-600 whitespace-pre-wrap bg-gray-50 p-3 rounded">
                          {orderDetail.order.internal_notes}
                        </pre>
                      </CardContent>
                    </Card>
                  )}
                </div>
              </>
            )}
          </DialogContent>
        </Dialog>

        {/* Action Dialog */}
        <Dialog open={showActionDialog} onOpenChange={setShowActionDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {actionType === 'approve' && 'Approve Order'}
                {actionType === 'regen' && 'Request Regeneration'}
                {actionType === 'request_info' && 'Request More Information'}
              </DialogTitle>
              <DialogDescription>
                {actionType === 'approve' && 'This will finalize the order and trigger automatic delivery.'}
                {actionType === 'regen' && 'Provide instructions for regeneration. The system will automatically regenerate and return to review.'}
                {actionType === 'request_info' && 'Describe what information you need from the client. SLA timer will pause.'}
              </DialogDescription>
            </DialogHeader>
            
            {actionType !== 'approve' && (
              <Textarea
                placeholder={
                  actionType === 'regen'
                    ? 'Enter regeneration instructions...'
                    : 'What information do you need from the client?'
                }
                value={actionNote}
                onChange={(e) => setActionNote(e.target.value)}
                rows={4}
                data-testid="action-note-input"
              />
            )}
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowActionDialog(false)}>
                Cancel
              </Button>
              <Button
                onClick={submitAction}
                disabled={isSubmitting || (actionType !== 'approve' && !actionNote.trim())}
                className={actionType === 'approve' ? 'bg-green-600 hover:bg-green-700' : ''}
                data-testid="action-submit"
              >
                {isSubmitting ? 'Processing...' : 'Confirm'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </AdminLayout>
  );
};

export default AdminOrdersPage;
