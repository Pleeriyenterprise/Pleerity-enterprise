import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';
import { toast } from 'sonner';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Truck,
  Package,
  Printer,
  CheckCircle2,
  Clock,
  AlertTriangle,
  RefreshCw,
  Search,
  Filter,
  MapPin,
  User,
  Calendar,
  ExternalLink,
  Edit,
  Eye,
  Send,
  XCircle,
} from 'lucide-react';
import { cn } from '../lib/utils';

const POSTAL_STATUSES = {
  PENDING_PRINT: { label: 'Pending Print', color: 'bg-amber-100 text-amber-800', icon: Printer },
  PRINTED: { label: 'Printed', color: 'bg-blue-100 text-blue-800', icon: CheckCircle2 },
  DISPATCHED: { label: 'Dispatched', color: 'bg-purple-100 text-purple-800', icon: Send },
  IN_TRANSIT: { label: 'In Transit', color: 'bg-cyan-100 text-cyan-800', icon: Truck },
  OUT_FOR_DELIVERY: { label: 'Out for Delivery', color: 'bg-indigo-100 text-indigo-800', icon: MapPin },
  DELIVERED: { label: 'Delivered', color: 'bg-green-100 text-green-800', icon: CheckCircle2 },
  FAILED: { label: 'Failed Delivery', color: 'bg-red-100 text-red-800', icon: AlertTriangle },
  RETURNED: { label: 'Returned', color: 'bg-orange-100 text-orange-800', icon: XCircle },
  CANCELLED: { label: 'Cancelled', color: 'bg-gray-100 text-gray-800', icon: XCircle },
};

const CARRIERS = [
  { value: 'ROYAL_MAIL', label: 'Royal Mail' },
  { value: 'DPD', label: 'DPD' },
  { value: 'HERMES', label: 'Evri (Hermes)' },
  { value: 'UPS', label: 'UPS' },
  { value: 'FEDEX', label: 'FedEx' },
  { value: 'DHL', label: 'DHL' },
  { value: 'OTHER', label: 'Other' },
];

/**
 * AdminPostalTrackingPage - Dedicated UI for managing printed copy deliveries
 */
const AdminPostalTrackingPage = () => {
  const { user } = useAuth();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [updateModalOpen, setUpdateModalOpen] = useState(false);
  const [addressModalOpen, setAddressModalOpen] = useState(false);
  const [stats, setStats] = useState({ pending_print: 0, printed: 0, in_transit: 0, delivered: 0 });

  // Form states
  const [updateForm, setUpdateForm] = useState({
    status: '',
    tracking_number: '',
    carrier: '',
    notes: '',
  });
  const [addressForm, setAddressForm] = useState({
    recipient_name: '',
    delivery_address: '',
    carrier: 'ROYAL_MAIL',
    tracking_number: '',
  });
  const [submitting, setSubmitting] = useState(false);

  const fetchOrders = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get('/admin/orders/postal/pending');
      const data = response.data;
      
      // Flatten orders object into array
      const ordersObj = data.orders || {};
      const allOrders = [];
      Object.entries(ordersObj).forEach(([status, statusOrders]) => {
        if (Array.isArray(statusOrders)) {
          statusOrders.forEach(order => {
            allOrders.push({ ...order, postal_status: status });
          });
        }
      });
      
      setOrders(allOrders);
      setStats({
        pending_print: data.pending_print || 0,
        printed: data.printed || 0,
        in_transit: data.in_transit || 0,
        delivered: data.delivered || 0,
        total: data.total || 0,
      });
    } catch (error) {
      toast.error('Failed to load postal orders');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const handleUpdateStatus = async () => {
    if (!selectedOrder || !updateForm.status) {
      toast.error('Please select a status');
      return;
    }

    setSubmitting(true);
    try {
      await api.post(`/admin/orders/${selectedOrder.order_id}/postal/status`, {
        status: updateForm.status,
        tracking_number: updateForm.tracking_number || undefined,
        carrier: updateForm.carrier || undefined,
        notes: updateForm.notes || undefined,
      });
      
      toast.success('Postal status updated');
      setUpdateModalOpen(false);
      setSelectedOrder(null);
      setUpdateForm({ status: '', tracking_number: '', carrier: '', notes: '' });
      fetchOrders();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update status');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSetAddress = async () => {
    if (!selectedOrder || !addressForm.delivery_address || !addressForm.recipient_name) {
      toast.error('Please fill in recipient name and address');
      return;
    }

    setSubmitting(true);
    try {
      await api.post(`/admin/orders/${selectedOrder.order_id}/postal/address`, addressForm);
      
      toast.success('Delivery address updated');
      setAddressModalOpen(false);
      setSelectedOrder(null);
      setAddressForm({ recipient_name: '', delivery_address: '', carrier: 'ROYAL_MAIL', tracking_number: '' });
      fetchOrders();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update address');
    } finally {
      setSubmitting(false);
    }
  };

  const openUpdateModal = (order) => {
    setSelectedOrder(order);
    setUpdateForm({
      status: order.postal_status || 'PENDING_PRINT',
      tracking_number: order.tracking_number || '',
      carrier: order.carrier || '',
      notes: '',
    });
    setUpdateModalOpen(true);
  };

  const openAddressModal = (order) => {
    setSelectedOrder(order);
    setAddressForm({
      recipient_name: order.recipient_name || order.client_name || '',
      delivery_address: order.delivery_address || '',
      carrier: order.carrier || 'ROYAL_MAIL',
      tracking_number: order.tracking_number || '',
    });
    setAddressModalOpen(true);
  };

  const filteredOrders = orders.filter(order => {
    const matchesSearch = 
      order.order_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      order.client_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      order.client_email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      order.tracking_number?.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || order.postal_status === statusFilter;
    
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status) => {
    const config = POSTAL_STATUSES[status] || POSTAL_STATUSES.PENDING_PRINT;
    const Icon = config.icon;
    return (
      <Badge className={cn("flex items-center gap-1", config.color)}>
        <Icon className="w-3 h-3" />
        {config.label}
      </Badge>
    );
  };

  return (
    <UnifiedAdminLayout>
      <div className="space-y-6" data-testid="postal-tracking-page">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-midnight-blue flex items-center gap-2">
              <Truck className="w-7 h-7 text-electric-teal" />
              Postal Tracking
            </h1>
            <p className="text-gray-500 mt-1">Manage printed copy deliveries and tracking</p>
          </div>
          <Button onClick={fetchOrders} variant="outline" className="gap-2">
            <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
            Refresh
          </Button>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-100 rounded-lg">
                <Printer className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-midnight-blue">{stats.pending_print}</p>
                <p className="text-xs text-gray-500">Pending Print</p>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Package className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-midnight-blue">{stats.printed}</p>
                <p className="text-xs text-gray-500">Printed</p>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-cyan-100 rounded-lg">
                <Truck className="w-5 h-5 text-cyan-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-midnight-blue">{stats.in_transit}</p>
                <p className="text-xs text-gray-500">In Transit</p>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <CheckCircle2 className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-midnight-blue">{stats.delivered}</p>
                <p className="text-xs text-gray-500">Delivered</p>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gray-100 rounded-lg">
                <Clock className="w-5 h-5 text-gray-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-midnight-blue">{stats.total}</p>
                <p className="text-xs text-gray-500">Total Active</p>
              </div>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                placeholder="Search by order ID, client, or tracking number..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full sm:w-48">
                <Filter className="w-4 h-4 mr-2" />
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                {Object.entries(POSTAL_STATUSES).map(([key, config]) => (
                  <SelectItem key={key} value={key}>{config.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Orders Table */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
            </div>
          ) : filteredOrders.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-gray-500">
              <Truck className="w-12 h-12 mb-4 text-gray-300" />
              <p className="font-medium">No postal orders found</p>
              <p className="text-sm">Orders requiring printed copies will appear here</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Order</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Client</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Service</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Tracking</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Address</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredOrders.map((order) => (
                    <tr key={order.order_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div>
                          <span className="font-mono text-sm font-medium text-midnight-blue">
                            {order.order_id}
                          </span>
                          <p className="text-xs text-gray-500 flex items-center gap-1 mt-1">
                            <Calendar className="w-3 h-3" />
                            {new Date(order.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div>
                          <p className="font-medium text-sm">{order.client_name || 'N/A'}</p>
                          <p className="text-xs text-gray-500">{order.client_email}</p>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm">{order.service_name || order.service_code}</span>
                      </td>
                      <td className="px-4 py-3">
                        {getStatusBadge(order.postal_status)}
                      </td>
                      <td className="px-4 py-3">
                        {order.tracking_number ? (
                          <div>
                            <span className="font-mono text-sm">{order.tracking_number}</span>
                            {order.carrier && (
                              <p className="text-xs text-gray-500">{CARRIERS.find(c => c.value === order.carrier)?.label || order.carrier}</p>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-400 text-sm">Not set</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {order.delivery_address ? (
                          <div className="max-w-[200px]">
                            <p className="text-sm truncate" title={order.delivery_address}>
                              {order.recipient_name || 'N/A'}
                            </p>
                            <p className="text-xs text-gray-500 truncate" title={order.delivery_address}>
                              {order.delivery_address}
                            </p>
                          </div>
                        ) : (
                          <Badge variant="outline" className="text-amber-600 border-amber-300">
                            <AlertTriangle className="w-3 h-3 mr-1" />
                            Missing
                          </Badge>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openUpdateModal(order)}
                            title="Update Status"
                          >
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openAddressModal(order)}
                            title="Edit Address"
                          >
                            <MapPin className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => window.open(`/admin/orders?order=${order.order_id}`, '_blank')}
                            title="View Order"
                          >
                            <ExternalLink className="w-4 h-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Update Status Modal */}
        <Dialog open={updateModalOpen} onOpenChange={setUpdateModalOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Update Postal Status</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <Label>Order ID</Label>
                <p className="font-mono text-sm mt-1">{selectedOrder?.order_id}</p>
              </div>
              <div>
                <Label>Status</Label>
                <Select value={updateForm.status} onValueChange={(v) => setUpdateForm(f => ({ ...f, status: v }))}>
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Select status" />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(POSTAL_STATUSES).map(([key, config]) => (
                      <SelectItem key={key} value={key}>{config.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Carrier</Label>
                <Select value={updateForm.carrier} onValueChange={(v) => setUpdateForm(f => ({ ...f, carrier: v }))}>
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Select carrier" />
                  </SelectTrigger>
                  <SelectContent>
                    {CARRIERS.map((carrier) => (
                      <SelectItem key={carrier.value} value={carrier.value}>{carrier.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Tracking Number</Label>
                <Input
                  value={updateForm.tracking_number}
                  onChange={(e) => setUpdateForm(f => ({ ...f, tracking_number: e.target.value }))}
                  placeholder="Enter tracking number"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>Notes (optional)</Label>
                <Input
                  value={updateForm.notes}
                  onChange={(e) => setUpdateForm(f => ({ ...f, notes: e.target.value }))}
                  placeholder="Add any notes..."
                  className="mt-1"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setUpdateModalOpen(false)}>Cancel</Button>
              <Button onClick={handleUpdateStatus} disabled={submitting}>
                {submitting && <RefreshCw className="w-4 h-4 mr-2 animate-spin" />}
                Update Status
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Address Modal */}
        <Dialog open={addressModalOpen} onOpenChange={setAddressModalOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Set Delivery Address</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <Label>Recipient Name</Label>
                <Input
                  value={addressForm.recipient_name}
                  onChange={(e) => setAddressForm(f => ({ ...f, recipient_name: e.target.value }))}
                  placeholder="Full name"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>Delivery Address</Label>
                <textarea
                  value={addressForm.delivery_address}
                  onChange={(e) => setAddressForm(f => ({ ...f, delivery_address: e.target.value }))}
                  placeholder="Full postal address including postcode"
                  className="mt-1 w-full px-3 py-2 border border-gray-200 rounded-lg text-sm min-h-[100px]"
                />
              </div>
              <div>
                <Label>Carrier</Label>
                <Select value={addressForm.carrier} onValueChange={(v) => setAddressForm(f => ({ ...f, carrier: v }))}>
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Select carrier" />
                  </SelectTrigger>
                  <SelectContent>
                    {CARRIERS.map((carrier) => (
                      <SelectItem key={carrier.value} value={carrier.value}>{carrier.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Tracking Number (optional)</Label>
                <Input
                  value={addressForm.tracking_number}
                  onChange={(e) => setAddressForm(f => ({ ...f, tracking_number: e.target.value }))}
                  placeholder="Enter if already dispatched"
                  className="mt-1"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setAddressModalOpen(false)}>Cancel</Button>
              <Button onClick={handleSetAddress} disabled={submitting}>
                {submitting && <RefreshCw className="w-4 h-4 mr-2 animate-spin" />}
                Save Address
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminPostalTrackingPage;
