/**
 * ActionModals - Modals for order actions (Regeneration, Request Info, Manual Override)
 * 
 * Features:
 * - RegenerationModal: reason dropdown + mandatory notes + guardrails
 * - RequestInfoModal: request notes + field checklist + deadline + email notification
 * - ManualOverrideModal: retry automation / advance stage with mandatory reason
 * - All actions are audited with who, timestamp, reason
 */

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import { Textarea } from '../../ui/textarea';
import { Checkbox } from '../../ui/checkbox';
import { Badge } from '../../ui/badge';
import { ScrollArea } from '../../ui/scroll-area';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../ui/select';
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
import {
  RotateCcw,
  MessageSquare,
  Send,
  RefreshCw,
  AlertTriangle,
  Info,
  Settings,
  Play,
  ArrowRight,
} from 'lucide-react';
import { toast } from 'sonner';

// Regeneration reasons dropdown options
const REGEN_REASONS = [
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
const COMMON_REQUESTED_FIELDS = [
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

// Allowed manual transitions (whitelist)
const ALLOWED_MANUAL_TRANSITIONS = {
  FAILED: ['QUEUED', 'IN_PROGRESS'],
  DELIVERY_FAILED: ['FINALISING', 'DELIVERING'],
  CLIENT_INPUT_REQUIRED: ['INTERNAL_REVIEW'],
  REGEN_REQUESTED: ['INTERNAL_REVIEW'],
};

/**
 * Regeneration Request Modal
 */
export const RegenerationModal = ({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
  currentVersion = null,
}) => {
  const [reason, setReason] = useState('');
  const [notes, setNotes] = useState('');
  const [sections, setSections] = useState([]);
  const [guardrails, setGuardrails] = useState({
    preserve_names_dates: false,
    preserve_format: false,
  });

  const handleSubmit = () => {
    if (!reason) {
      toast.error('Please select a reason for regeneration');
      return;
    }
    if (!notes.trim() || notes.trim().length < 10) {
      toast.error('Correction notes are required (minimum 10 characters)');
      return;
    }

    onSubmit({
      reason,
      correction_notes: notes,
      affected_sections: sections.length > 0 ? sections : null,
      guardrails,
      regenerated_from_version: currentVersion,
    });
  };

  const handleClose = () => {
    setReason('');
    setNotes('');
    setSections([]);
    setGuardrails({ preserve_names_dates: false, preserve_format: false });
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg" data-testid="regeneration-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <RotateCcw className="h-5 w-5 text-blue-600" />
            Request Document Regeneration
          </DialogTitle>
          <DialogDescription>
            A new document version will be generated with your corrections.
            The previous version will be marked as superseded.
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-[60vh]">
          <div className="space-y-4 pr-4">
            {/* Reason dropdown (required) */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">
                Reason for Regeneration <span className="text-red-500">*</span>
              </Label>
              <Select value={reason} onValueChange={setReason}>
                <SelectTrigger data-testid="regen-reason-select">
                  <SelectValue placeholder="Select reason..." />
                </SelectTrigger>
                <SelectContent>
                  {REGEN_REASONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Correction notes (required) */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">
                Correction Notes <span className="text-red-500">*</span>
              </Label>
              <Textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Describe what needs to be changed in detail..."
                rows={4}
                data-testid="regen-notes-input"
              />
              <p className="text-xs text-gray-500">
                Minimum 10 characters. Be specific about required changes.
              </p>
            </div>

            {/* Guardrails */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Guardrails</Label>
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="preserve_names_dates"
                    checked={guardrails.preserve_names_dates}
                    onCheckedChange={(checked) =>
                      setGuardrails((prev) => ({ ...prev, preserve_names_dates: checked }))
                    }
                  />
                  <label htmlFor="preserve_names_dates" className="text-sm">
                    Preserve all names and dates exactly
                  </label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="preserve_format"
                    checked={guardrails.preserve_format}
                    onCheckedChange={(checked) =>
                      setGuardrails((prev) => ({ ...prev, preserve_format: checked }))
                    }
                  />
                  <label htmlFor="preserve_format" className="text-sm">
                    Preserve document structure/format
                  </label>
                </div>
              </div>
            </div>

            {/* Info box */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <Info className="h-4 w-4 text-blue-600 mt-0.5" />
                <div className="text-sm text-blue-800">
                  <p className="font-medium">Stored audit data:</p>
                  <ul className="list-disc list-inside mt-1 text-xs space-y-1">
                    <li>regen_reason: {reason || '(not selected)'}</li>
                    <li>regen_notes: {notes.length > 0 ? `${notes.length} chars` : '(empty)'}</li>
                    <li>regenerated_from_version: v{currentVersion || '?'}</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </ScrollArea>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isSubmitting || !reason || !notes.trim()}
            data-testid="submit-regen-btn"
          >
            {isSubmitting ? (
              <RefreshCw className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <RotateCcw className="h-4 w-4 mr-2" />
            )}
            Request Regeneration
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

/**
 * Request Client Info Modal
 */
export const RequestInfoModal = ({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
}) => {
  const [notes, setNotes] = useState('');
  const [requestedFields, setRequestedFields] = useState([]);
  const [deadlineDays, setDeadlineDays] = useState('');
  const [requestAttachments, setRequestAttachments] = useState(false);

  const toggleField = (fieldId) => {
    setRequestedFields((prev) =>
      prev.includes(fieldId)
        ? prev.filter((f) => f !== fieldId)
        : [...prev, fieldId]
    );
  };

  const handleSubmit = () => {
    if (!notes.trim()) {
      toast.error('Please specify what information you need');
      return;
    }

    onSubmit({
      request_notes: notes,
      requested_fields: requestedFields.length > 0 ? requestedFields : null,
      deadline_days: deadlineDays && deadlineDays !== 'none' ? parseInt(deadlineDays) : null,
      request_attachments: requestAttachments,
    });
  };

  const handleClose = () => {
    setNotes('');
    setRequestedFields([]);
    setDeadlineDays('');
    setRequestAttachments(false);
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg" data-testid="request-info-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-pink-600" />
            Request More Information
          </DialogTitle>
          <DialogDescription>
            The client will receive a branded email with your request.
            Order SLA timer will pause until they respond.
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-[60vh]">
          <div className="space-y-4 pr-4">
            {/* Request notes (required) */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">
                What information do you need? <span className="text-red-500">*</span>
              </Label>
              <Textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Please provide details about what you need from the client..."
                rows={4}
                data-testid="info-request-notes"
              />
            </div>

            {/* Quick field selection */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Quick Select Fields (Optional)</Label>
              <div className="grid grid-cols-2 gap-2">
                {COMMON_REQUESTED_FIELDS.map((field) => (
                  <div key={field.id} className="flex items-center space-x-2">
                    <Checkbox
                      id={field.id}
                      checked={requestedFields.includes(field.id)}
                      onCheckedChange={() => toggleField(field.id)}
                    />
                    <label htmlFor={field.id} className="text-sm cursor-pointer">
                      {field.label}
                    </label>
                  </div>
                ))}
              </div>
            </div>

            {/* Response deadline */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Response Deadline (Optional)</Label>
              <Select value={deadlineDays} onValueChange={setDeadlineDays}>
                <SelectTrigger>
                  <SelectValue placeholder="Select deadline..." />
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

            {/* Request attachments */}
            <div className="flex items-center space-x-2">
              <Checkbox
                id="request_attachments"
                checked={requestAttachments}
                onCheckedChange={setRequestAttachments}
              />
              <label htmlFor="request_attachments" className="text-sm">
                Request file/document uploads
              </label>
            </div>

            {/* Info box */}
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
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isSubmitting || !notes.trim()}
            data-testid="submit-info-request-btn"
          >
            {isSubmitting ? (
              <RefreshCw className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Send className="h-4 w-4 mr-2" />
            )}
            Send Request to Client
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

/**
 * Manual Override Modal - For admin fallback controls
 */
export const ManualOverrideModal = ({
  isOpen,
  onClose,
  onSubmit,
  currentStatus,
  isSubmitting = false,
}) => {
  const [action, setAction] = useState('');
  const [targetStatus, setTargetStatus] = useState('');
  const [reason, setReason] = useState('');

  const allowedTransitions = ALLOWED_MANUAL_TRANSITIONS[currentStatus] || [];

  const handleSubmit = () => {
    if (!reason.trim() || reason.trim().length < 10) {
      toast.error('Mandatory reason required (minimum 10 characters)');
      return;
    }

    if (action === 'advance' && !targetStatus) {
      toast.error('Please select target status');
      return;
    }

    onSubmit({
      action,
      target_status: action === 'advance' ? targetStatus : null,
      reason: reason.trim(),
      from_status: currentStatus,
    });
  };

  const handleClose = () => {
    setAction('');
    setTargetStatus('');
    setReason('');
    onClose();
  };

  return (
    <AlertDialog open={isOpen} onOpenChange={handleClose}>
      <AlertDialogContent data-testid="manual-override-modal">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2 text-orange-600">
            <Settings className="h-5 w-5" />
            Manual Override Controls
          </AlertDialogTitle>
          <AlertDialogDescription>
            Use these controls only when automation has stalled.
            All overrides are logged with full audit trail.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="space-y-4">
          {/* Warning */}
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-orange-600 mt-0.5" />
              <div className="text-sm text-orange-800">
                <p className="font-medium">Enterprise Audit Trail</p>
                <p className="text-xs mt-1">
                  This action will be recorded with: who, timestamp, from_state,
                  to_state, and mandatory reason.
                </p>
              </div>
            </div>
          </div>

          {/* Action selection */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">Action</Label>
            <Select value={action} onValueChange={setAction}>
              <SelectTrigger>
                <SelectValue placeholder="Select action..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="retry">
                  <div className="flex items-center gap-2">
                    <Play className="h-4 w-4" />
                    Retry automation step
                  </div>
                </SelectItem>
                {allowedTransitions.length > 0 && (
                  <SelectItem value="advance">
                    <div className="flex items-center gap-2">
                      <ArrowRight className="h-4 w-4" />
                      Advance to next stage (manual override)
                    </div>
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
          </div>

          {/* Target status (only for advance action) */}
          {action === 'advance' && allowedTransitions.length > 0 && (
            <div className="space-y-2">
              <Label className="text-sm font-medium">Target Status</Label>
              <Select value={targetStatus} onValueChange={setTargetStatus}>
                <SelectTrigger>
                  <SelectValue placeholder="Select target status..." />
                </SelectTrigger>
                <SelectContent>
                  {allowedTransitions.map((status) => (
                    <SelectItem key={status} value={status}>
                      {status.replace(/_/g, ' ')}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-gray-500">
                Only whitelisted safe transitions are allowed.
              </p>
            </div>
          )}

          {/* Mandatory reason */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">
              Mandatory Reason <span className="text-red-500">*</span>
            </Label>
            <Textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Explain why this manual override is necessary..."
              rows={3}
              data-testid="override-reason-input"
            />
            <p className="text-xs text-gray-500">
              Minimum 10 characters. This will be stored in the audit log.
            </p>
          </div>
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <Button
            onClick={handleSubmit}
            disabled={isSubmitting || !action || !reason.trim()}
            className="bg-orange-600 hover:bg-orange-700"
            data-testid="submit-override-btn"
          >
            {isSubmitting ? (
              <RefreshCw className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Settings className="h-4 w-4 mr-2" />
            )}
            Execute Override
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};

export default { RegenerationModal, RequestInfoModal, ManualOverrideModal };
