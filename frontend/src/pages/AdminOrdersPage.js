/**
 * AdminOrdersPage - Enterprise-grade Order Management & Workflow System
 * 
 * Refactored to use modular components:
 * - OrderPipelineView: Clickable pipeline stages with live counts
 * - OrderList: Filtered order list with sorting
 * - OrderDetailsPane: Full order details with tabs
 * - DocumentPreviewModal: Document viewer with metadata
 * - ActionModals: Regeneration, Request Info, Manual Override
 * - AuditTimeline: Audit trail display
 * 
 * All API calls centralized in ordersApi.js
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import AdminLayout from '../components/admin/AdminLayout';
import { toast } from 'sonner';

// Import modular components
import {
  OrderPipelineView,
  PIPELINE_COLUMNS,
  OrderList,
  STATUS_COLORS,
  formatDate,
  DocumentPreviewModal,
  RegenerationModal,
  RequestInfoModal,
  ManualOverrideModal,
  OrderDetailsPane,
} from '../components/admin/orders';

// Import API client
import { ordersApi } from '../api/ordersApi';

// Import UI components
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '../components/ui/dialog';
import { ScrollArea } from '../components/ui/scroll-area';

// Auto-refresh interval (ms) - 15 seconds
const AUTO_REFRESH_INTERVAL = 15000;

const AdminOrdersPage = () => {
  // ============================================
  // STATE
  // ============================================
  
  // Data state
  const [orders, setOrders] = useState([]);
  const [counts, setCounts] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  
  // Selection state
  const [selectedStage, setSelectedStage] = useState(null);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [orderDetail, setOrderDetail] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [documentVersions, setDocumentVersions] = useState([]);
  const [selectedDocVersion, setSelectedDocVersion] = useState(null);
  const [allowedTransitions, setAllowedTransitions] = useState([]);
  const [adminActions, setAdminActions] = useState(null);
  
  // Dialog states
  const [showStageDialog, setShowStageDialog] = useState(false);
  const [showDetailDialog, setShowDetailDialog] = useState(false);
  const [showDocumentPreview, setShowDocumentPreview] = useState(false);
  const [showRegenModal, setShowRegenModal] = useState(false);
  const [showInfoRequestModal, setShowInfoRequestModal] = useState(false);
  const [showManualOverrideModal, setShowManualOverrideModal] = useState(false);
  
  // Sorting and search
  const [sortBy, setSortBy] = useState('priority');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Action state
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Auto-refresh
  const [autoRefresh, setAutoRefresh] = useState(true);
  const refreshIntervalRef = useRef(null);

  // ============================================
  // DATA FETCHING
  // ============================================
  
  /**
   * Fetch orders for pipeline view
   */
  const fetchOrders = useCallback(async (showLoading = true) => {
    if (showLoading) setIsLoading(true);
    try {
      const data = await ordersApi.getPipeline();
      setOrders(data.orders || []);
      setCounts(data.counts || {});
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Failed to fetch orders:', error);
      if (showLoading) toast.error('Failed to load orders');
    } finally {
      if (showLoading) setIsLoading(false);
    }
  }, []);

  /**
   * Fetch order detail with timeline and documents
   */
  const fetchOrderDetail = useCallback(async (orderId) => {
    try {
      // Fetch order detail and documents in parallel
      const [detailData, docsData] = await Promise.all([
        ordersApi.getOrderDetail(orderId),
        ordersApi.getDocumentVersions(orderId),
      ]);
      
      setOrderDetail(detailData.order);
      setTimeline(detailData.timeline || []);
      setAllowedTransitions(detailData.allowed_transitions || []);
      setAdminActions(detailData.admin_actions);
      
      // Set document versions
      const versions = docsData.versions || [];
      setDocumentVersions(versions);
      
      // Select latest version
      if (versions.length > 0) {
        setSelectedDocVersion(versions[versions.length - 1]);
      } else {
        setSelectedDocVersion(null);
      }
      
      setShowDetailDialog(true);
    } catch (error) {
      console.error('Failed to fetch order detail:', error);
      toast.error('Failed to load order details');
    }
  }, []);

  // ============================================
  // EFFECTS
  // ============================================
  
  // Initial load
  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  // Auto-refresh
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

  // ============================================
  // EVENT HANDLERS
  // ============================================
  
  /**
   * Handle pipeline stage click
   */
  const handleStageClick = (status) => {
    setSelectedStage(status);
    setShowStageDialog(true);
  };

  /**
   * Handle order click from list
   */
  const handleOrderClick = (order) => {
    setSelectedOrder(order);
    fetchOrderDetail(order.order_id);
    setShowStageDialog(false);
  };

  /**
   * Handle document preview
   */
  const handleOpenDocumentPreview = (version) => {
    setSelectedDocVersion(version);
    setShowDocumentPreview(true);
  };

  /**
   * Get orders for a specific status
   */
  const getOrdersForStatus = (status) => {
    return orders.filter((o) => o.status === status);
  };

  /**
   * Get stage name from status
   */
  const getStageName = (status) => {
    const column = PIPELINE_COLUMNS.find((c) => c.status === status);
    return column?.label || status;
  };

  // ============================================
  // ACTION HANDLERS
  // ============================================
  
  /**
   * Handle approve action
   */
  const handleApprove = async (version) => {
    if (!version) {
      toast.error('Please select a document version to approve');
      return;
    }
    
    setIsSubmitting(true);
    try {
      await ordersApi.approveOrder(
        selectedOrder.order_id,
        version.version,
        null
      );
      toast.success(`Order approved! Document v${version.version} locked as final.`);
      setShowDocumentPreview(false);
      setShowDetailDialog(false);
      fetchOrders();
    } catch (error) {
      toast.error(error.message || 'Failed to approve order');
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Handle regeneration request
   */
  const handleRegenerationSubmit = async (data) => {
    setIsSubmitting(true);
    try {
      await ordersApi.requestRegeneration(
        selectedOrder.order_id,
        data.reason,
        data.correction_notes,
        data.affected_sections,
        data.guardrails
      );
      toast.success('Regeneration requested. System will regenerate automatically.');
      setShowRegenModal(false);
      setShowDocumentPreview(false);
      setShowDetailDialog(false);
      fetchOrders();
    } catch (error) {
      toast.error(error.message || 'Failed to request regeneration');
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Handle client info request
   */
  const handleInfoRequestSubmit = async (data) => {
    setIsSubmitting(true);
    try {
      await ordersApi.requestClientInfo(
        selectedOrder.order_id,
        data.request_notes,
        data.requested_fields,
        data.deadline_days,
        data.request_attachments
      );
      toast.success('Info request sent to client. SLA paused.');
      setShowInfoRequestModal(false);
      setShowDocumentPreview(false);
      setShowDetailDialog(false);
      fetchOrders();
    } catch (error) {
      toast.error(error.message || 'Failed to send info request');
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Handle document generation
   */
  const handleGenerateDocuments = async () => {
    setIsSubmitting(true);
    try {
      const result = await ordersApi.generateDocuments(selectedOrder.order_id);
      toast.success(`Document v${result.version?.version || 1} generated`);
      // Refresh order details
      await fetchOrderDetail(selectedOrder.order_id);
    } catch (error) {
      toast.error(error.message || 'Failed to generate documents');
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Handle priority toggle
   */
  const handlePriorityToggle = async (priority) => {
    setIsSubmitting(true);
    try {
      await ordersApi.setPriority(selectedOrder.order_id, priority);
      toast.success(`Priority ${priority ? 'set' : 'removed'}`);
      fetchOrders();
      // Update local state
      setOrderDetail((prev) => ({ ...prev, priority }));
    } catch (error) {
      toast.error(error.message || 'Failed to update priority');
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Handle cancel order
   */
  const handleCancelOrder = async (reason) => {
    setIsSubmitting(true);
    try {
      await ordersApi.cancelOrder(selectedOrder.order_id, reason);
      toast.success('Order cancelled');
      setShowDetailDialog(false);
      fetchOrders();
    } catch (error) {
      toast.error(error.message || 'Failed to cancel order');
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Handle archive order
   */
  const handleArchiveOrder = async () => {
    const reason = window.prompt('Enter reason for archiving:');
    if (!reason) return;
    
    setIsSubmitting(true);
    try {
      await ordersApi.archiveOrder(selectedOrder.order_id, reason);
      toast.success('Order archived');
      setShowDetailDialog(false);
      fetchOrders();
    } catch (error) {
      toast.error(error.message || 'Failed to archive order');
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Handle manual override
   */
  const handleManualOverrideSubmit = async (data) => {
    setIsSubmitting(true);
    try {
      if (data.action === 'retry') {
        // Retry automation - trigger document generation again
        await ordersApi.generateDocuments(selectedOrder.order_id);
        toast.success('Automation retry triggered');
      } else if (data.action === 'advance') {
        // Manual advance to target status
        await ordersApi.transitionOrder(
          selectedOrder.order_id,
          data.target_status,
          `[MANUAL OVERRIDE] ${data.reason}`
        );
        toast.success(`Order advanced to ${data.target_status}`);
      }
      setShowManualOverrideModal(false);
      setShowDetailDialog(false);
      fetchOrders();
    } catch (error) {
      toast.error(error.message || 'Override failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ============================================
  // RENDER
  // ============================================
  
  return (
    <AdminLayout>
      <div className="space-y-6" data-testid="admin-orders-page">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Orders Pipeline</h1>
          <p className="text-gray-500 text-sm">
            Enterprise-grade order management and workflow control
          </p>
        </div>

        {/* Pipeline View */}
        <OrderPipelineView
          counts={counts}
          selectedStage={selectedStage}
          onStageClick={handleStageClick}
          lastUpdated={lastUpdated}
          autoRefresh={autoRefresh}
          onAutoRefreshToggle={() => setAutoRefresh(!autoRefresh)}
          onRefresh={() => fetchOrders()}
          isLoading={isLoading}
        />

        {/* Stage Orders Dialog */}
        <Dialog open={showStageDialog} onOpenChange={setShowStageDialog}>
          <DialogContent className="max-w-2xl max-h-[80vh]">
            <DialogHeader>
              <DialogTitle>
                {getStageName(selectedStage)} Orders
              </DialogTitle>
              <DialogDescription>
                {counts[selectedStage] || 0} orders in this stage
              </DialogDescription>
            </DialogHeader>
            <ScrollArea className="max-h-[60vh]">
              <OrderList
                orders={getOrdersForStatus(selectedStage)}
                selectedStage={selectedStage}
                stageName={getStageName(selectedStage)}
                sortBy={sortBy}
                onSortChange={setSortBy}
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
                onOrderClick={handleOrderClick}
              />
            </ScrollArea>
          </DialogContent>
        </Dialog>

        {/* Order Details Pane */}
        <OrderDetailsPane
          isOpen={showDetailDialog}
          onClose={() => setShowDetailDialog(false)}
          order={orderDetail}
          timeline={timeline}
          documentVersions={documentVersions}
          allowedTransitions={allowedTransitions}
          adminActions={adminActions}
          isLocked={orderDetail?.version_locked}
          onApprove={handleApprove}
          onRequestRegen={() => setShowRegenModal(true)}
          onRequestInfo={() => setShowInfoRequestModal(true)}
          onGenerateDocuments={handleGenerateDocuments}
          onOpenDocumentPreview={handleOpenDocumentPreview}
          onOpenManualOverride={() => setShowManualOverrideModal(true)}
          onPriorityToggle={handlePriorityToggle}
          onCancel={handleCancelOrder}
          onArchive={handleArchiveOrder}
          isSubmitting={isSubmitting}
        />

        {/* Document Preview Modal */}
        <DocumentPreviewModal
          isOpen={showDocumentPreview}
          onClose={() => setShowDocumentPreview(false)}
          orderId={selectedOrder?.order_id}
          serviceCode={selectedOrder?.service_code}
          versions={documentVersions}
          selectedVersion={selectedDocVersion}
          onVersionSelect={setSelectedDocVersion}
          onApprove={handleApprove}
          onRequestRegen={() => {
            setShowDocumentPreview(false);
            setShowRegenModal(true);
          }}
          onRequestInfo={() => {
            setShowDocumentPreview(false);
            setShowInfoRequestModal(true);
          }}
          isSubmitting={isSubmitting}
          isLocked={orderDetail?.version_locked}
        />

        {/* Regeneration Modal */}
        <RegenerationModal
          isOpen={showRegenModal}
          onClose={() => setShowRegenModal(false)}
          onSubmit={handleRegenerationSubmit}
          isSubmitting={isSubmitting}
          currentVersion={selectedDocVersion?.version}
        />

        {/* Request Info Modal */}
        <RequestInfoModal
          isOpen={showInfoRequestModal}
          onClose={() => setShowInfoRequestModal(false)}
          onSubmit={handleInfoRequestSubmit}
          isSubmitting={isSubmitting}
        />

        {/* Manual Override Modal */}
        <ManualOverrideModal
          isOpen={showManualOverrideModal}
          onClose={() => setShowManualOverrideModal(false)}
          onSubmit={handleManualOverrideSubmit}
          currentStatus={orderDetail?.status}
          isSubmitting={isSubmitting}
        />
      </div>
    </AdminLayout>
  );
};

export default AdminOrdersPage;
