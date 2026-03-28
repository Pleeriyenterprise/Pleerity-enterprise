/**
 * Secure job link page: contractor interacts with a single work order via token (no login).
 * Token is in URL ?token=... from assignment email.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  createJobLinkAPI,
  openBlobApiResponse,
  contractorEvidenceFilenameFromKey,
  isContractorFileEvidenceKey,
} from '../../api/client';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Wrench, Loader2, X, FileText, CheckCircle, XCircle, AlertCircle, Upload } from 'lucide-react';
import { toast } from 'sonner';

function formatDate(s) {
  if (!s) return '—';
  try {
    return new Date(s).toLocaleDateString(undefined, { dateStyle: 'short' });
  } catch {
    return String(s);
  }
}

const STATUS_OPTIONS = [
  { value: 'SCHEDULED', label: 'Scheduled' },
  { value: 'IN_PROGRESS', label: 'In progress' },
  { value: 'AWAITING_PARTS', label: 'Awaiting parts' },
  { value: 'COMPLETED', label: 'Completed' },
];

export default function JobPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [workOrder, setWorkOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [invoiceModal, setInvoiceModal] = useState(false);
  const [invoiceForm, setInvoiceForm] = useState({ reference: '', description: '', submitted_amount: '' });
  const [invoiceSaving, setInvoiceSaving] = useState(false);
  const [notesForm, setNotesForm] = useState({ contractor_notes: '', completion_notes: '' });
  const [evidenceUploading, setEvidenceUploading] = useState(false);
  const [evidenceFileLoadingKey, setEvidenceFileLoadingKey] = useState(null);

  const api = token ? createJobLinkAPI(token) : null;

  const loadWorkOrder = useCallback(() => {
    if (!api) return;
    setLoading(true);
    setError(null);
    api.getWorkOrder()
      .then((res) => {
        setWorkOrder(res.data);
      })
      .catch((err) => {
        const msg = err.response?.data?.detail || 'Invalid or expired job link';
        setError(msg);
        setWorkOrder(null);
        toast.error(msg);
      })
      .finally(() => setLoading(false));
  }, [api]);

  useEffect(() => {
    if (!token) {
      setError('Missing job link. Use the link from your assignment email.');
      setLoading(false);
      return;
    }
    loadWorkOrder();
  }, [token, loadWorkOrder]);

  useEffect(() => {
    if (workOrder) {
      setNotesForm({
        contractor_notes: workOrder.contractor_notes || '',
        completion_notes: workOrder.completion_notes || '',
      });
    }
  }, [workOrder]);

  const handleAccept = () => {
    setActionLoading(true);
    api.acceptAssignment()
      .then(() => {
        toast.success('Assignment accepted');
        loadWorkOrder();
      })
      .catch((e) => toast.error(e.response?.data?.detail || 'Failed'))
      .finally(() => setActionLoading(false));
  };

  const handleDecline = () => {
    if (!confirm('Decline this assignment? The work order will be unassigned.')) return;
    setActionLoading(true);
    api.declineAssignment()
      .then(() => {
        toast.success('Assignment declined');
        setWorkOrder(null);
        setError('You have declined this assignment.');
      })
      .catch((e) => toast.error(e.response?.data?.detail || 'Failed'))
      .finally(() => setActionLoading(false));
  };

  const handleStatusChange = (status) => {
    setActionLoading(true);
    api.updateWorkOrder({ status })
      .then(() => {
        toast.success('Status updated');
        loadWorkOrder();
      })
      .catch((e) => toast.error(e.response?.data?.detail || 'Failed'))
      .finally(() => setActionLoading(false));
  };

  const handleSaveNotes = () => {
    setActionLoading(true);
    api.updateWorkOrder({
      contractor_notes: notesForm.contractor_notes || undefined,
      completion_notes: notesForm.completion_notes || undefined,
    })
      .then(() => {
        toast.success('Notes saved');
        loadWorkOrder();
      })
      .catch((e) => toast.error(e.response?.data?.detail || 'Failed'))
      .finally(() => setActionLoading(false));
  };

  const onEvidenceSelected = (e) => {
    const file = e.target.files?.[0];
    if (!file || !api) return;
    setEvidenceUploading(true);
    api
      .uploadWorkOrderEvidence(file)
      .then(() => {
        toast.success('Evidence uploaded');
        loadWorkOrder();
      })
      .catch((err) => toast.error(err.response?.data?.detail || 'Upload failed'))
      .finally(() => {
        setEvidenceUploading(false);
        e.target.value = '';
      });
  };

  const handleEvidenceFileOpen = (storageKey, download) => {
    if (!api) return;
    setEvidenceFileLoadingKey(storageKey);
    api
      .downloadWorkOrderEvidenceFile(storageKey, download)
      .then((res) =>
        openBlobApiResponse(res, {
          download,
          fallbackFilename: contractorEvidenceFilenameFromKey(storageKey),
        }),
      )
      .catch((err) => {
        const d = err?.response?.data?.detail;
        toast.error(typeof d === 'string' ? d : 'Could not open file');
      })
      .finally(() => setEvidenceFileLoadingKey(null));
  };

  const handleSubmitInvoice = (e) => {
    e.preventDefault();
    if (!api) return;
    setInvoiceSaving(true);
    api.submitInvoice({
      reference: invoiceForm.reference || undefined,
      description: invoiceForm.description || undefined,
      submitted_amount: invoiceForm.submitted_amount ? parseFloat(invoiceForm.submitted_amount) : undefined,
    })
      .then(() => {
        toast.success('Invoice submitted. It will appear in the client’s Approvals.');
        setInvoiceModal(false);
        setInvoiceForm({ reference: '', description: '', submitted_amount: '' });
      })
      .catch((err) => toast.error(err.response?.data?.detail || 'Failed'))
      .finally(() => setInvoiceSaving(false));
  };

  if (!token) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <CardContent className="p-6 text-center">
            <AlertCircle className="w-12 h-12 text-amber-500 mx-auto mb-3" />
            <h1 className="text-lg font-semibold text-gray-900">Invalid link</h1>
            <p className="text-gray-600 mt-2">Use the link from your work order assignment email.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loading && !workOrder) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-10 h-10 animate-spin text-electric-teal" />
      </div>
    );
  }

  if (error && !workOrder) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <CardContent className="p-6 text-center">
            <AlertCircle className="w-12 h-12 text-amber-500 mx-auto mb-3" />
            <h1 className="text-lg font-semibold text-gray-900">Invalid or expired link</h1>
            <p className="text-gray-600 mt-2">{error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const detail = workOrder;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-2">
        <Wrench className="w-6 h-6 text-electric-teal" />
        <span className="font-semibold text-midnight-blue">Work order</span>
      </header>

      <main className="max-w-2xl mx-auto p-4">
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50/80 p-3 text-sm text-amber-900">
          <p className="font-medium mb-1">Payment responsibility</p>
          <p>Pleerity coordinates work orders and invoice approval. Payment responsibility lies with the client. Pleerity does not process contractor payments. Follow up with the client for payment.</p>
        </div>
        <Card>
          <CardContent className="p-6 space-y-4">
            <p className="font-medium text-gray-900">{detail.description || detail.work_order_id}</p>
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt className="text-gray-500">Status</dt>
              <dd><span className="px-1.5 py-0.5 rounded bg-gray-100">{detail.status}</span></dd>
              <dt className="text-gray-500">Property</dt>
              <dd>{detail.property_address || detail.property_id}</dd>
              <dt className="text-gray-500">SLA complete by</dt>
              <dd>{formatDate(detail.sla_complete_by)}</dd>
            </dl>

            {(detail.status === 'ASSIGNED' || detail.status === 'OPEN') && (
              <div className="flex gap-2">
                <Button size="sm" onClick={handleAccept} disabled={!!actionLoading}>
                  {actionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4 mr-1" />}
                  Accept
                </Button>
                <Button size="sm" variant="outline" onClick={handleDecline} disabled={!!actionLoading}>
                  <XCircle className="w-4 h-4 mr-1" /> Decline
                </Button>
              </div>
            )}

            {!['OPEN', 'ASSIGNED'].includes(detail.status) && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Update status</label>
                <select
                  value={detail.status}
                  onChange={(e) => handleStatusChange(e.target.value)}
                  disabled={!!actionLoading}
                  className="border border-gray-200 rounded-md px-3 py-2 text-sm w-full"
                >
                  {STATUS_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Your notes</label>
              <Input
                placeholder="Contractor notes"
                value={notesForm.contractor_notes}
                onChange={(e) => setNotesForm((f) => ({ ...f, contractor_notes: e.target.value }))}
                className="mb-2"
              />
              <Input
                placeholder="Completion notes"
                value={notesForm.completion_notes}
                onChange={(e) => setNotesForm((f) => ({ ...f, completion_notes: e.target.value }))}
                className="mb-2"
              />
              <Button size="sm" variant="outline" onClick={handleSaveNotes} disabled={!!actionLoading || evidenceUploading}>
                Save notes
              </Button>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Evidence</label>
              <p className="text-xs text-gray-500 mb-2">PDF, images, or Word — max 20MB. Available after you accept the job.</p>
              {(detail.evidence_keys || []).length > 0 && (
                <ul className="text-sm text-gray-700 mb-2 space-y-2 max-h-40 overflow-y-auto">
                  {(detail.evidence_keys || []).map((k) => {
                    const keyStr = typeof k === 'string' ? k : String(k);
                    const fileKey = isContractorFileEvidenceKey(keyStr);
                    return (
                      <li key={keyStr} className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-2 last:border-0">
                        <span className="break-all text-xs">{contractorEvidenceFilenameFromKey(keyStr)}</span>
                        {fileKey ? (
                          <span className="flex gap-1 shrink-0">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="h-7 text-xs px-2"
                              disabled={evidenceFileLoadingKey === keyStr}
                              onClick={() => handleEvidenceFileOpen(keyStr, false)}
                            >
                              View
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="h-7 text-xs px-2"
                              onClick={() => handleEvidenceFileOpen(keyStr, true)}
                              disabled={evidenceFileLoadingKey === keyStr}
                            >
                              Download
                            </Button>
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400 shrink-0">Linked ref</span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
              <label className="inline-flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                <Upload className="w-4 h-4 shrink-0 text-electric-teal" />
                <span>{evidenceUploading ? 'Uploading…' : 'Choose file'}</span>
                <input
                  type="file"
                  className="sr-only"
                  accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,application/pdf"
                  disabled={evidenceUploading || detail.status === 'OPEN' || detail.status === 'ASSIGNED'}
                  onChange={onEvidenceSelected}
                />
              </label>
            </div>

            {['COMPLETED', 'VERIFIED', 'CLOSED'].includes((detail.status || '').toUpperCase()) && (
              <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90" onClick={() => setInvoiceModal(true)}>
                <FileText className="w-4 h-4 mr-1" /> Submit invoice
              </Button>
            )}
          </CardContent>
        </Card>
      </main>

      {invoiceModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4" onClick={() => setInvoiceModal(false)}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4">Submit invoice</h3>
            <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-2 mb-4">Pleerity coordinates work orders and invoice approval. Payment responsibility lies with the client. Pleerity does not process contractor payments. Follow up with the client for payment.</p>
            <form onSubmit={handleSubmitInvoice} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Reference (optional)</label>
                <Input value={invoiceForm.reference} onChange={(e) => setInvoiceForm((f) => ({ ...f, reference: e.target.value }))} placeholder="INV-001" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description (optional)</label>
                <textarea value={invoiceForm.description} onChange={(e) => setInvoiceForm((f) => ({ ...f, description: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full min-h-[80px]" rows={2} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Amount £ (optional)</label>
                <Input type="number" step="0.01" min="0" value={invoiceForm.submitted_amount} onChange={(e) => setInvoiceForm((f) => ({ ...f, submitted_amount: e.target.value }))} placeholder="0.00" />
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={invoiceSaving} className="bg-electric-teal hover:bg-electric-teal/90">
                  {invoiceSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Submit'}
                </Button>
                <Button type="button" variant="outline" onClick={() => setInvoiceModal(false)}>Cancel</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
