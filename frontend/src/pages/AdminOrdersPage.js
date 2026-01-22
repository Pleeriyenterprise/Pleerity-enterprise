import React, { useState, useEffect, useCallback, useRef } from 'react';
import AdminLayout from '../components/admin/AdminLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Label } from '../components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { Textarea } from '../components/ui/textarea';
import {
  Search,
  RefreshCw,
  Clock,
  User,
  Package,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileText,
  RotateCcw,
  MessageSquare,
  Play,
  Pause,
  Trash2,
  ArrowLeft,
  ArrowRight,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Flag,
  Calendar,
  Timer,
  Zap,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '../lib/utils';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Auto-refresh interval (ms)
const AUTO_REFRESH_INTERVAL = 15000;

// Status color mapping for badges
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

// Pipeline columns configuration with emphasis colors
const pipelineColumns = [
  { status: 'PAID', label: 'Paid', color: 'blue', bgActive: 'bg-blue-50', borderActive: 'border-blue-500', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200' },
  { status: 'QUEUED', label: 'Queued', color: 'slate', bgActive: 'bg-slate-100', borderActive: 'border-slate-500', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200' },
  { status: 'IN_PROGRESS', label: 'In Progress', color: 'yellow', bgActive: 'bg-yellow-50', borderActive: 'border-yellow-500', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200' },
  { status: 'DRAFT_READY', label: 'Draft Ready', color: 'purple', bgActive: 'bg-purple-50', borderActive: 'border-purple-500', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200' },
  { status: 'INTERNAL_REVIEW', label: 'Review', color: 'orange', bgActive: 'bg-orange-50', borderActive: 'border-orange-500', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200' },
  { status: 'CLIENT_INPUT_REQUIRED', label: 'Awaiting Client', color: 'pink', bgActive: 'bg-pink-50', borderActive: 'border-pink-500', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200' },
  { status: 'FINALISING', label: 'Finalising', color: 'teal', bgActive: 'bg-teal-50', borderActive: 'border-teal-500', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200' },
  { status: 'DELIVERING', label: 'Delivering', color: 'cyan', bgActive: 'bg-cyan-50', borderActive: 'border-cyan-500', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200' },
  { status: 'COMPLETED', label: 'Completed', color: 'green', bgActive: 'bg-green-50', borderActive: 'border-green-500', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200' },
  { status: 'DELIVERY_FAILED', label: 'Delivery Failed', color: 'red', bgActive: 'bg-red-50', borderActive: 'border-red-500', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200' },
  { status: 'FAILED', label: 'Failed', color: 'red', bgActive: 'bg-red-100', borderActive: 'border-red-600', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200' },
];

// Sort options
const sortOptions = [
  { value: 'entered_desc', label: 'Entered Stage (Latest First)' },
  { value: 'entered_asc', label: 'Entered Stage (Earliest First)' },
  { value: 'priority', label: 'Priority (Highest First)' },
  { value: 'sla_asc', label: 'SLA Remaining (Urgent First)' },
  { value: 'created_desc', label: 'Created (Newest First)' },
  { value: 'created_asc', label: 'Created (Oldest First)' },
];

// State-specific actions configuration
const stateActions = {
  CREATED: [
    { key: 'cancel', label: 'Cancel Order', icon: XCircle, variant: 'destructive', requiresReason: true },
  ],
  PAID: [
    { key: 'transition_queued', label: 'Move to Queue', icon: ArrowRight, variant: 'default', requiresReason: true },
    { key: 'cancel', label: 'Cancel Order', icon: XCircle, variant: 'destructive', requiresReason: true },
  ],
  QUEUED: [
    { key: 'transition_in_progress', label: 'Start Processing', icon: Play, variant: 'default', requiresReason: true },
    { key: 'cancel', label: 'Cancel Order', icon: XCircle, variant: 'destructive', requiresReason: true },
  ],
  IN_PROGRESS: [
    { key: 'transition_draft_ready', label: 'Mark Draft Ready', icon: CheckCircle2, variant: 'default', requiresReason: true },
    { key: 'transition_failed', label: 'Mark Failed', icon: AlertTriangle, variant: 'destructive', requiresReason: true },
  ],
  DRAFT_READY: [
    { key: 'transition_internal_review', label: 'Send to Review', icon: ArrowRight, variant: 'default', requiresReason: true },
  ],
  INTERNAL_REVIEW: [
    { key: 'approve', label: 'Approve & Finalize', icon: CheckCircle2, variant: 'success', requiresReason: false },
    { key: 'regen', label: 'Request Regeneration', icon: RotateCcw, variant: 'outline', requiresReason: true },
    { key: 'request_info', label: 'Request More Info', icon: MessageSquare, variant: 'outline', requiresReason: true },
    { key: 'cancel', label: 'Cancel Order', icon: XCircle, variant: 'destructive', requiresReason: true },
  ],
  REGEN_REQUESTED: [
    { key: 'transition_regenerating', label: 'Start Regeneration', icon: Play, variant: 'default', requiresReason: true },
  ],
  REGENERATING: [
    { key: 'transition_internal_review', label: 'Return to Review', icon: ArrowRight, variant: 'default', requiresReason: true },
    { key: 'transition_failed', label: 'Mark Failed', icon: AlertTriangle, variant: 'destructive', requiresReason: true },
  ],
  CLIENT_INPUT_REQUIRED: [
    { key: 'resend_request', label: 'Resend Request', icon: RefreshCw, variant: 'outline', requiresReason: true },
    { key: 'transition_internal_review', label: 'Resume (Client Responded)', icon: Play, variant: 'default', requiresReason: true },
  ],
  FINALISING: [
    { key: 'transition_delivering', label: 'Start Delivery', icon: ArrowRight, variant: 'default', requiresReason: true },
    { key: 'transition_failed', label: 'Mark Failed', icon: AlertTriangle, variant: 'destructive', requiresReason: true },
  ],
  DELIVERING: [
    { key: 'transition_completed', label: 'Mark Completed', icon: CheckCircle2, variant: 'success', requiresReason: true },
    { key: 'transition_delivery_failed', label: 'Delivery Failed', icon: AlertTriangle, variant: 'destructive', requiresReason: true },
  ],
  DELIVERY_FAILED: [
    { key: 'retry_delivery', label: 'Retry Delivery', icon: RotateCcw, variant: 'default', requiresReason: true },
    { key: 'transition_failed', label: 'Escalate to Failed', icon: AlertTriangle, variant: 'destructive', requiresReason: true },
  ],
  FAILED: [
    { key: 'retry_queued', label: 'Re-queue Order', icon: RotateCcw, variant: 'default', requiresReason: true },
    { key: 'rollback', label: 'Rollback to Prior Stage', icon: ArrowLeft, variant: 'outline', requiresReason: true },
  ],
  COMPLETED: [],
  CANCELLED: [],
};

const AdminOrdersPage = () => {
  // Data state
  const [orders, setOrders] = useState([]);
  const [counts, setCounts] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  
  // Selection state
  const [selectedStage, setSelectedStage] = useState(null);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [orderDetail, setOrderDetail] = useState(null);
  
  // Sorting
  const [sortBy, setSortBy] = useState('priority');
  
  // Search
  const [searchQuery, setSearchQuery] = useState('');
  
  // Dialog states
  const [showStageDialog, setShowStageDialog] = useState(false);
  const [showDetailDialog, setShowDetailDialog] = useState(false);
  const [showActionDialog, setShowActionDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  
  // Action state
  const [currentAction, setCurrentAction] = useState(null);
  const [actionReason, setActionReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Auto-refresh
  const [autoRefresh, setAutoRefresh] = useState(true);
  const refreshIntervalRef = useRef(null);

  // Fetch orders
  const fetchOrders = useCallback(async (showLoading = true) => {
    if (showLoading) setIsLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_URL}/api/admin/orders/pipeline`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (response.ok) {
        const data = await response.json();
        setOrders(data.orders || []);
        setCounts(data.counts || {});
        setLastUpdated(new Date());
      }
    } catch (error) {
      console.error('Failed to fetch orders:', error);
      if (showLoading) toast.error('Failed to load orders');
    } finally {
      if (showLoading) setIsLoading(false);
    }
  }, []);

  // Initial load and auto-refresh setup
  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  // Auto-refresh effect
  useEffect(() => {
    if (autoRefresh) {
      refreshIntervalRef.current = setInterval(() => {
        fetchOrders(false); // Silent refresh
      }, AUTO_REFRESH_INTERVAL);
    }
    
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [autoRefresh, fetchOrders]);

  // Fetch order detail
  const fetchOrderDetail = async (orderId) => {
    try {
      const token = localStorage.getItem('auth_token');
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

  // Get orders for a specific status
  const getOrdersForStatus = useCallback((status) => {
    let filtered = orders.filter((o) => o.status === status);
    
    // Sort orders
    filtered.sort((a, b) => {
      // Priority orders always first
      if (a.priority && !b.priority) return -1;
      if (!a.priority && b.priority) return 1;
      
      switch (sortBy) {
        case 'entered_desc':
          return new Date(b.updated_at) - new Date(a.updated_at);
        case 'entered_asc':
          return new Date(a.updated_at) - new Date(b.updated_at);
        case 'priority':
          // Already handled above, fall through to entered_desc
          return new Date(b.updated_at) - new Date(a.updated_at);
        case 'sla_asc':
          const slaA = a.sla_hours ? a.sla_hours - getHoursInState(a) : Infinity;
          const slaB = b.sla_hours ? b.sla_hours - getHoursInState(b) : Infinity;
          return slaA - slaB;
        case 'created_desc':
          return new Date(b.created_at) - new Date(a.created_at);
        case 'created_asc':
          return new Date(a.created_at) - new Date(b.created_at);
        default:
          return 0;
      }
    });
    
    return filtered;
  }, [orders, sortBy]);

  // Calculate hours in current state
  const getHoursInState = (order) => {
    const updated = new Date(order.updated_at);
    const now = new Date();
    return (now - updated) / (1000 * 60 * 60);
  };

  // Format time in state
  const formatTimeInState = (order) => {
    const hours = getHoursInState(order);
    if (hours < 1) return 'Just now';
    if (hours < 24) return `${Math.floor(hours)}h`;
    return `${Math.floor(hours / 24)}d ${Math.floor(hours % 24)}h`;
  };

  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Handle stage click
  const handleStageClick = (status) => {
    setSelectedStage(status);
    setShowStageDialog(true);
  };

  // Handle order click
  const handleOrderClick = (order) => {
    setSelectedOrder(order);
    fetchOrderDetail(order.order_id);
  };

  // Handle action button click
  const handleActionClick = (action) => {
    setCurrentAction(action);
    setActionReason('');
    if (action.requiresReason) {
      setShowActionDialog(true);
    } else {
      // Execute immediately for actions that don't require reason
      executeAction(action, '');
    }
  };

  // Execute action
  const executeAction = async (action, reason) => {
    if (!selectedOrder) return;
    
    setIsSubmitting(true);
    try {
      const token = localStorage.getItem('auth_token');
      let endpoint = '';
      let body = {};
      
      // Map action keys to API endpoints
      switch (action.key) {
        case 'approve':
          endpoint = `/api/admin/orders/${selectedOrder.order_id}/approve`;
          break;
        case 'regen':
          endpoint = `/api/admin/orders/${selectedOrder.order_id}/request-regen`;
          body = { note: reason };
          break;
        case 'request_info':
          endpoint = `/api/admin/orders/${selectedOrder.order_id}/request-info`;
          body = { note: reason };
          break;
        case 'cancel':
          endpoint = `/api/admin/orders/${selectedOrder.order_id}/transition`;
          body = { new_status: 'CANCELLED', reason };
          break;
        case 'delete':
          endpoint = `/api/admin/orders/${selectedOrder.order_id}/delete`;
          body = { reason };
          break;
        case 'resend_request':
          endpoint = `/api/admin/orders/${selectedOrder.order_id}/resend-request`;
          body = { reason };
          break;
        case 'retry_delivery':
          endpoint = `/api/admin/orders/${selectedOrder.order_id}/transition`;
          body = { new_status: 'DELIVERING', reason: `Retry delivery: ${reason}` };
          break;
        case 'retry_queued':
          endpoint = `/api/admin/orders/${selectedOrder.order_id}/transition`;
          body = { new_status: 'QUEUED', reason: `Re-queued: ${reason}` };
          break;
        case 'rollback':
          endpoint = `/api/admin/orders/${selectedOrder.order_id}/rollback`;
          body = { reason };
          break;
        default:
          // Handle transition_* actions
          if (action.key.startsWith('transition_')) {
            const newStatus = action.key.replace('transition_', '').toUpperCase();
            endpoint = `/api/admin/orders/${selectedOrder.order_id}/transition`;
            body = { new_status: newStatus, reason };
          }
          break;
      }
      
      if (!endpoint) {
        toast.error('Unknown action');
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
        setShowDeleteDialog(false);
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

  // Handle delete
  const handleDelete = () => {
    setShowDeleteDialog(true);
  };

  const confirmDelete = async () => {
    if (!actionReason.trim()) {
      toast.error('Reason is required for deletion');
      return;
    }
    await executeAction({ key: 'delete', requiresReason: true }, actionReason);
  };

  // Get actions for current order state
  const getActionsForState = (status) => {
    return stateActions[status] || [];
  };

  // Check if stage has orders (for emphasis)
  const stageHasOrders = (status) => {
    return (counts[status] || 0) > 0;
  };

  return (
    <AdminLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold text-midnight-blue">Orders Pipeline</h1>
            <div className="text-gray-500 flex items-center gap-2">
              <span>Operational Control Center</span>
              {lastUpdated && (
                <span className="text-xs">
                  • Last updated: {lastUpdated.toLocaleTimeString()}
                </span>
              )}
              {autoRefresh && (
                <Badge variant="outline" className="text-xs">
                  <Zap className="w-3 h-3 mr-1" />
                  Live
                </Badge>
              )}
            </div>
          </div>
          <div className="flex items-center space-x-3">
            {/* Search */}
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
            
            {/* Sort */}
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="w-48" data-testid="sort-select">
                <SelectValue placeholder="Sort by..." />
              </SelectTrigger>
              <SelectContent>
                {sortOptions.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            {/* Auto-refresh toggle */}
            <Button
              variant={autoRefresh ? 'default' : 'outline'}
              size="sm"
              onClick={() => setAutoRefresh(!autoRefresh)}
              data-testid="auto-refresh-toggle"
            >
              {autoRefresh ? <Pause className="w-4 h-4 mr-1" /> : <Play className="w-4 h-4 mr-1" />}
              {autoRefresh ? 'Pause' : 'Live'}
            </Button>
            
            {/* Manual refresh */}
            <Button
              variant="outline"
              onClick={() => fetchOrders()}
              disabled={isLoading}
              data-testid="refresh-orders"
            >
              <RefreshCw className={cn("w-4 h-4 mr-2", isLoading && "animate-spin")} />
              Refresh
            </Button>
          </div>
        </div>

        {/* Pipeline View - Clickable Stages with Visual Emphasis */}
        <div className="overflow-x-auto pb-4">
          <div className="flex space-x-3 min-w-max">
            {pipelineColumns.map((column) => {
              const hasOrders = stageHasOrders(column.status);
              const orderCount = counts[column.status] || 0;
              const stageOrders = getOrdersForStatus(column.status);
              
              return (
                <div
                  key={column.status}
                  className={cn(
                    "w-56 flex-shrink-0 rounded-lg border-t-4 transition-all cursor-pointer",
                    hasOrders
                      ? `${column.bgActive} ${column.borderActive} shadow-md hover:shadow-lg`
                      : `${column.bgMuted} ${column.borderMuted} opacity-60 hover:opacity-80`
                  )}
                  onClick={() => handleStageClick(column.status)}
                  data-testid={`pipeline-stage-${column.status.toLowerCase()}`}
                >
                  {/* Stage Header - Clickable */}
                  <div className={cn(
                    "p-3 border-b cursor-pointer",
                    hasOrders ? "border-gray-200" : "border-gray-100"
                  )}>
                    <div className="flex justify-between items-center">
                      <h3 className={cn(
                        "font-semibold text-sm",
                        hasOrders ? "text-midnight-blue" : "text-gray-400"
                      )}>
                        {column.label}
                      </h3>
                      <Badge
                        variant={hasOrders ? "default" : "secondary"}
                        className={cn(
                          "text-xs",
                          hasOrders && `bg-${column.color}-500`
                        )}
                      >
                        {orderCount}
                      </Badge>
                    </div>
                    {hasOrders && (
                      <p className="text-xs text-gray-500 mt-1">
                        Click to view all
                      </p>
                    )}
                  </div>
                  
                  {/* Order Preview (max 3) */}
                  <div className="p-2 space-y-2 min-h-[120px]">
                    {isLoading ? (
                      <div className="animate-pulse space-y-2">
                        <div className="h-16 bg-gray-200 rounded" />
                      </div>
                    ) : stageOrders.length === 0 ? (
                      <div className="text-center py-4 text-gray-400 text-xs">
                        No orders
                      </div>
                    ) : (
                      <>
                        {stageOrders.slice(0, 3).map((order) => (
                          <Card
                            key={order.order_id}
                            className={cn(
                              "cursor-pointer hover:shadow-md transition-shadow",
                              order.priority && "border-l-4 border-l-red-500"
                            )}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOrderClick(order);
                            }}
                            data-testid={`order-card-${order.order_id}`}
                          >
                            <CardContent className="p-2">
                              <div className="flex justify-between items-start">
                                <span className="text-xs font-mono text-gray-500 truncate">
                                  {order.order_id}
                                </span>
                                {order.priority && (
                                  <Flag className="w-3 h-3 text-red-500" />
                                )}
                              </div>
                              <p className="font-medium text-xs text-midnight-blue truncate mt-1">
                                {order.service_name}
                              </p>
                              <div className="flex justify-between items-center mt-1">
                                <span className="text-xs text-gray-400 truncate">
                                  {order.customer?.full_name}
                                </span>
                                <span className="text-xs text-gray-400 flex items-center">
                                  <Clock className="w-3 h-3 mr-1" />
                                  {formatTimeInState(order)}
                                </span>
                              </div>
                            </CardContent>
                          </Card>
                        ))}
                        {stageOrders.length > 3 && (
                          <div className="text-center text-xs text-gray-500 py-1">
                            +{stageOrders.length - 3} more
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Stage Detail Dialog - Shows all orders in selected stage */}
        <Dialog open={showStageDialog} onOpenChange={setShowStageDialog}>
          <DialogContent className="max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                {selectedStage && (
                  <>
                    <Badge className={statusColors[selectedStage]}>
                      {selectedStage}
                    </Badge>
                    <span>Orders</span>
                    <Badge variant="outline">{counts[selectedStage] || 0}</Badge>
                  </>
                )}
              </DialogTitle>
              <DialogDescription>
                All orders currently in this pipeline stage
              </DialogDescription>
            </DialogHeader>
            
            {/* Sort controls */}
            <div className="flex items-center gap-4 py-2 border-b">
              <Label className="text-sm text-gray-500">Sort by:</Label>
              <Select value={sortBy} onValueChange={setSortBy}>
                <SelectTrigger className="w-56">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {sortOptions.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            {/* Orders list */}
            <div className="flex-1 overflow-y-auto py-4 space-y-3">
              {selectedStage && getOrdersForStatus(selectedStage).length === 0 ? (
                <div className="text-center py-12 text-gray-400">
                  No orders in this stage
                </div>
              ) : (
                selectedStage && getOrdersForStatus(selectedStage).map((order) => (
                  <Card
                    key={order.order_id}
                    className={cn(
                      "cursor-pointer hover:shadow-md transition-shadow",
                      order.priority && "border-l-4 border-l-red-500"
                    )}
                    onClick={() => handleOrderClick(order)}
                  >
                    <CardContent className="p-4">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-sm font-medium">
                              {order.order_id}
                            </span>
                            {order.priority && (
                              <Badge variant="destructive" className="text-xs">
                                <Flag className="w-3 h-3 mr-1" />
                                Priority
                              </Badge>
                            )}
                          </div>
                          <p className="font-semibold text-midnight-blue mt-1">
                            {order.service_name}
                          </p>
                          <p className="text-sm text-gray-500">
                            {order.customer?.full_name} • {order.customer?.email}
                          </p>
                        </div>
                        <div className="text-right text-sm">
                          <div className="flex items-center text-gray-500">
                            <Calendar className="w-4 h-4 mr-1" />
                            Entered: {formatDate(order.updated_at)}
                          </div>
                          <div className="flex items-center text-gray-500 mt-1">
                            <Timer className="w-4 h-4 mr-1" />
                            Time in stage: {formatTimeInState(order)}
                          </div>
                          {order.sla_hours && (
                            <div className={cn(
                              "flex items-center mt-1",
                              getHoursInState(order) > order.sla_hours * 0.8
                                ? "text-red-500"
                                : "text-gray-500"
                            )}>
                              <AlertCircle className="w-4 h-4 mr-1" />
                              SLA: {order.sla_hours}h
                            </div>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          </DialogContent>
        </Dialog>

        {/* Order Detail Dialog with Action Panel */}
        <Dialog open={showDetailDialog} onOpenChange={setShowDetailDialog}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            {orderDetail && (
              <>
                <DialogHeader>
                  <DialogTitle className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span>{orderDetail.order?.order_id}</span>
                      {orderDetail.order?.priority && (
                        <Badge variant="destructive">
                          <Flag className="w-3 h-3 mr-1" />
                          Priority
                        </Badge>
                      )}
                    </div>
                    <Badge className={statusColors[orderDetail.order?.status]}>
                      {orderDetail.order?.status}
                    </Badge>
                  </DialogTitle>
                  <DialogDescription>
                    {orderDetail.order?.service_name}
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-6 py-4">
                  {/* Stage Entry Time */}
                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center text-sm text-gray-600">
                      <Calendar className="w-4 h-4 mr-2" />
                      Entered current stage: {formatDate(orderDetail.order?.updated_at)}
                    </div>
                    <div className="flex items-center text-sm text-gray-600">
                      <Timer className="w-4 h-4 mr-2" />
                      Time in stage: {orderDetail.order && formatTimeInState(orderDetail.order)}
                    </div>
                  </div>

                  {/* Customer & Service Info */}
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

                  {/* STATE-SPECIFIC ACTION PANEL */}
                  {orderDetail.order?.status && getActionsForState(orderDetail.order.status).length > 0 && (
                    <Card className="border-2 border-electric-teal">
                      <CardHeader className="pb-2 bg-electric-teal/5">
                        <CardTitle className="text-sm flex items-center text-electric-teal">
                          <Zap className="w-4 h-4 mr-2" />
                          Available Actions for {orderDetail.order.status}
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="pt-4">
                        <div className="flex flex-wrap gap-3">
                          {getActionsForState(orderDetail.order.status).map((action) => (
                            <Button
                              key={action.key}
                              variant={action.variant === 'success' ? 'default' : action.variant}
                              className={cn(
                                action.variant === 'success' && 'bg-green-600 hover:bg-green-700'
                              )}
                              onClick={() => handleActionClick(action)}
                              data-testid={`action-${action.key}`}
                            >
                              <action.icon className="w-4 h-4 mr-2" />
                              {action.label}
                            </Button>
                          ))}
                        </div>
                        
                        {/* Always show delete option */}
                        <div className="mt-4 pt-4 border-t">
                          <Button
                            variant="ghost"
                            className="text-red-600 hover:text-red-700 hover:bg-red-50"
                            onClick={handleDelete}
                            data-testid="action-delete"
                          >
                            <Trash2 className="w-4 h-4 mr-2" />
                            Delete Order (Requires Reason)
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Workflow Timeline */}
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center">
                        <FileText className="w-4 h-4 mr-2" />
                        Workflow Timeline (Audit Trail)
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-4 max-h-64 overflow-y-auto">
                        {orderDetail.timeline?.map((entry, index) => (
                          <div key={entry.execution_id} className="flex">
                            <div className="flex flex-col items-center mr-4">
                              <div className={cn(
                                "w-3 h-3 rounded-full",
                                index === orderDetail.timeline.length - 1
                                  ? "bg-electric-teal"
                                  : entry.transition_type === 'admin_manual'
                                    ? "bg-orange-500"
                                    : "bg-gray-300"
                              )} />
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
                                  <Badge
                                    variant="outline"
                                    className={cn(
                                      "ml-2 text-xs",
                                      entry.transition_type === 'admin_manual' && "border-orange-500 text-orange-600",
                                      entry.transition_type === 'admin_delete' && "border-red-500 text-red-600"
                                    )}
                                  >
                                    {entry.transition_type}
                                  </Badge>
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
                                  <strong>Reason:</strong> {entry.reason}
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

        {/* Action Confirmation Dialog */}
        <Dialog open={showActionDialog} onOpenChange={setShowActionDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center">
                {currentAction?.icon && <currentAction.icon className="w-5 h-5 mr-2" />}
                {currentAction?.label}
              </DialogTitle>
              <DialogDescription>
                {currentAction?.key === 'approve' 
                  ? 'This will finalize the order and trigger automatic delivery.'
                  : 'Please provide a reason for this action. This will be logged in the audit trail.'}
              </DialogDescription>
            </DialogHeader>
            
            <div className="py-4">
              <Label htmlFor="action-reason">
                Reason {currentAction?.requiresReason ? '(Required)' : '(Optional)'}
              </Label>
              <Textarea
                id="action-reason"
                placeholder="Enter reason for this action..."
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
                rows={4}
                className="mt-2"
                data-testid="action-reason-input"
              />
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowActionDialog(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => executeAction(currentAction, actionReason)}
                disabled={isSubmitting || (currentAction?.requiresReason && !actionReason.trim())}
                className={cn(
                  currentAction?.variant === 'success' && 'bg-green-600 hover:bg-green-700',
                  currentAction?.variant === 'destructive' && 'bg-red-600 hover:bg-red-700'
                )}
                data-testid="action-confirm"
              >
                {isSubmitting ? 'Processing...' : 'Confirm'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="flex items-center text-red-600">
                <Trash2 className="w-5 h-5 mr-2" />
                Delete Order
              </AlertDialogTitle>
              <AlertDialogDescription>
                This action cannot be undone. The order will be permanently deleted.
                A mandatory reason is required and will be logged as <code>admin_delete</code>.
              </AlertDialogDescription>
            </AlertDialogHeader>
            
            <div className="py-4">
              <Label htmlFor="delete-reason" className="text-red-600">
                Reason (Required)
              </Label>
              <Textarea
                id="delete-reason"
                placeholder="Why is this order being deleted?"
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
                rows={3}
                className="mt-2 border-red-200 focus:border-red-500"
                data-testid="delete-reason-input"
              />
            </div>
            
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={confirmDelete}
                disabled={isSubmitting || !actionReason.trim()}
                className="bg-red-600 hover:bg-red-700"
                data-testid="delete-confirm"
              >
                {isSubmitting ? 'Deleting...' : 'Delete Order'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </AdminLayout>
  );
};

export default AdminOrdersPage;
