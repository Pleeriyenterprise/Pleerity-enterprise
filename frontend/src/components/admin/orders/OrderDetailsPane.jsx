/**
 * OrderDetailsPane - Comprehensive order detail view
 * 
 * Features:
 * - Full order information display
 * - Intake data view
 * - Document versions management
 * - Review actions (INTERNAL_REVIEW specific)
 * - Client input request/response display
 * - Audit timeline integration
 * - Admin actions (priority, notes, cancel/archive)
 */

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { Badge } from '../../ui/badge';
import { Label } from '../../ui/label';
import { Separator } from '../../ui/separator';
import { ScrollArea } from '../../ui/scroll-area';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../../ui/tabs';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../../ui/tooltip';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../../ui/alert-dialog';
import { Textarea } from '../../ui/textarea';
import {
  FileText,
  User,
  Package,
  Clock,
  Flag,
  Zap,
  Eye,
  Lock,
  Unlock,
  CheckCircle2,
  RotateCcw,
  MessageSquare,
  RefreshCw,
  Archive,
  X,
  Settings,
  AlertTriangle,
  Download,
  Copy,
} from 'lucide-react';
import { cn } from '../../../lib/utils';
import { toast } from 'sonner';
import { formatPriceShort } from '../../../api/ordersApi';
import { AuditTimeline } from './AuditTimeline';
import { STATUS_COLORS, formatDate } from './OrderList';

/**
 * Order info section
 */
const OrderInfoSection = ({ order }) => {
  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied`);
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        {/* Order ID */}
        <div>
          <Label className="text-xs text-gray-500">Order ID</Label>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm">{order.order_id}</span>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={() => copyToClipboard(order.order_id, 'Order ID')}
            >
              <Copy className="h-3 w-3" />
            </Button>
          </div>
        </div>

        {/* Status */}
        <div>
          <Label className="text-xs text-gray-500">Status</Label>
          <Badge className={cn('text-xs', STATUS_COLORS[order.status])}>
            {order.status?.replace(/_/g, ' ')}
          </Badge>
        </div>

        {/* Service */}
        <div>
          <Label className="text-xs text-gray-500">Service</Label>
          <p className="text-sm">{order.service_name || order.service_code}</p>
        </div>

        {/* Category */}
        <div>
          <Label className="text-xs text-gray-500">Category</Label>
          <p className="text-sm">{order.service_category || '-'}</p>
        </div>

        {/* Created */}
        <div>
          <Label className="text-xs text-gray-500">Created</Label>
          <p className="text-sm">{formatDate(order.created_at)}</p>
        </div>

        {/* Updated */}
        <div>
          <Label className="text-xs text-gray-500">Last Updated</Label>
          <p className="text-sm">{formatDate(order.updated_at)}</p>
        </div>

        {/* Amount */}
        <div>
          <Label className="text-xs text-gray-500">Total Amount</Label>
          <p className="text-sm font-medium">{formatPriceShort(order.total_amount || order.pricing?.total_price_pence || order.pricing_snapshot?.total_price_pence || 0)}</p>
        </div>

        {/* Payment Status */}
        <div>
          <Label className="text-xs text-gray-500">Payment</Label>
          <Badge
            variant="outline"
            className={cn(
              'text-xs',
              (order.stripe_payment_status || order.payment_status) === 'paid'
                ? 'border-green-500 text-green-700'
                : 'border-gray-300'
            )}
          >
            {order.stripe_payment_status || order.payment_status || (order.paid_at ? 'paid' : 'pending')}
          </Badge>
        </div>
      </div>

      {/* Flags */}
      <div className="flex flex-wrap gap-2">
        {order.priority && (
          <Badge className="bg-orange-100 text-orange-800">
            <Flag className="h-3 w-3 mr-1" />
            Priority
          </Badge>
        )}
        {order.fast_track && (
          <Badge className="bg-purple-100 text-purple-800 animate-pulse">
            <Zap className="h-3 w-3 mr-1" />
            Fast Track
          </Badge>
        )}
        {order.requires_postal_delivery && (
          <Badge className="bg-cyan-100 text-cyan-800">
            <Package className="h-3 w-3 mr-1" />
            Printed Copy
          </Badge>
        )}
        {order.version_locked && (
          <Badge className="bg-green-100 text-green-800">
            <Lock className="h-3 w-3 mr-1" />
            Version Locked
          </Badge>
        )}
        {order.is_archived && (
          <Badge variant="secondary">
            <Archive className="h-3 w-3 mr-1" />
            Archived
          </Badge>
        )}
      </div>
      
      {/* Postal Delivery Section */}
      {order.requires_postal_delivery && (
        <div className="mt-3 p-3 bg-cyan-50 rounded-lg border border-cyan-200">
          <div className="flex items-center gap-2 mb-2">
            <Package className="h-4 w-4 text-cyan-600" />
            <span className="font-medium text-cyan-800">Postal Delivery</span>
            <Badge className={`text-xs ${
              order.postal_status === 'DELIVERED' ? 'bg-green-100 text-green-800' :
              order.postal_status === 'DISPATCHED' ? 'bg-blue-100 text-blue-800' :
              order.postal_status === 'PRINTED' ? 'bg-yellow-100 text-yellow-800' :
              'bg-gray-100 text-gray-800'
            }`}>
              {order.postal_status || 'PENDING_PRINT'}
            </Badge>
          </div>
          {order.postal_tracking_number && (
            <p className="text-sm text-cyan-700">
              Tracking: <span className="font-mono">{order.postal_tracking_number}</span>
              {order.postal_carrier && ` (${order.postal_carrier})`}
            </p>
          )}
          {order.postal_delivery_address && (
            <p className="text-sm text-gray-600 mt-1">
              📍 {order.postal_delivery_address}
            </p>
          )}
        </div>
      )}
    </div>
  );
};

/**
 * Customer info section
 */
const CustomerInfoSection = ({ customer }) => {
  if (!customer) return <p className="text-sm text-gray-500">No customer data</p>;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 mb-2">
        <User className="h-4 w-4 text-gray-500" />
        <span className="font-medium">{customer.full_name || 'Unknown'}</span>
      </div>
      
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <Label className="text-xs text-gray-500">Email</Label>
          <p>{customer.email || '-'}</p>
        </div>
        <div>
          <Label className="text-xs text-gray-500">Phone</Label>
          <p>{customer.phone || '-'}</p>
        </div>
      </div>
    </div>
  );
};

/**
 * Intake data viewer
 */
const IntakeDataSection = ({ intakeData }) => {
  if (!intakeData || Object.keys(intakeData).length === 0) {
    return <p className="text-sm text-gray-500">No intake data available</p>;
  }

  return (
    <div className="space-y-2">
      {Object.entries(intakeData).map(([key, value]) => {
        // Skip internal fields
        if (key.startsWith('_')) return null;
        
        return (
          <div key={key} className="flex justify-between py-1 border-b border-gray-100">
            <span className="text-sm text-gray-600">
              {key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
            </span>
            <span className="text-sm font-medium">
              {typeof value === 'object' ? JSON.stringify(value) : String(value)}
            </span>
          </div>
        );
      })}
    </div>
  );
};

/**
 * Client input request/response display
 */
const ClientInputSection = ({ order }) => {
  const request = order?.client_input_request;
  const responses = order?.client_input_responses || [];

  if (!request) return null;

  return (
    <div className="space-y-4 border-t pt-4 mt-4">
      <h4 className="font-medium flex items-center gap-2">
        <MessageSquare className="h-4 w-4" />
        Client Input Request
      </h4>

      {/* Request details */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
        <p className="text-sm font-medium text-yellow-800">What we requested:</p>
        <p className="text-sm mt-1 whitespace-pre-wrap">{request.request_notes}</p>
        {request.requested_fields?.length > 0 && (
          <div className="mt-2">
            <p className="text-xs font-medium text-yellow-700">Requested fields:</p>
            <div className="flex flex-wrap gap-1 mt-1">
              {request.requested_fields.map((f) => (
                <Badge key={f} variant="outline" className="text-xs">
                  {f}
                </Badge>
              ))}
            </div>
          </div>
        )}
        <p className="text-xs text-yellow-600 mt-2">
          Requested: {formatDate(request.requested_at)} by {request.requested_by_admin_email}
        </p>
      </div>

      {/* Responses */}
      {responses.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium">Client Responses:</p>
          {responses.map((resp, idx) => (
            <div key={idx} className="bg-green-50 border border-green-200 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <Badge variant="outline" className="text-xs">
                  Response v{resp.version}
                </Badge>
                <span className="text-xs text-gray-500">
                  {formatDate(resp.submitted_at)}
                </span>
              </div>
              <div className="space-y-1">
                {Object.entries(resp.payload || {}).map(([key, value]) => (
                  <div key={key} className="flex">
                    <span className="text-xs font-medium w-32 text-gray-600">
                      {key.replace(/_/g, ' ')}:
                    </span>
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

/**
 * Document versions section (for review)
 */
const DocumentVersionsSection = ({
  versions,
  selectedVersion,
  onVersionSelect,
  onPreview,
  isLocked,
}) => {
  if (!versions || versions.length === 0) {
    return (
      <div className="text-center py-8">
        <FileText className="h-8 w-8 mx-auto mb-2 text-gray-300" />
        <p className="text-sm text-gray-500">No documents generated yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {versions.map((v) => (
        <div
          key={v.version}
          onClick={() => onVersionSelect(v)}
          className={cn(
            'p-3 rounded-lg border cursor-pointer transition-all',
            selectedVersion?.version === v.version
              ? 'border-blue-500 bg-blue-50'
              : 'border-gray-200 hover:border-gray-300',
            v.is_approved && 'ring-2 ring-green-500',
            v.status === 'SUPERSEDED' && 'opacity-60'
          )}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-gray-500" />
              <span className="font-medium">v{v.version}</span>
              <Badge
                className={cn(
                  'text-xs',
                  v.status === 'FINAL' && 'bg-green-100 text-green-800',
                  v.status === 'DRAFT' && 'bg-amber-100 text-amber-800',
                  v.status === 'REGENERATED' && 'bg-blue-100 text-blue-800',
                  v.status === 'SUPERSEDED' && 'bg-gray-100 text-gray-600'
                )}
              >
                {v.status}
              </Badge>
              {v.is_approved && (
                <Badge className="bg-green-100 text-green-800 text-xs">
                  <Lock className="h-3 w-3 mr-1" />
                  Approved
                </Badge>
              )}
            </div>
            <span className="text-xs text-gray-500">
              {formatDate(v.generated_at || v.created_at)}
            </span>
          </div>

          {/* File badges */}
          <div className="flex items-center gap-2 mt-2">
            {v.filename_docx && (
              <Badge variant="outline" className="text-xs bg-blue-50 border-blue-200">
                <FileText className="h-3 w-3 mr-1" />
                DOCX
              </Badge>
            )}
            {v.filename_pdf && (
              <Badge variant="outline" className="text-xs bg-red-50 border-red-200">
                <FileText className="h-3 w-3 mr-1" />
                PDF
              </Badge>
            )}
          </div>

          {v.regeneration_notes && (
            <p className="text-xs text-gray-500 mt-2 line-clamp-2">
              Notes: {v.regeneration_notes}
            </p>
          )}
        </div>
      ))}

      {/* Preview button */}
      {selectedVersion && (
        <Button
          variant="outline"
          className="w-full"
          onClick={() => onPreview(selectedVersion)}
        >
          <Eye className="h-4 w-4 mr-2" />
          Preview v{selectedVersion.version}
        </Button>
      )}
    </div>
  );
};

/**
 * Review actions section (INTERNAL_REVIEW specific)
 */
const ReviewActionsSection = ({
  order,
  documentVersions,
  selectedVersion,
  onApprove,
  onRequestRegen,
  onRequestInfo,
  onGenerateDocuments,
  isSubmitting,
}) => {
  const status = order?.status;
  if (status !== 'INTERNAL_REVIEW') return null;

  const isLocked = order?.version_locked;
  const hasDocuments = documentVersions && documentVersions.length > 0;

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
          <p className="text-sm text-gray-500 mb-1">No documents generated yet</p>
          <Button
            onClick={onGenerateDocuments}
            disabled={isSubmitting}
            size="sm"
            data-testid="generate-draft-btn"
          >
            {isSubmitting ? (
              <RefreshCw className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <FileText className="h-4 w-4 mr-2" />
            )}
            Generate Draft
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-2">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  onClick={onApprove}
                  disabled={isLocked || isSubmitting}
                  className="bg-green-600 hover:bg-green-700"
                  data-testid="approve-finalize-btn"
                >
                  <CheckCircle2 className="h-4 w-4 mr-2" />
                  Approve & Finalize
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                Lock document as FINAL, move order to delivery stage
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  onClick={onRequestRegen}
                  disabled={isLocked || isSubmitting}
                  data-testid="request-regen-btn"
                >
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Request Revision
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                Create new document version with changes
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  onClick={onRequestInfo}
                  disabled={isSubmitting}
                  data-testid="request-info-btn"
                >
                  <MessageSquare className="h-4 w-4 mr-2" />
                  Request Client Info
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                Pause workflow, send email to client
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      )}
    </div>
  );
};

/**
 * Main OrderDetailsPane component
 */
const OrderDetailsPane = ({
  isOpen,
  onClose,
  order,
  timeline = [],
  documentVersions = [],
  allowedTransitions = [],
  adminActions = null,
  isLocked = false,
  onApprove,
  onRequestRegen,
  onRequestInfo,
  onGenerateDocuments,
  onOpenDocumentPreview,
  onOpenManualOverride,
  onPriorityToggle,
  onCancel,
  onArchive,
  isSubmitting = false,
}) => {
  const [activeTab, setActiveTab] = useState('details');
  const [selectedDocVersion, setSelectedDocVersion] = useState(null);
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [cancelReason, setCancelReason] = useState('');

  // Auto-select latest version when versions change
  const latestVersion = documentVersions.length > 0 
    ? documentVersions[documentVersions.length - 1] 
    : null;
  
  // Use derived state instead of useEffect with setState
  const currentDocVersion = selectedDocVersion || latestVersion;

  if (!order) return null;

  const handleDocumentClick = (version) => {
    const docVersion = documentVersions.find((v) => v.version === version);
    if (docVersion) {
      setSelectedDocVersion(docVersion);
      onOpenDocumentPreview(docVersion);
    }
  };

  return (
    <>
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="max-w-4xl max-h-[90vh]" data-testid="order-details-pane">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              Order Details
              <span className="font-mono text-gray-500">{order.order_id}</span>
              <Badge className={cn('text-xs ml-2', STATUS_COLORS[order.status])}>
                {order.status?.replace(/_/g, ' ')}
              </Badge>
            </DialogTitle>
          </DialogHeader>

          <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="details">Details</TabsTrigger>
              <TabsTrigger value="documents">Documents</TabsTrigger>
              <TabsTrigger value="timeline">Timeline</TabsTrigger>
              <TabsTrigger value="actions">Actions</TabsTrigger>
            </TabsList>

            <ScrollArea className="h-[60vh] mt-4">
              {/* Details Tab */}
              <TabsContent value="details" className="space-y-6 pr-4">
                <OrderInfoSection order={order} />
                <Separator />
                <CustomerInfoSection customer={order.customer} />
                <Separator />
                <div>
                  <h4 className="font-medium mb-2">Intake Data</h4>
                  <IntakeDataSection intakeData={order.intake_data} />
                </div>
                <ClientInputSection order={order} />
              </TabsContent>

              {/* Documents Tab */}
              <TabsContent value="documents" className="space-y-4 pr-4">
                <DocumentVersionsSection
                  versions={documentVersions}
                  selectedVersion={currentDocVersion}
                  onVersionSelect={setSelectedDocVersion}
                  onPreview={onOpenDocumentPreview}
                  isLocked={isLocked}
                />
                <ReviewActionsSection
                  order={order}
                  documentVersions={documentVersions}
                  selectedVersion={currentDocVersion}
                  onApprove={() => onApprove(currentDocVersion)}
                  onRequestRegen={onRequestRegen}
                  onRequestInfo={onRequestInfo}
                  onGenerateDocuments={onGenerateDocuments}
                  isSubmitting={isSubmitting}
                />
              </TabsContent>

              {/* Timeline Tab */}
              <TabsContent value="timeline" className="pr-4">
                <AuditTimeline
                  timeline={timeline}
                  onDocumentClick={handleDocumentClick}
                  maxHeight="55vh"
                />
              </TabsContent>

              {/* Actions Tab */}
              <TabsContent value="actions" className="space-y-4 pr-4">
                {/* Priority */}
                <div className="flex items-center justify-between p-3 border rounded-lg">
                  <div>
                    <Label className="font-medium">Priority Flag</Label>
                    <p className="text-sm text-gray-500">
                      Mark as priority for faster processing
                    </p>
                  </div>
                  <Button
                    variant={order.priority ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => onPriorityToggle(!order.priority)}
                    disabled={isSubmitting}
                  >
                    <Flag className="h-4 w-4 mr-1" />
                    {order.priority ? 'Remove Priority' : 'Set Priority'}
                  </Button>
                </div>

                {/* Manual Override (for failed/stalled states) */}
                {['FAILED', 'DELIVERY_FAILED', 'CLIENT_INPUT_REQUIRED', 'REGEN_REQUESTED'].includes(
                  order.status
                ) && (
                  <div className="flex items-center justify-between p-3 border border-orange-200 bg-orange-50 rounded-lg">
                    <div>
                      <Label className="font-medium text-orange-800">Manual Override</Label>
                      <p className="text-sm text-orange-600">
                        Use when automation has stalled
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={onOpenManualOverride}
                      className="border-orange-500 text-orange-600 hover:bg-orange-100"
                      disabled={isSubmitting}
                    >
                      <Settings className="h-4 w-4 mr-1" />
                      Override Controls
                    </Button>
                  </div>
                )}

                <Separator />

                {/* Cancel/Archive */}
                <div className="space-y-2">
                  <Label className="text-sm text-gray-500">Danger Zone</Label>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowCancelDialog(true)}
                      className="border-red-300 text-red-600 hover:bg-red-50"
                      disabled={isSubmitting}
                    >
                      <X className="h-4 w-4 mr-1" />
                      Cancel Order
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onArchive()}
                      className="border-gray-300 text-gray-600"
                      disabled={isSubmitting}
                    >
                      <Archive className="h-4 w-4 mr-1" />
                      Archive Order
                    </Button>
                  </div>
                </div>
              </TabsContent>
            </ScrollArea>
          </Tabs>
        </DialogContent>
      </Dialog>

      {/* Cancel Dialog */}
      <AlertDialog open={showCancelDialog} onOpenChange={setShowCancelDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2 text-red-600">
              <AlertTriangle className="h-5 w-5" />
              Cancel Order
            </AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. The order will be marked as cancelled
              but will remain in the system for audit purposes.
            </AlertDialogDescription>
          </AlertDialogHeader>

          <div className="space-y-2">
            <Label>Reason (required)</Label>
            <Textarea
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="Why is this order being cancelled?"
              rows={3}
            />
          </div>

          <AlertDialogFooter>
            <AlertDialogCancel>Go Back</AlertDialogCancel>
            <Button
              variant="destructive"
              onClick={() => {
                if (!cancelReason.trim()) {
                  toast.error('Reason is required');
                  return;
                }
                onCancel(cancelReason);
                setShowCancelDialog(false);
                setCancelReason('');
              }}
              disabled={!cancelReason.trim() || isSubmitting}
            >
              Cancel Order
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};

export {
  OrderDetailsPane,
  OrderInfoSection,
  CustomerInfoSection,
  IntakeDataSection,
  ClientInputSection,
  DocumentVersionsSection,
  ReviewActionsSection,
};
export default OrderDetailsPane;
