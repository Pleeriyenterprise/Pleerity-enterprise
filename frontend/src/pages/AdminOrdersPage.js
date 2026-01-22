import React, { useState, useEffect, useCallback, useRef } from 'react';
import AdminLayout from '../components/admin/AdminLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
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
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../components/ui/tabs';
import { Textarea } from '../components/ui/textarea';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
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
  Eye,
  Lock,
  Unlock,
  Download,
  File,
  History,
  Send,
  Upload,
  Check,
  Info,
  Archive,
  X,
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

// Pipeline columns configuration
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

// Regeneration reasons dropdown options
const regenReasons = [
  { value: 'missing_info', label: 'Missing Information' },
  { value: 'incorrect_wording', label: 'Incorrect Wording' },
  { value: 'tone_style', label: 'Tone/Style Issue' },
  { value: 'wrong_emphasis', label: 'Wrong Section Emphasis' },
  { value: 'formatting', label: 'Formatting Issue' },
  { value: 'factual_error', label: 'Factual Error' },
  { value: 'legal_compliance', label: 'Legal/Compliance Issue' },
  { value: 'other', label: 'Other' },
];

// Common requested fields for client info
const commonRequestedFields = [
  { id: 'tenant_name', label: 'Tenant Full Name' },
  { id: 'property_address', label: 'Property Address Confirmation' },
  { id: 'tenancy_start_date', label: 'Tenancy Start Date' },
  { id: 'tenancy_end_date', label: 'Tenancy End Date' },
  { id: 'notice_date', label: 'Notice Date' },
  { id: 'deposit_amount', label: 'Deposit Amount' },
  { id: 'monthly_rent', label: 'Monthly Rent' },
  { id: 'eicr_date', label: 'EICR Certificate Date' },
  { id: 'gas_cert_date', label: 'Gas Safety Certificate Date' },
  { id: 'epc_rating', label: 'EPC Rating' },
  { id: 'landlord_details', label: 'Landlord Details' },
  { id: 'clarification', label: 'General Clarification' },
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
  const [documentVersions, setDocumentVersions] = useState([]);
  const [selectedDocVersion, setSelectedDocVersion] = useState(null);
  
  // Sorting
  const [sortBy, setSortBy] = useState('priority');
  
  // Search
  const [searchQuery, setSearchQuery] = useState('');
  
  // Dialog states
  const [showStageDialog, setShowStageDialog] = useState(false);
  const [showDetailDialog, setShowDetailDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showRegenModal, setShowRegenModal] = useState(false);
  const [showInfoRequestModal, setShowInfoRequestModal] = useState(false);
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [showDocumentViewer, setShowDocumentViewer] = useState(false);
  
  // Regeneration modal state
  const [regenReason, setRegenReason] = useState('');
  const [regenNotes, setRegenNotes] = useState('');
  const [regenSections, setRegenSections] = useState([]);
  const [regenGuardrails, setRegenGuardrails] = useState({
    preserve_names_dates: false,
    preserve_format: false,
  });
  
  // Info request modal state
  const [infoRequestNotes, setInfoRequestNotes] = useState('');
  const [requestedFields, setRequestedFields] = useState([]);
  const [deadlineDays, setDeadlineDays] = useState('');
  const [requestAttachments, setRequestAttachments] = useState(false);
  
  // Approval modal state
  const [approveVersion, setApproveVersion] = useState(null);
  const [approveNotes, setApproveNotes] = useState('');
  
  // Action state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deleteReason, setDeleteReason] = useState('');
  
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
        fetchOrders(false);
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
        
        // Also fetch document versions
        const docsResponse = await fetch(`${API_URL}/api/admin/orders/${orderId}/documents`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        
        if (docsResponse.ok) {
          const docsData = await docsResponse.json();
          setDocumentVersions(docsData.versions || []);
          if (docsData.current_version) {
            setSelectedDocVersion(docsData.current_version);
          }
        }
        
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
    
    filtered.sort((a, b) => {
      if (a.priority && !b.priority) return -1;
      if (!a.priority && b.priority) return 1;
      
      switch (sortBy) {
        case 'entered_desc':
          return new Date(b.updated_at) - new Date(a.updated_at);
        case 'entered_asc':
          return new Date(a.updated_at) - new Date(b.updated_at);
        case 'priority':
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

  // ==========================================
  // APPROVAL ACTION
  // ==========================================
  const handleApproveClick = () => {
    if (!documentVersions.length) {
      toast.error('No document to approve. Generate documents first.');
      return;
    }
    setApproveVersion(documentVersions[documentVersions.length - 1]?.version || 1);
    setApproveNotes('');
    setShowApproveModal(true);
  };

  const submitApproval = async () => {
    if (!approveVersion) {
      toast.error('Please select a version to approve');
      return;
    }
    
    setIsSubmitting(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_URL}/api/admin/orders/${selectedOrder.order_id}/approve`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          version: approveVersion,
          notes: approveNotes || null,
        }),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        toast.success(`Order approved! Document v${approveVersion} locked as final.`);
        setShowApproveModal(false);
        setShowDetailDialog(false);
        fetchOrders();
      } else {
        toast.error(data.detail || 'Failed to approve order');
      }
    } catch (error) {
      toast.error('Failed to approve order');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ==========================================
  // REGENERATION ACTION
  // ==========================================
  const handleRegenClick = () => {
    setRegenReason('');
    setRegenNotes('');
    setRegenSections([]);
    setRegenGuardrails({ preserve_names_dates: false, preserve_format: false });
    setShowRegenModal(true);
  };

  const submitRegeneration = async () => {
    if (!regenReason) {
      toast.error('Please select a reason for regeneration');
      return;
    }
    if (!regenNotes.trim()) {
      toast.error('Correction notes are required for regeneration');
      return;
    }
    
    setIsSubmitting(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_URL}/api/admin/orders/${selectedOrder.order_id}/request-regen`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          reason: regenReason,
          correction_notes: regenNotes,
          affected_sections: regenSections.length ? regenSections : null,
          guardrails: regenGuardrails,
        }),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        toast.success('Regeneration requested. System will regenerate automatically.');
        setShowRegenModal(false);
        setShowDetailDialog(false);
        fetchOrders();
      } else {
        toast.error(data.detail || 'Failed to request regeneration');
      }
    } catch (error) {
      toast.error('Failed to request regeneration');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ==========================================
  // REQUEST MORE INFO ACTION
  // ==========================================
  const handleRequestInfoClick = () => {
    setInfoRequestNotes('');
    setRequestedFields([]);
    setDeadlineDays('');
    setRequestAttachments(false);
    setShowInfoRequestModal(true);
  };

  const toggleRequestedField = (fieldId) => {
    setRequestedFields(prev => 
      prev.includes(fieldId) 
        ? prev.filter(f => f !== fieldId)
        : [...prev, fieldId]
    );
  };

  const submitInfoRequest = async () => {
    if (!infoRequestNotes.trim()) {
      toast.error('Please specify what information you need');
      return;
    }
    
    setIsSubmitting(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_URL}/api/admin/orders/${selectedOrder.order_id}/request-info`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          request_notes: infoRequestNotes,
          requested_fields: requestedFields.length ? requestedFields : null,
          deadline_days: deadlineDays && deadlineDays !== 'none' ? parseInt(deadlineDays) : null,
          request_attachments: requestAttachments,
        }),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        toast.success('Info request sent to client. SLA paused.');
        setShowInfoRequestModal(false);
        setShowDetailDialog(false);
        fetchOrders();
      } else {
        toast.error(data.detail || 'Failed to send info request');
      }
    } catch (error) {
      toast.error('Failed to send info request');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ==========================================
  // GENERATE DOCUMENTS
  // ==========================================
  const handleGenerateDocuments = async () => {
    setIsSubmitting(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_URL}/api/admin/orders/${selectedOrder.order_id}/generate-documents`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      
      const data = await response.json();
      
      if (response.ok) {
        toast.success(`Document v${data.version.version} generated`);
        // Refresh order details
        fetchOrderDetail(selectedOrder.order_id);
      } else {
        toast.error(data.detail || 'Failed to generate documents');
      }
    } catch (error) {
      toast.error('Failed to generate documents');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ==========================================
  // CANCEL/ARCHIVE ACTIONS
  // ==========================================
  const handleCancelOrder = async () => {
    if (!deleteReason.trim()) {
      toast.error('Reason is required to cancel order');
      return;
    }
    
    setIsSubmitting(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_URL}/api/admin/orders/${selectedOrder.order_id}/cancel`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ reason: deleteReason }),
      });
      
      if (response.ok) {
        toast.success('Order cancelled');
        setShowDeleteDialog(false);
        setShowDetailDialog(false);
        fetchOrders();
      } else {
        const data = await response.json();
        toast.error(data.detail || 'Failed to cancel order');
      }
    } catch (error) {
      toast.error('Failed to cancel order');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleArchiveOrder = async () => {
    if (!deleteReason.trim()) {
      toast.error('Reason is required to archive order');
      return;
    }
    
    setIsSubmitting(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_URL}/api/admin/orders/${selectedOrder.order_id}/archive`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ reason: deleteReason }),
      });
      
      if (response.ok) {
        toast.success('Order archived');
        setShowDeleteDialog(false);
        setShowDetailDialog(false);
        fetchOrders();
      } else {
        const data = await response.json();
        toast.error(data.detail || 'Failed to archive order');
      }
    } catch (error) {
      toast.error('Failed to archive order');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ==========================================
  // DELETE ACTION (Legacy - kept for compatibility)
  // ==========================================
  const handleDeleteOrder = async () => {
    if (!deleteReason.trim()) {
      toast.error('Reason is required to delete order');
      return;
    }
    
    setIsSubmitting(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_URL}/api/admin/orders/${selectedOrder.order_id}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ reason: deleteReason }),
      });
      
      if (response.ok) {
        toast.success('Order deleted');
        setShowDeleteDialog(false);
        setShowDetailDialog(false);
        fetchOrders();
      } else {
        const data = await response.json();
        toast.error(data.detail || 'Failed to delete order');
      }
    } catch (error) {
      toast.error('Failed to delete order');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ==========================================
  // GENERIC TRANSITION
  // ==========================================
  const handleTransition = async (newStatus, reason) => {
    setIsSubmitting(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_URL}/api/admin/orders/${selectedOrder.order_id}/transition`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ new_status: newStatus, reason }),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        toast.success(`Order moved to ${newStatus}`);
        setShowDetailDialog(false);
        fetchOrders();
      } else {
        toast.error(data.detail || 'Failed to transition order');
      }
    } catch (error) {
      toast.error('Failed to transition order');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ==========================================
  // RENDER: Pipeline Column
  // ==========================================
  const renderPipelineColumn = (column) => {
    const count = counts[column.status] || 0;
    const hasOrders = count > 0;
    
    return (
      <div
        key={column.status}
        data-testid={`pipeline-column-${column.status.toLowerCase()}`}
        onClick={() => count > 0 && handleStageClick(column.status)}
        className={cn(
          'flex flex-col items-center justify-center p-3 rounded-lg border-2 transition-all min-w-[100px]',
          hasOrders ? column.bgActive : column.bgMuted,
          hasOrders ? column.borderActive : column.borderMuted,
          count > 0 && 'cursor-pointer hover:scale-105 hover:shadow-md',
        )}
      >
        <span className={cn(
          'text-2xl font-bold',
          hasOrders ? `text-${column.color}-700` : 'text-gray-400'
        )}>
          {count}
        </span>
        <span className={cn(
          'text-xs font-medium text-center',
          hasOrders ? `text-${column.color}-600` : 'text-gray-400'
        )}>
          {column.label}
        </span>
      </div>
    );
  };

  // ==========================================
  // RENDER: Document Version Item
  // ==========================================
  const renderDocumentVersion = (version) => {
    const isSelected = selectedDocVersion?.version === version.version;
    const isApproved = version.is_approved;
    
    return (
      <div
        key={version.version}
        onClick={() => setSelectedDocVersion(version)}
        className={cn(
          'p-3 rounded-lg border cursor-pointer transition-all',
          isSelected ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300',
          isApproved && 'ring-2 ring-green-500'
        )}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-gray-500" />
            <span className="font-medium">v{version.version}</span>
            {version.is_regeneration && (
              <Badge variant="outline" className="text-xs">Regenerated</Badge>
            )}
            {isApproved && (
              <Badge className="bg-green-100 text-green-800 text-xs">
                <Lock className="h-3 w-3 mr-1" />
                Approved
              </Badge>
            )}
          </div>
          <span className="text-xs text-gray-500">
            {formatDate(version.generated_at)}
          </span>
        </div>
        {version.regeneration_notes && (
          <p className="text-xs text-gray-500 mt-1 line-clamp-2">
            {version.regeneration_notes}
          </p>
        )}
      </div>
    );
  };

  // ==========================================
  // RENDER: Client Input Section (for CLIENT_INPUT_REQUIRED)
  // ==========================================
  const renderClientInputSection = () => {
    const order = orderDetail?.order || orderDetail;
    if (!order?.client_input_request) return null;
    
    const request = order.client_input_request;
    const responses = order.client_input_responses || [];
    
    return (
      <div className="space-y-4 border-t pt-4 mt-4">
        <h4 className="font-medium flex items-center gap-2">
          <MessageSquare className="h-4 w-4" />
          Client Input Request
        </h4>
        
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
          <p className="text-sm font-medium text-yellow-800">What we requested:</p>
          <p className="text-sm mt-1 whitespace-pre-wrap">{request.request_notes}</p>
          {request.requested_fields?.length > 0 && (
            <div className="mt-2">
              <p className="text-xs font-medium text-yellow-700">Requested fields:</p>
              <div className="flex flex-wrap gap-1 mt-1">
                {request.requested_fields.map(f => (
                  <Badge key={f} variant="outline" className="text-xs">{f}</Badge>
                ))}
              </div>
            </div>
          )}
          <p className="text-xs text-yellow-600 mt-2">
            Requested: {formatDate(request.requested_at)} by {request.requested_by_admin_email}
          </p>
        </div>
        
        {responses.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Client Responses:</p>
            {responses.map((resp, idx) => (
              <div key={idx} className="bg-green-50 border border-green-200 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <Badge variant="outline" className="text-xs">Response v{resp.version}</Badge>
                  <span className="text-xs text-gray-500">{formatDate(resp.submitted_at)}</span>
                </div>
                <div className="space-y-1">
                  {Object.entries(resp.payload || {}).map(([key, value]) => (
                    <div key={key} className="flex">
                      <span className="text-xs font-medium w-32 text-gray-600">{key.replace(/_/g, ' ')}:</span>
                      <span className="text-xs">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // ==========================================
  // RENDER: Review Actions (INTERNAL_REVIEW specific)
  // ==========================================
  const renderReviewActions = () => {
    const status = orderDetail?.order?.status || orderDetail?.status;
    if (status !== 'INTERNAL_REVIEW') return null;
    
    const isLocked = orderDetail?.order?.version_locked || orderDetail?.version_locked;
    const hasDocuments = documentVersions.length > 0;
    
    return (
      <div className="space-y-4 border-t pt-4 mt-4">
        <div className="flex items-center justify-between">
          <h4 className="font-medium flex items-center gap-2">
            <Eye className="h-4 w-4" />
            Document Review Actions
          </h4>
          {isLocked && (
            <Badge className="bg-green-100 text-green-800">
              <Lock className="h-3 w-3 mr-1" />
              Version Locked
            </Badge>
          )}
        </div>
        
        {!hasDocuments ? (
          <div className="bg-gray-50 rounded-lg p-4 text-center">
            <FileText className="h-8 w-8 mx-auto text-gray-400 mb-2" />
            <p className="text-sm text-gray-500">No documents generated yet</p>
            <Button
              onClick={handleGenerateDocuments}
              disabled={isSubmitting}
              className="mt-3"
              size="sm"
            >
              {isSubmitting ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : <FileText className="h-4 w-4 mr-2" />}
              Generate Documents
            </Button>
          </div>
        ) : (
          <>
            {/* Document versions list */}
            <div className="space-y-2">
              <Label className="text-sm">Document Versions</Label>
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {documentVersions.map(renderDocumentVersion)}
              </div>
            </div>
            
            {/* Document preview button */}
            {selectedDocVersion && (
              <Button
                variant="outline"
                className="w-full"
                onClick={() => setShowDocumentViewer(true)}
              >
                <Eye className="h-4 w-4 mr-2" />
                Preview Document v{selectedDocVersion.version}
              </Button>
            )}
            
            {/* Action buttons */}
            <div className="grid grid-cols-1 gap-2">
              <Button
                onClick={handleApproveClick}
                disabled={isLocked || isSubmitting}
                className="bg-green-600 hover:bg-green-700"
                data-testid="approve-finalize-btn"
              >
                <CheckCircle2 className="h-4 w-4 mr-2" />
                Approve & Finalize
              </Button>
              
              <Button
                variant="outline"
                onClick={handleRegenClick}
                disabled={isLocked || isSubmitting}
                data-testid="request-regen-btn"
              >
                <RotateCcw className="h-4 w-4 mr-2" />
                Request Regeneration
              </Button>
              
              <Button
                variant="outline"
                onClick={handleRequestInfoClick}
                disabled={isSubmitting}
                data-testid="request-info-btn"
              >
                <MessageSquare className="h-4 w-4 mr-2" />
                Request More Info
              </Button>
            </div>
          </>
        )}
      </div>
    );
  };

  // ==========================================
  // RENDER: Audit Timeline
  // ==========================================
  const renderAuditTimeline = () => {
    if (!orderDetail?.timeline?.length) return null;
    
    return (
      <div className="space-y-2">
        {orderDetail.timeline.map((event, idx) => (
          <div key={idx} className="flex gap-3 text-sm">
            <div className="flex flex-col items-center">
              <div className={cn(
                'w-2 h-2 rounded-full',
                idx === 0 ? 'bg-blue-500' : 'bg-gray-300'
              )} />
              {idx < orderDetail.timeline.length - 1 && (
                <div className="w-0.5 h-full bg-gray-200 mt-1" />
              )}
            </div>
            <div className="flex-1 pb-4">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-xs">
                  {event.new_state || event.action}
                </Badge>
                <span className="text-xs text-gray-500">{formatDate(event.timestamp)}</span>
              </div>
              <p className="text-xs text-gray-600 mt-1">{event.reason}</p>
              {event.triggered_by_email && (
                <p className="text-xs text-gray-400">by {event.triggered_by_email}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    );
  };

  // ==========================================
  // MAIN RENDER
  // ==========================================
  return (
    <AdminLayout>
      <div className="space-y-6" data-testid="admin-orders-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Orders Pipeline</h1>
            <p className="text-gray-500 text-sm">
              Enterprise-grade order management and workflow control
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Clock className="h-4 w-4" />
              <span>Updated: {lastUpdated ? formatDate(lastUpdated) : '-'}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={autoRefresh ? 'text-green-600' : 'text-gray-500'}
            >
              {autoRefresh ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
            </Button>
            <Button variant="outline" size="sm" onClick={() => fetchOrders()}>
              <RefreshCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
            </Button>
          </div>
        </div>

        {/* Pipeline View */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Package className="h-5 w-5" />
              Pipeline Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {pipelineColumns.map(renderPipelineColumn)}
            </div>
          </CardContent>
        </Card>

        {/* Sort Controls */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Label className="text-sm text-gray-500">Sort by:</Label>
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="w-[200px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {sortOptions.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex-1">
            <div className="relative max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search orders..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>
        </div>

        {/* Stage Dialog - Shows orders in selected stage */}
        <Dialog open={showStageDialog} onOpenChange={setShowStageDialog}>
          <DialogContent className="max-w-2xl max-h-[80vh]">
            <DialogHeader>
              <DialogTitle>
                {pipelineColumns.find(c => c.status === selectedStage)?.label || selectedStage} Orders
              </DialogTitle>
              <DialogDescription>
                {counts[selectedStage] || 0} orders in this stage
              </DialogDescription>
            </DialogHeader>
            <ScrollArea className="max-h-[60vh]">
              <div className="space-y-3 pr-4">
                {getOrdersForStatus(selectedStage).map(order => (
                  <Card
                    key={order.order_id}
                    className="cursor-pointer hover:shadow-md transition-shadow"
                    onClick={() => {
                      setShowStageDialog(false);
                      handleOrderClick(order);
                    }}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="font-medium">{order.order_id}</p>
                          <p className="text-sm text-gray-500">{order.service_name}</p>
                          <p className="text-sm text-gray-500">
                            {order.customer?.full_name || order.customer?.email}
                          </p>
                        </div>
                        <div className="text-right">
                          <Badge className={statusColors[order.status]}>
                            {order.status.replace(/_/g, ' ')}
                          </Badge>
                          <p className="text-xs text-gray-500 mt-1">
                            <Timer className="inline h-3 w-3 mr-1" />
                            {formatTimeInState(order)}
                          </p>
                          {order.priority && (
                            <Badge className="bg-red-100 text-red-800 mt-1">
                              <Flag className="h-3 w-3 mr-1" />
                              Priority
                            </Badge>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </ScrollArea>
          </DialogContent>
        </Dialog>

        {/* Order Detail Dialog */}
        <Dialog open={showDetailDialog} onOpenChange={setShowDetailDialog}>
          <DialogContent className="max-w-3xl max-h-[90vh]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                Order: {orderDetail?.order?.order_id || orderDetail?.order_id}
                <Badge className={statusColors[orderDetail?.order?.status || orderDetail?.status]}>
                  {(orderDetail?.order?.status || orderDetail?.status)?.replace(/_/g, ' ')}
                </Badge>
              </DialogTitle>
            </DialogHeader>
            
            <Tabs defaultValue="details" className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="details">Details</TabsTrigger>
                <TabsTrigger value="documents">Documents</TabsTrigger>
                <TabsTrigger value="timeline">Timeline</TabsTrigger>
              </TabsList>
              
              <TabsContent value="details" className="space-y-4">
                <ScrollArea className="max-h-[50vh]">
                  {/* Customer Info */}
                  <div className="space-y-2">
                    <h4 className="font-medium flex items-center gap-2">
                      <User className="h-4 w-4" />
                      Customer
                    </h4>
                    <div className="bg-gray-50 rounded-lg p-3 space-y-1 text-sm">
                      <p><span className="text-gray-500">Name:</span> {orderDetail?.order?.customer?.full_name || orderDetail?.customer?.full_name}</p>
                      <p><span className="text-gray-500">Email:</span> {orderDetail?.order?.customer?.email || orderDetail?.customer?.email}</p>
                      <p><span className="text-gray-500">Phone:</span> {orderDetail?.order?.customer?.phone || orderDetail?.customer?.phone || '-'}</p>
                    </div>
                  </div>
                  
                  {/* Service Info */}
                  <div className="space-y-2 mt-4">
                    <h4 className="font-medium flex items-center gap-2">
                      <Package className="h-4 w-4" />
                      Service
                    </h4>
                    <div className="bg-gray-50 rounded-lg p-3 space-y-1 text-sm">
                      <p><span className="text-gray-500">Name:</span> {orderDetail?.order?.service_name || orderDetail?.service_name}</p>
                      <p><span className="text-gray-500">Code:</span> {orderDetail?.order?.service_code || orderDetail?.service_code}</p>
                      <p><span className="text-gray-500">Category:</span> {orderDetail?.order?.service_category || orderDetail?.service_category}</p>
                      <p><span className="text-gray-500">Amount:</span> £{orderDetail?.order?.pricing?.total_amount || orderDetail?.pricing?.total_amount || orderDetail?.pricing?.amount}</p>
                    </div>
                  </div>
                  
                  {/* Dates */}
                  <div className="space-y-2 mt-4">
                    <h4 className="font-medium flex items-center gap-2">
                      <Calendar className="h-4 w-4" />
                      Dates
                    </h4>
                    <div className="bg-gray-50 rounded-lg p-3 space-y-1 text-sm">
                      <p><span className="text-gray-500">Created:</span> {formatDate(orderDetail?.order?.created_at || orderDetail?.created_at)}</p>
                      <p><span className="text-gray-500">Updated:</span> {formatDate(orderDetail?.order?.updated_at || orderDetail?.updated_at)}</p>
                      {(orderDetail?.order?.completed_at || orderDetail?.completed_at) && (
                        <p><span className="text-gray-500">Completed:</span> {formatDate(orderDetail?.order?.completed_at || orderDetail?.completed_at)}</p>
                      )}
                    </div>
                  </div>
                  
                  {/* Client Input Section */}
                  {(orderDetail?.order?.status || orderDetail?.status) === 'CLIENT_INPUT_REQUIRED' && renderClientInputSection()}
                  
                  {/* Review Actions */}
                  {renderReviewActions()}
                </ScrollArea>
              </TabsContent>
              
              <TabsContent value="documents" className="space-y-4">
                <ScrollArea className="max-h-[50vh]">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h4 className="font-medium">Document Versions</h4>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleGenerateDocuments}
                        disabled={isSubmitting}
                      >
                        <FileText className="h-4 w-4 mr-2" />
                        Generate New
                      </Button>
                    </div>
                    
                    {documentVersions.length === 0 ? (
                      <div className="text-center py-8 text-gray-500">
                        <FileText className="h-12 w-12 mx-auto mb-2 opacity-50" />
                        <p>No documents generated yet</p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {documentVersions.map(renderDocumentVersion)}
                      </div>
                    )}
                    
                    {selectedDocVersion && (
                      <div className="border-t pt-4 space-y-2">
                        <h4 className="font-medium">Selected: v{selectedDocVersion.version}</h4>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setShowDocumentViewer(true)}
                          >
                            <Eye className="h-4 w-4 mr-2" />
                            Preview
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              // Download PDF
                              window.open(
                                `${API_URL}/api/admin/orders/${orderDetail.order_id}/documents/${selectedDocVersion.version}/preview?format=pdf`,
                                '_blank'
                              );
                            }}
                          >
                            <Download className="h-4 w-4 mr-2" />
                            Download PDF
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </TabsContent>
              
              <TabsContent value="timeline">
                <ScrollArea className="max-h-[50vh]">
                  <h4 className="font-medium mb-4 flex items-center gap-2">
                    <History className="h-4 w-4" />
                    Audit Timeline
                  </h4>
                  {renderAuditTimeline()}
                </ScrollArea>
              </TabsContent>
            </Tabs>
            
            <DialogFooter className="flex justify-between">
              <Button
                variant="destructive"
                size="sm"
                onClick={() => {
                  setDeleteReason('');
                  setShowDeleteDialog(true);
                }}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete Order
              </Button>
              <Button variant="outline" onClick={() => setShowDetailDialog(false)}>
                Close
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Approval Modal */}
        <Dialog open={showApproveModal} onOpenChange={setShowApproveModal}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                Approve & Finalize Order
              </DialogTitle>
              <DialogDescription>
                This will lock document v{approveVersion} as the final version and proceed to delivery.
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4">
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex items-center gap-2 text-green-800">
                  <Lock className="h-4 w-4" />
                  <span className="font-medium">Version Locking</span>
                </div>
                <p className="text-sm text-green-700 mt-1">
                  Document v{approveVersion} will be locked as final. No further regeneration or edits 
                  will be allowed unless explicitly reopened.
                </p>
              </div>
              
              <div className="space-y-2">
                <Label>Approval Notes (Optional)</Label>
                <Textarea
                  value={approveNotes}
                  onChange={(e) => setApproveNotes(e.target.value)}
                  placeholder="Any notes for this approval..."
                  rows={3}
                />
              </div>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowApproveModal(false)}>
                Cancel
              </Button>
              <Button
                onClick={submitApproval}
                disabled={isSubmitting}
                className="bg-green-600 hover:bg-green-700"
              >
                {isSubmitting ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : <Check className="h-4 w-4 mr-2" />}
                Approve & Lock v{approveVersion}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Regeneration Modal */}
        <Dialog open={showRegenModal} onOpenChange={setShowRegenModal}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <RotateCcw className="h-5 w-5 text-blue-600" />
                Request Document Regeneration
              </DialogTitle>
              <DialogDescription>
                Provide detailed instructions for regeneration. This is required for audit purposes.
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Reason for Regeneration *</Label>
                <Select value={regenReason} onValueChange={setRegenReason}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a reason..." />
                  </SelectTrigger>
                  <SelectContent>
                    {regenReasons.map(r => (
                      <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label>Correction / Reviewer Notes *</Label>
                <Textarea
                  value={regenNotes}
                  onChange={(e) => setRegenNotes(e.target.value)}
                  placeholder="Describe exactly what needs to be fixed or changed..."
                  rows={4}
                  className="min-h-[100px]"
                />
                <p className="text-xs text-gray-500">
                  Be specific about what to change. These notes will be stored in the audit log.
                </p>
              </div>
              
              <div className="space-y-2">
                <Label>Guardrails (Optional)</Label>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="preserve_names_dates"
                      checked={regenGuardrails.preserve_names_dates}
                      onCheckedChange={(checked) => 
                        setRegenGuardrails(prev => ({...prev, preserve_names_dates: checked}))
                      }
                    />
                    <label htmlFor="preserve_names_dates" className="text-sm">
                      Do not change names, addresses, or dates
                    </label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="preserve_format"
                      checked={regenGuardrails.preserve_format}
                      onCheckedChange={(checked) => 
                        setRegenGuardrails(prev => ({...prev, preserve_format: checked}))
                      }
                    />
                    <label htmlFor="preserve_format" className="text-sm">
                      Keep same tone and format
                    </label>
                  </div>
                </div>
              </div>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowRegenModal(false)}>
                Cancel
              </Button>
              <Button
                onClick={submitRegeneration}
                disabled={isSubmitting || !regenReason || !regenNotes.trim()}
              >
                {isSubmitting ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}
                Request Regeneration
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Request More Info Modal */}
        <Dialog open={showInfoRequestModal} onOpenChange={setShowInfoRequestModal}>
          <DialogContent className="max-w-lg max-h-[90vh]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5 text-blue-600" />
                Request Client Information
              </DialogTitle>
              <DialogDescription>
                The client will receive an email and be asked to provide this information via the portal.
              </DialogDescription>
            </DialogHeader>
            
            <ScrollArea className="max-h-[60vh]">
              <div className="space-y-4 pr-4">
                <div className="space-y-2">
                  <Label>What information do you need? *</Label>
                  <Textarea
                    value={infoRequestNotes}
                    onChange={(e) => setInfoRequestNotes(e.target.value)}
                    placeholder="Describe what information is missing and why it's needed..."
                    rows={4}
                    className="min-h-[100px]"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>Requested Fields (Optional)</Label>
                  <p className="text-xs text-gray-500 mb-2">
                    Select specific fields for the client to fill out
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    {commonRequestedFields.map(field => (
                      <div key={field.id} className="flex items-center gap-2">
                        <Checkbox
                          id={field.id}
                          checked={requestedFields.includes(field.id)}
                          onCheckedChange={() => toggleRequestedField(field.id)}
                        />
                        <label htmlFor={field.id} className="text-sm">
                          {field.label}
                        </label>
                      </div>
                    ))}
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label>Response Deadline (Optional)</Label>
                  <Select value={deadlineDays} onValueChange={setDeadlineDays}>
                    <SelectTrigger>
                      <SelectValue placeholder="No deadline" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No deadline</SelectItem>
                      <SelectItem value="3">3 days</SelectItem>
                      <SelectItem value="5">5 days</SelectItem>
                      <SelectItem value="7">7 days</SelectItem>
                      <SelectItem value="14">14 days</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="request_attachments"
                    checked={requestAttachments}
                    onCheckedChange={setRequestAttachments}
                  />
                  <label htmlFor="request_attachments" className="text-sm">
                    Request file/document uploads
                  </label>
                </div>
                
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                  <div className="flex items-start gap-2">
                    <Info className="h-4 w-4 text-blue-600 mt-0.5" />
                    <div className="text-sm text-blue-800">
                      <p className="font-medium">What happens next:</p>
                      <ul className="list-disc list-inside mt-1 text-xs space-y-1">
                        <li>Order moves to CLIENT_INPUT_REQUIRED</li>
                        <li>SLA timer pauses automatically</li>
                        <li>Client receives branded email with portal link</li>
                        <li>Once client submits, order returns to INTERNAL_REVIEW</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            </ScrollArea>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowInfoRequestModal(false)}>
                Cancel
              </Button>
              <Button
                onClick={submitInfoRequest}
                disabled={isSubmitting || !infoRequestNotes.trim()}
              >
                {isSubmitting ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}
                Send Request to Client
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Document Viewer Modal */}
        <Dialog open={showDocumentViewer} onOpenChange={setShowDocumentViewer}>
          <DialogContent className="max-w-4xl max-h-[90vh]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Document Preview - v{selectedDocVersion?.version}
                {selectedDocVersion?.is_approved && (
                  <Badge className="bg-green-100 text-green-800">
                    <Lock className="h-3 w-3 mr-1" />
                    Approved
                  </Badge>
                )}
              </DialogTitle>
            </DialogHeader>
            
            <div className="border rounded-lg bg-gray-50 p-4 overflow-auto max-h-[60vh]">
              {/* MOCK document preview */}
              <div className="bg-white border shadow-sm p-6 min-h-[400px]">
                <div className="text-center mb-6">
                  <Badge className="bg-yellow-100 text-yellow-800 text-lg px-4 py-2">
                    DRAFT / MOCK DOCUMENT
                  </Badge>
                </div>
                
                <div className="space-y-4 font-mono text-sm">
                  <div className="border-b pb-2">
                    <p className="text-gray-500">Document Type: {selectedDocVersion?.document_type}</p>
                    <p className="text-gray-500">Version: v{selectedDocVersion?.version}</p>
                    <p className="text-gray-500">Generated: {formatDate(selectedDocVersion?.generated_at)}</p>
                    {selectedDocVersion?.is_regeneration && (
                      <p className="text-blue-600">This is a regenerated version</p>
                    )}
                  </div>
                  
                  <div className="bg-gray-100 p-4 rounded">
                    <p className="text-center text-gray-600">
                      [MOCK DOCUMENT CONTENT]
                    </p>
                    <p className="text-center text-gray-500 text-xs mt-2">
                      In production, this would display the actual document content.
                    </p>
                  </div>
                  
                  {selectedDocVersion?.regeneration_notes && (
                    <div className="bg-blue-50 border border-blue-200 rounded p-3">
                      <p className="text-blue-800 font-medium">Regeneration Notes:</p>
                      <p className="text-blue-700 text-sm">{selectedDocVersion.regeneration_notes}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
            
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  window.open(
                    `${API_URL}/api/admin/orders/${orderDetail?.order_id}/documents/${selectedDocVersion?.version}/preview?format=pdf`,
                    '_blank'
                  );
                }}
              >
                <Download className="h-4 w-4 mr-2" />
                Download PDF
              </Button>
              <Button variant="outline" onClick={() => setShowDocumentViewer(false)}>
                Close
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Cancel/Archive Order Dialog */}
        <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="flex items-center gap-2 text-orange-600">
                <Archive className="h-5 w-5" />
                Cancel or Archive Order
              </AlertDialogTitle>
              <AlertDialogDescription>
                Orders are immutable records and cannot be deleted. Choose an action:
              </AlertDialogDescription>
            </AlertDialogHeader>
            
            <div className="space-y-4">
              <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
                <p className="text-sm text-orange-800">
                  <strong>Cancel:</strong> For orders that have not been paid or had documents generated.
                  <br />
                  <strong>Archive:</strong> For completed orders you want to hide from the active pipeline.
                </p>
              </div>
              
              <div className="space-y-2">
                <Label>Reason *</Label>
                <Textarea
                  value={deleteReason}
                  onChange={(e) => setDeleteReason(e.target.value)}
                  placeholder="Explain why this order is being cancelled/archived..."
                  rows={3}
                />
            </div>
            
            <AlertDialogFooter className="flex-col sm:flex-row gap-2">
              <AlertDialogCancel>Close</AlertDialogCancel>
              <Button
                variant="outline"
                onClick={handleCancelOrder}
                disabled={isSubmitting || !deleteReason.trim()}
                className="border-orange-500 text-orange-600 hover:bg-orange-50"
              >
                {isSubmitting ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : <X className="h-4 w-4 mr-2" />}
                Cancel Order
              </Button>
              <Button
                onClick={handleArchiveOrder}
                disabled={isSubmitting || !deleteReason.trim()}
                className="bg-gray-600 hover:bg-gray-700"
              >
                {isSubmitting ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : <Archive className="h-4 w-4 mr-2" />}
                Archive Order
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </AdminLayout>
  );
};

export default AdminOrdersPage;
