import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  createContractorAPI,
  openBlobApiResponse,
  contractorEvidenceFilenameFromKey,
  isContractorFileEvidenceKey,
} from '../../api/client';
import { getContractorToken } from './ContractorLoginPage';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Wrench, LogOut, Loader2, X, FileText, CheckCircle, XCircle, Upload } from 'lucide-react';
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

export default function ContractorDashboardPage() {
  const navigate = useNavigate();
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [workOrders, setWorkOrders] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [detailId, setDetailId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [invoiceModal, setInvoiceModal] = useState(null);
  const [invoiceForm, setInvoiceForm] = useState({ reference: '', description: '', submitted_amount: '' });
  const [invoiceSaving, setInvoiceSaving] = useState(false);
  const [invoices, setInvoices] = useState([]);
  const [invoicesLoading, setInvoicesLoading] = useState(false);
  const [notesForm, setNotesForm] = useState({ contractor_notes: '', completion_notes: '' });
  const [evidenceUploading, setEvidenceUploading] = useState(false);
  const [evidenceFileLoadingKey, setEvidenceFileLoadingKey] = useState(null);

  useEffect(() => {
    const t = getContractorToken();
    if (!t) {
      navigate('/contractor/login', { replace: true });
      return;
    }
    setToken(t);
    try {
      const u = localStorage.getItem('contractor_user');
      if (u) setUser(JSON.parse(u));
    } catch (_) {}
  }, [navigate]);

  const api = token ? createContractorAPI(token) : null;

  const loadWorkOrders = useCallback(() => {
    if (!api) return;
    setLoading(true);
    api.getWorkOrders({ limit: 100 })
      .then((res) => {
        setWorkOrders(res.data?.work_orders || []);
        setTotal(res.data?.total ?? 0);
      })
      .catch(() => {
        toast.error('Failed to load work orders');
        setWorkOrders([]);
      })
      .finally(() => setLoading(false));
  }, [api]);

  useEffect(() => {
    if (api) loadWorkOrders();
  }, [api, loadWorkOrders]);

  const loadInvoices = useCallback(() => {
    if (!api) return;
    setInvoicesLoading(true);
    api.getInvoices({ limit: 50 })
      .then((res) => setInvoices(res.data?.invoices || []))
      .catch(() => setInvoices([]))
      .finally(() => setInvoicesLoading(false));
  }, [api]);

  useEffect(() => {
    if (api) loadInvoices();
  }, [api, loadInvoices]);

  useEffect(() => {
    if (!api || !detailId) return;
    setDetailLoading(true);
    api.getWorkOrder(detailId)
      .then((res) => setDetail(res.data))
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }, [api, detailId]);

  useEffect(() => {
    if (detail) {
      setNotesForm({
        contractor_notes: detail.contractor_notes || '',
        completion_notes: detail.completion_notes || '',
      });
    }
  }, [detail]);

  const handleLogout = () => {
    localStorage.removeItem('contractor_token');
    localStorage.removeItem('contractor_user');
    navigate('/contractor/login', { replace: true });
  };

  const handleAccept = (id) => {
    setActionLoading(id);
    api.acceptAssignment(id)
      .then(() => {
        toast.success('Assignment accepted');
        loadWorkOrders();
        setDetailId(null);
      })
      .catch((e) => toast.error(e.response?.data?.detail || 'Failed'))
      .finally(() => setActionLoading(null));
  };

  const handleDecline = (id) => {
    if (!confirm('Decline this assignment? The work order will be unassigned.')) return;
    setActionLoading(id);
    api.declineAssignment(id)
      .then(() => {
        toast.success('Assignment declined');
        loadWorkOrders();
        setDetailId(null);
      })
      .catch((e) => toast.error(e.response?.data?.detail || 'Failed'))
      .finally(() => setActionLoading(null));
  };

  const handleStatusChange = (id, status) => {
    setActionLoading(id);
    api.updateWorkOrder(id, { status })
      .then(() => {
        toast.success('Status updated');
        loadWorkOrders();
        if (detailId === id) api.getWorkOrder(id).then((r) => setDetail(r.data));
      })
      .catch((e) => toast.error(e.response?.data?.detail || 'Failed'))
      .finally(() => setActionLoading(null));
  };

  const handleSaveNotes = () => {
    if (!detail || !api) return;
    setActionLoading(detail.work_order_id);
    api
      .updateWorkOrder(detail.work_order_id, {
        contractor_notes: notesForm.contractor_notes || undefined,
        completion_notes: notesForm.completion_notes || undefined,
      })
      .then((r) => {
        toast.success('Notes saved');
        setDetail(r.data);
        loadWorkOrders();
      })
      .catch((e) => toast.error(e.response?.data?.detail || 'Failed'))
      .finally(() => setActionLoading(null));
  };

  const onEvidenceSelected = (e) => {
    const file = e.target.files?.[0];
    if (!file || !detail || !api) return;
    setEvidenceUploading(true);
    api
      .uploadWorkOrderEvidence(detail.work_order_id, file)
      .then((res) => {
        toast.success('Evidence uploaded');
        setDetail(res.data.work_order);
        loadWorkOrders();
      })
      .catch((err) => toast.error(err.response?.data?.detail || 'Upload failed'))
      .finally(() => {
        setEvidenceUploading(false);
        e.target.value = '';
      });
  };

  const handleEvidenceFileOpen = (storageKey, download) => {
    if (!detail || !api) return;
    setEvidenceFileLoadingKey(storageKey);
    api
      .downloadWorkOrderEvidenceFile(detail.work_order_id, storageKey, download)
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
    if (!invoiceModal || !api) return;
    setInvoiceSaving(true);
    api.submitInvoice({
      work_order_id: invoiceModal.work_order_id,
      reference: invoiceForm.reference || undefined,
      description: invoiceForm.description || undefined,
      submitted_amount: invoiceForm.submitted_amount ? parseFloat(invoiceForm.submitted_amount) : undefined,
    })
      .then(() => {
        toast.success('Invoice submitted. It will appear in the client’s Approvals.');
        setInvoiceModal(null);
        setInvoiceForm({ reference: '', description: '', submitted_amount: '' });
        loadInvoices();
      })
      .catch((err) => toast.error(err.response?.data?.detail || 'Failed'))
      .finally(() => setInvoiceSaving(false));
  };

  if (!token) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Wrench className="w-6 h-6 text-electric-teal" />
          <span className="font-semibold text-midnight-blue">Contractor Portal</span>
          {user?.email && <span className="text-sm text-gray-500">({user.email})</span>}
        </div>
        <Button variant="ghost" size="sm" onClick={handleLogout}>
          <LogOut className="w-4 h-4 mr-1" /> Sign out
        </Button>
      </header>

      <main className="max-w-4xl mx-auto p-4">
        <h1 className="text-xl font-bold text-gray-900 mb-4">My work orders</h1>
        {loading ? (
          <div className="flex items-center justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-electric-teal" /></div>
        ) : workOrders.length === 0 ? (
          <Card><CardContent className="py-8 text-center text-gray-500">No work orders assigned to you.</CardContent></Card>
        ) : (
          <div className="space-y-2">
            {workOrders.map((wo) => (
              <Card key={wo.work_order_id} className="cursor-pointer hover:shadow-md" onClick={() => setDetailId(wo.work_order_id)}>
                <CardContent className="py-3 flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-medium text-gray-900 truncate max-w-md">{wo.description || wo.work_order_id}</p>
                    <p className="text-sm text-gray-500">{wo.property_address || wo.property_id} · {wo.status}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">{formatDate(wo.sla_complete_by)}</span>
                    <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); setDetailId(wo.work_order_id); }}>View</Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* My invoices */}
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">My invoices</h2>
          {invoicesLoading ? (
            <div className="flex gap-2 text-gray-500 py-4"><Loader2 className="w-5 h-5 animate-spin" /> Loading…</div>
          ) : invoices.length === 0 ? (
            <Card><CardContent className="py-6 text-center text-gray-500">No invoices submitted yet.</CardContent></Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50">
                      <th className="text-left p-3 font-medium">Reference</th>
                      <th className="text-right p-3 font-medium">Amount</th>
                      <th className="p-3 font-medium">Status</th>
                      <th className="p-3 font-medium">Submitted</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.map((inv) => (
                      <tr key={inv.invoice_id} className="border-b last:border-0">
                        <td className="p-3">{inv.reference || inv.invoice_id}</td>
                        <td className="p-3 text-right">{inv.submitted_amount != null ? `£${Number(inv.submitted_amount).toFixed(2)}` : '—'}</td>
                        <td className="p-3"><span className={`px-1.5 py-0.5 rounded ${inv.status === 'approved' || inv.status === 'paid' ? 'bg-green-100 text-green-800' : inv.status === 'rejected' ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800'}`}>{inv.status || '—'}</span></td>
                        <td className="p-3">{formatDate(inv.submitted_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Detail drawer */}
        {detailId && (
          <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={() => setDetailId(null)}>
            <div className="w-full max-w-lg bg-white shadow-xl overflow-y-auto" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between p-4 border-b">
                <h2 className="font-semibold text-midnight-blue">Work order</h2>
                <button type="button" onClick={() => setDetailId(null)} className="p-1 rounded hover:bg-gray-100"><X className="w-5 h-5" /></button>
              </div>
              <div className="p-4">
                {detailLoading ? (
                  <Loader2 className="w-6 h-6 animate-spin text-electric-teal" />
                ) : detail ? (
                  <>
                    <p className="font-medium text-gray-900 mb-2">{detail.description || detail.work_order_id}</p>
                    <dl className="grid grid-cols-2 gap-2 text-sm mb-4">
                      <dt className="text-gray-500">Status</dt>
                      <dd><span className="px-1.5 py-0.5 rounded bg-gray-100">{detail.status}</span></dd>
                      <dt className="text-gray-500">Property</dt>
                      <dd>{detail.property_address || detail.property_id}</dd>
                      <dt className="text-gray-500">SLA complete by</dt>
                      <dd>{formatDate(detail.sla_complete_by)}</dd>
                    </dl>
                    <div className="space-y-2 mb-4">
                      <span className="block text-sm font-medium text-gray-700">Your notes</span>
                      <Input
                        placeholder="Contractor notes"
                        value={notesForm.contractor_notes}
                        onChange={(ev) => setNotesForm((f) => ({ ...f, contractor_notes: ev.target.value }))}
                        className="mb-1"
                      />
                      <Input
                        placeholder="Completion notes"
                        value={notesForm.completion_notes}
                        onChange={(ev) => setNotesForm((f) => ({ ...f, completion_notes: ev.target.value }))}
                        className="mb-1"
                      />
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={handleSaveNotes}
                        disabled={!!actionLoading || evidenceUploading}
                      >
                        Save notes
                      </Button>
                    </div>
                    <div className="mb-4">
                      <span className="block text-sm font-medium text-gray-700 mb-1">Evidence</span>
                      <p className="text-xs text-gray-500 mb-2">PDF, images, or Word — max 20MB. Upload after you accept the job.</p>
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
                                      disabled={evidenceFileLoadingKey === keyStr}
                                      onClick={() => handleEvidenceFileOpen(keyStr, true)}
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
                      <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
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
                    {(detail.status === 'ASSIGNED' || detail.status === 'OPEN') && (
                      <div className="flex gap-2 mb-4">
                        <Button size="sm" onClick={() => handleAccept(detail.work_order_id)} disabled={!!actionLoading}>
                          {actionLoading === detail.work_order_id ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4 mr-1" />}
                          Accept
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => handleDecline(detail.work_order_id)} disabled={!!actionLoading}>
                          <XCircle className="w-4 h-4 mr-1" /> Decline
                        </Button>
                      </div>
                    )}
                    {!['OPEN', 'ASSIGNED'].includes(detail.status) && (
                      <div className="mb-4">
                        <label className="block text-sm font-medium text-gray-700 mb-1">Update status</label>
                        <select
                          value={detail.status}
                          onChange={(e) => handleStatusChange(detail.work_order_id, e.target.value)}
                          disabled={!!actionLoading}
                          className="border border-gray-200 rounded-md px-3 py-2 text-sm w-full"
                        >
                          {STATUS_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                          ))}
                        </select>
                      </div>
                    )}
                    {['COMPLETED', 'VERIFIED', 'CLOSED'].includes((detail.status || '').toUpperCase()) && (
                      <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90" onClick={() => setInvoiceModal(detail)}>
                        <FileText className="w-4 h-4 mr-1" /> Submit invoice
                      </Button>
                    )}
                  </>
                ) : (
                  <p className="text-gray-500">Could not load details.</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Invoice modal */}
        {invoiceModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4" onClick={() => setInvoiceModal(null)}>
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
              <h3 className="text-lg font-semibold mb-4">Submit invoice</h3>
              <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-2 mb-4">Pleerity coordinates work orders and invoice approval. Payment responsibility lies with the client. Pleerity does not process contractor payments. Follow up with the client for payment.</p>
              <form onSubmit={handleSubmitInvoice} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Reference (optional)</label>
                  <input type="text" value={invoiceForm.reference} onChange={(e) => setInvoiceForm((f) => ({ ...f, reference: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full" placeholder="INV-001" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Description (optional)</label>
                  <textarea value={invoiceForm.description} onChange={(e) => setInvoiceForm((f) => ({ ...f, description: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full" rows={2} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Amount £ (optional)</label>
                  <input type="number" step="0.01" min="0" value={invoiceForm.submitted_amount} onChange={(e) => setInvoiceForm((f) => ({ ...f, submitted_amount: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full" placeholder="0.00" />
                </div>
                <div className="flex gap-2">
                  <Button type="submit" disabled={invoiceSaving} className="bg-electric-teal hover:bg-electric-teal/90">
                    {invoiceSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Submit'}
                  </Button>
                  <Button type="button" variant="outline" onClick={() => setInvoiceModal(null)}>Cancel</Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
