/**
 * Operations → Approvals: invoice and work-order approval workspace.
 * Summary KPIs, filters, queue table, exceptions panel, detail drawer, export. Gated by invoicing.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Input } from '../components/ui/input';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '../components/ui/sheet';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { ClipboardCheck, Loader2, Download, Search, Wrench, Briefcase, Eye, CheckCircle, XCircle, MessageCircle } from 'lucide-react';
import { toast } from 'sonner';
import { EntitlementProtectedRoute } from '../utils/EntitlementProtectedRoute';

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'needs_info', label: 'Needs Info' },
  { value: 'paid', label: 'Paid' },
];
const PAYMENT_METHOD_OPTIONS = [
  { value: 'bank_transfer', label: 'Bank transfer' },
  { value: 'cash', label: 'Cash' },
  { value: 'card', label: 'Card' },
  { value: 'cheque', label: 'Cheque' },
  { value: 'other', label: 'Other' },
];
const BENCHMARK_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'below', label: 'Below Benchmark' },
  { value: 'within', label: 'Within Benchmark' },
  { value: 'above', label: 'Above Benchmark' },
  { value: 'none', label: 'No Benchmark' },
];

function formatDate(s) {
  if (!s) return '—';
  try {
    const d = typeof s === 'string' ? new Date(s) : s;
    return d.toLocaleDateString(undefined, { dateStyle: 'short' });
  } catch {
    return s;
  }
}

function formatAmount(amount, currency = 'GBP') {
  if (amount == null) return '—';
  return new Intl.NumberFormat('en-GB', { style: 'currency', currency: currency || 'GBP' }).format(amount);
}

function StatusBadge({ status }) {
  const map = {
    pending: 'bg-amber-100 text-amber-800',
    approved: 'bg-green-100 text-green-800',
    rejected: 'bg-red-100 text-red-800',
    needs_info: 'bg-blue-100 text-blue-800',
    paid: 'bg-emerald-100 text-emerald-800',
  };
  const label = status ? status.replace(/_/g, ' ') : '—';
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${map[status] || 'bg-gray-100 text-gray-700'}`}>
      {label}
    </span>
  );
}

function BenchmarkBadge({ fit }) {
  const map = {
    below: 'bg-green-100 text-green-800',
    within: 'bg-gray-100 text-gray-800',
    above: 'bg-amber-100 text-amber-800',
    none: 'bg-gray-100 text-gray-500',
  };
  const label = fit === 'above' ? 'Above' : fit === 'below' ? 'Below' : fit === 'within' ? 'Within' : 'No benchmark';
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${map[fit] || 'bg-gray-100 text-gray-500'}`}>
      {label}
    </span>
  );
}

function ClientApprovalsPageInner() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [properties, setProperties] = useState([]);
  const [contractors, setContractors] = useState([]);
  const [filters, setFilters] = useState({
    status: '',
    contractorId: '',
    propertyId: '',
    workOrderId: '',
    benchmarkFit: '',
    q: '',
    from: '',
    to: '',
  });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [markPaidForm, setMarkPaidForm] = useState({ payment_method: '', payment_reference: '', payment_notes: '' });

  const loadApprovals = useCallback(() => {
    setLoading(true);
    setError(null);
    const params = {
      skip: 0,
      limit: 200,
      ...(filters.status && { status: filters.status }),
      ...(filters.contractorId && { contractorId: filters.contractorId }),
      ...(filters.propertyId && { propertyId: filters.propertyId }),
      ...(filters.workOrderId && { workOrderId: filters.workOrderId }),
      ...(filters.benchmarkFit && { benchmarkFit: filters.benchmarkFit }),
      ...(filters.q && { q: filters.q.trim() }),
      ...(filters.from && { from: filters.from }),
      ...(filters.to && { to: filters.to }),
    };
    clientAPI.getApprovals(params)
      .then((res) => setData(res.data))
      .catch((err) => {
        if (err?.response?.status === 403) {
          setError(err?.response?.data?.detail || 'Invoicing is not enabled for your account.');
        } else {
          setError('Failed to load approvals.');
          toast.error(err?.response?.data?.detail || 'Failed to load approvals');
        }
        setData(null);
      })
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => { loadApprovals(); }, [loadApprovals]);

  const loadProperties = useCallback(() => {
    clientAPI.getProperties().then((res) => {
      setProperties(res.data?.properties || res.data || []);
    }).catch(() => setProperties([]));
  }, []);
  const loadContractors = useCallback(() => {
    clientAPI.getContractors({ limit: 200 }).then((res) => {
      setContractors(res.data?.contractors || res.data || []);
    }).catch(() => setContractors([]));
  }, []);
  useEffect(() => { loadProperties(); loadContractors(); }, [loadProperties, loadContractors]);

  const openDrawer = (invoiceId) => {
    setSelectedId(invoiceId);
    setDrawerOpen(true);
    setDetail(null);
    setDetailLoading(true);
    clientAPI.getApproval(invoiceId)
      .then((res) => setDetail(res.data))
      .catch(() => {
        toast.error('Failed to load detail');
        setDetail(null);
      })
      .finally(() => setDetailLoading(false));
  };

  const invoiceIdFromUrl = searchParams.get('invoice_id');
  const workOrderIdFromUrl = searchParams.get('work_order_id');
  useEffect(() => {
    if (invoiceIdFromUrl) openDrawer(invoiceIdFromUrl);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invoiceIdFromUrl]);

  useEffect(() => {
    if (workOrderIdFromUrl) {
      setFilters((f) => (f.workOrderId === workOrderIdFromUrl ? f : { ...f, workOrderId: workOrderIdFromUrl }));
    }
  }, [workOrderIdFromUrl]);

  const handleAction = (action, notes, invoiceIdParam) => {
    const id = invoiceIdParam ?? selectedId;
    if (!id) return;
    setActionLoading(true);
    const payload = { action, notes };
    if (action === 'mark_paid') {
      payload.payment_method = markPaidForm.payment_method;
      payload.payment_reference = markPaidForm.payment_reference || undefined;
      payload.payment_notes = markPaidForm.payment_notes || undefined;
    }
    clientAPI.updateApproval(id, payload)
      .then(() => {
        if (action === 'mark_paid') {
          toast.success('Invoice marked as paid');
          setMarkPaidForm({ payment_method: '', payment_reference: '', payment_notes: '' });
        } else {
          toast.success(action === 'approved' ? 'Approved' : action === 'rejected' ? 'Rejected' : 'More info requested');
        }
        loadApprovals();
        setDrawerOpen(false);
        setSelectedId(null);
        setDetail(null);
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Action failed'))
      .finally(() => setActionLoading(false));
  };

  const handleExport = () => {
    setExporting(true);
    const params = {
      ...(filters.status && { status: filters.status }),
      ...(filters.contractorId && { contractorId: filters.contractorId }),
      ...(filters.propertyId && { propertyId: filters.propertyId }),
      ...(filters.workOrderId && { workOrderId: filters.workOrderId }),
      ...(filters.benchmarkFit && { benchmarkFit: filters.benchmarkFit }),
      ...(filters.q && { q: filters.q.trim() }),
      ...(filters.from && { from: filters.from }),
      ...(filters.to && { to: filters.to }),
    };
    clientAPI.exportApprovals(params)
      .then((res) => {
        const blob = new Blob([res.data], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `approvals_export_${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        toast.success('Export downloaded');
      })
      .catch(() => toast.error('Export failed'))
      .finally(() => setExporting(false));
  };

  const applyFilter = (key, value) => {
    setFilters((f) => ({ ...f, [key]: value }));
  };

  const summary = data?.summary || {};
  const approvals = data?.approvals || [];
  const exceptions = data?.exceptions || [];
  const hasFilters = filters.status || filters.contractorId || filters.propertyId || filters.workOrderId || filters.benchmarkFit || (filters.q && filters.q.trim()) || filters.from || filters.to;

  if (error && !loading) {
    return (
      <div className="p-6 max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-4">
          <ClipboardCheck className="w-7 h-7" />
          Approvals
        </h1>
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-6 flex items-start gap-3">
            <p className="font-medium text-amber-900">{error}</p>
            <p className="text-sm text-amber-800 mt-1">Contact your account administrator to enable invoicing for your account.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <ClipboardCheck className="w-7 h-7" />
            Approvals
          </h1>
          <p className="text-gray-600 mt-1">Review invoices and cost submissions linked to work orders. Compare to benchmarks and approve, reject, or request more information.</p>
          <div className="mt-3 rounded-lg border border-sky-200 bg-sky-50/80 p-3 text-sm text-sky-900 max-w-2xl">
            <p className="font-medium mb-1">Payment responsibility</p>
            <p>Contractors are independent service providers engaged by you. You are responsible for paying the contractor. Pleerity does not process contractor payments.</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={handleExport} disabled={exporting}>
          {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
          Export CSV
        </Button>
      </div>

      {/* Summary KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-3 mb-6">
        {[
          { key: 'pending', label: 'Pending Approval', value: summary.pending ?? 0, onClick: () => applyFilter('status', 'pending') },
          { key: 'approvedThisMonth', label: 'Approved This Month', value: summary.approvedThisMonth ?? 0 },
          { key: 'rejected', label: 'Rejected', value: summary.rejected ?? 0, onClick: () => applyFilter('status', 'rejected') },
          { key: 'needsInfo', label: 'Needs Info', value: summary.needsInfo ?? 0, onClick: () => applyFilter('status', 'needs_info') },
          { key: 'paid', label: 'Paid', value: summary.paid ?? 0, onClick: () => applyFilter('status', 'paid') },
          { key: 'outOfRange', label: 'Out of Range', value: summary.outOfRange ?? 0, onClick: () => applyFilter('benchmarkFit', 'above') },
          { key: 'totalPendingValue', label: 'Pending Value', value: summary.totalPendingValue != null ? formatAmount(summary.totalPendingValue) : '—' },
        ].map(({ key, label, value, onClick }) => (
          <Card
            key={key}
            className={`cursor-pointer transition-shadow hover:shadow-md ${onClick ? 'border-electric-teal/30' : ''}`}
            onClick={onClick}
          >
            <CardContent className="p-4">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
              <p className="text-xl font-semibold text-gray-900 mt-1">{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <CardContent className="p-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex items-center gap-2 min-w-[200px] flex-1">
              <Search className="w-4 h-4 text-gray-400" />
              <Input
                placeholder="Search ref, contractor, property, work order…"
                value={filters.q}
                onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
                className="max-w-sm"
              />
            </div>
            <Select value={filters.status || 'all'} onValueChange={(v) => applyFilter('status', v === 'all' ? '' : v)}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((o) => (
                  <SelectItem key={o.value || 'all'} value={o.value || 'all'}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filters.benchmarkFit || 'all'} onValueChange={(v) => applyFilter('benchmarkFit', v === 'all' ? '' : v)}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Benchmark" />
              </SelectTrigger>
              <SelectContent>
                {BENCHMARK_OPTIONS.map((o) => (
                  <SelectItem key={o.value || 'all'} value={o.value || 'all'}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filters.propertyId || 'all'} onValueChange={(v) => applyFilter('propertyId', v === 'all' ? '' : v)}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Property" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All properties</SelectItem>
                {properties.map((p) => (
                  <SelectItem key={p.property_id} value={p.property_id}>{p.nickname || p.address_line_1 || p.property_id}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filters.contractorId || 'all'} onValueChange={(v) => applyFilter('contractorId', v === 'all' ? '' : v)}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Contractor" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All contractors</SelectItem>
                {contractors.map((c) => (
                  <SelectItem key={c.contractor_id} value={c.contractor_id}>{c.company_name || c.contractor_id}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              placeholder="Work order ID"
              value={filters.workOrderId}
              onChange={(e) => setFilters((f) => ({ ...f, workOrderId: e.target.value }))}
              className="w-[140px]"
            />
            <Input
              type="date"
              placeholder="From"
              value={filters.from}
              onChange={(e) => setFilters((f) => ({ ...f, from: e.target.value }))}
              className="w-[140px]"
            />
            <Input
              type="date"
              placeholder="To"
              value={filters.to}
              onChange={(e) => setFilters((f) => ({ ...f, to: e.target.value }))}
              className="w-[140px]"
            />
          </div>
        </CardContent>
      </Card>

      {/* Exceptions panel */}
      {exceptions.length > 0 && (
        <Card className="mb-6 border-amber-200 bg-amber-50/50">
          <CardHeader>
            <CardTitle className="text-base">Review Exceptions</CardTitle>
            <CardDescription className="text-sm text-amber-800">
              Items that need attention: above benchmark, missing work order link, missing contractor, or missing attachment.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {exceptions.slice(0, 10).map((ex) => (
                <li key={ex.invoice_id} className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-medium">{ex.reference || ex.invoice_id}</span>
                  <span className="text-gray-600">{ex.property_label}</span>
                  <span className="text-gray-600">{ex.contractor_label}</span>
                  <span className="text-amber-700">{ex.reason_flagged}</span>
                  <Button variant="outline" size="sm" onClick={() => openDrawer(ex.invoice_id)}>View</Button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Approval queue table */}
      <Card>
        <CardHeader>
          <CardTitle>Approval queue</CardTitle>
          <CardDescription>
            {approvals.length} item(s){hasFilters ? ' matching filters' : ''}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex gap-2 text-gray-500 py-8">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading…
            </div>
          ) : approvals.length === 0 ? (
            <div className="py-12 text-center text-gray-500">
              <ClipboardCheck className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p className="font-medium">
                {hasFilters ? 'No approval items match your current filters.' : 'No invoices or approvals are waiting for review.'}
              </p>
              <div className="flex justify-center gap-3 mt-4">
                <Button variant="outline" size="sm" onClick={() => navigate('/operations/work-orders')}>
                  <Wrench className="w-4 h-4 mr-2" />
                  View Work Orders
                </Button>
                <Button variant="outline" size="sm" onClick={() => navigate('/operations/contractors')}>
                  <Briefcase className="w-4 h-4 mr-2" />
                  View Contractors
                </Button>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ref</TableHead>
                  <TableHead>Property</TableHead>
                  <TableHead>Work Order</TableHead>
                  <TableHead>Contractor</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead>Benchmark</TableHead>
                  <TableHead>Fit</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {approvals.map((row) => (
                  <TableRow
                    key={row.invoice_id}
                    className={row.benchmark_fit === 'above' ? 'bg-amber-50/50' : ''}
                  >
                    <TableCell className="font-medium">{row.reference || row.invoice_id}</TableCell>
                    <TableCell>{row.property_label ?? '—'}</TableCell>
                    <TableCell>{row.work_order_id ? (row.work_order_label || row.work_order_id) : <span className="text-amber-600">—</span>}</TableCell>
                    <TableCell>{row.contractor_label ?? '—'}</TableCell>
                    <TableCell className="text-right">{formatAmount(row.submitted_amount, row.currency)}</TableCell>
                    <TableCell>
                      {row.benchmark_min != null && row.benchmark_max != null
                        ? `${formatAmount(row.benchmark_min, row.currency)} – ${formatAmount(row.benchmark_max, row.currency)}`
                        : 'No benchmark'}
                    </TableCell>
                    <TableCell><BenchmarkBadge fit={row.benchmark_fit} /></TableCell>
                    <TableCell><StatusBadge status={row.status} /></TableCell>
                    <TableCell>{formatDate(row.submitted_at)}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => openDrawer(row.invoice_id)}><Eye className="w-4 h-4" /></Button>
                      {row.status === 'pending' && (
                        <>
                          <Button variant="ghost" size="sm" className="text-green-700" onClick={() => handleAction('approved', undefined, row.invoice_id)}><CheckCircle className="w-4 h-4" /></Button>
                          <Button variant="ghost" size="sm" className="text-red-700" onClick={() => handleAction('rejected', undefined, row.invoice_id)}><XCircle className="w-4 h-4" /></Button>
                          <Button variant="ghost" size="sm" className="text-blue-700" onClick={() => handleAction('needs_info', undefined, row.invoice_id)}><MessageCircle className="w-4 h-4" /></Button>
                        </>
                      )}
                      {row.status === 'approved' && (
                        <Button variant="ghost" size="sm" className="text-emerald-700" onClick={() => openDrawer(row.invoice_id)} title="Mark as paid">Mark paid</Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Detail drawer */}
      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent side="right" className="w-full sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle>{detail ? (detail.reference || detail.invoice_id) : 'Approval detail'}</SheetTitle>
            <SheetDescription>
              {detail && (
                <>
                  <StatusBadge status={detail.status} /> · {formatAmount(detail.submitted_amount, detail.currency)} · {detail.contractor_label}
                </>
              )}
            </SheetDescription>
          </SheetHeader>
          {detailLoading ? (
            <div className="flex gap-2 text-gray-500 py-8"><Loader2 className="w-5 h-5 animate-spin" /> Loading…</div>
          ) : detail ? (
            <div className="mt-6 space-y-6">
              <div className="rounded-lg border border-sky-200 bg-sky-50/80 p-3 text-sm text-sky-900">
                <p className="font-medium mb-1">Payment responsibility</p>
                <p>Contractors are independent service providers engaged by you. You are responsible for paying the contractor. Pleerity does not process contractor payments.</p>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Linked context</h4>
                <ul className="text-sm space-y-1">
                  <li><strong>Property:</strong> {detail.property_label ?? '—'}</li>
                  <li><strong>Work order:</strong> {detail.work_order_label || detail.work_order_id || '—'}</li>
                </ul>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Financial review</h4>
                <p><strong>Submitted:</strong> {formatAmount(detail.submitted_amount, detail.currency)}</p>
                <p><strong>Benchmark:</strong> {detail.benchmark_min != null && detail.benchmark_max != null ? `${formatAmount(detail.benchmark_min, detail.currency)} – ${formatAmount(detail.benchmark_max, detail.currency)}` : 'No benchmark'}</p>
                <p><strong>Fit:</strong> <BenchmarkBadge fit={detail.benchmark_fit} /></p>
                {detail.description && <p className="mt-2 text-gray-600">{detail.description}</p>}
                {detail.attachment_storage_key ? <p className="text-sm text-gray-500 mt-1">Document attached</p> : <p className="text-sm text-gray-400 mt-1">No document attached</p>}
              </div>
              {detail.status === 'pending' && (
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" className="bg-green-600 hover:bg-green-700" onClick={() => handleAction('approved', null, detail.invoice_id)} disabled={actionLoading}>Approve</Button>
                  <Button size="sm" variant="destructive" onClick={() => handleAction('rejected', null, detail.invoice_id)} disabled={actionLoading}>Reject</Button>
                  <Button size="sm" variant="outline" onClick={() => handleAction('needs_info', null, detail.invoice_id)} disabled={actionLoading}>Request more info</Button>
                </div>
              )}
              {detail.status === 'approved' && (
                <div className="space-y-3 border-t pt-4">
                  <h4 className="text-sm font-semibold text-gray-700">Mark as paid</h4>
                  <Select value={markPaidForm.payment_method} onValueChange={(v) => setMarkPaidForm((f) => ({ ...f, payment_method: v }))}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Payment method" />
                    </SelectTrigger>
                    <SelectContent>
                      {PAYMENT_METHOD_OPTIONS.map((o) => (
                        <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input
                    placeholder="Payment reference (optional)"
                    value={markPaidForm.payment_reference}
                    onChange={(e) => setMarkPaidForm((f) => ({ ...f, payment_reference: e.target.value }))}
                  />
                  <Input
                    placeholder="Notes (optional)"
                    value={markPaidForm.payment_notes}
                    onChange={(e) => setMarkPaidForm((f) => ({ ...f, payment_notes: e.target.value }))}
                  />
                  <Button
                    size="sm"
                    className="bg-emerald-600 hover:bg-emerald-700"
                    disabled={actionLoading || !markPaidForm.payment_method}
                    onClick={() => handleAction('mark_paid', null, detail.invoice_id)}
                  >
                    Mark as paid
                  </Button>
                </div>
              )}
              {detail.status === 'paid' && (detail.paid_at || detail.payment_method) && (
                <div className="text-sm text-gray-600 space-y-1 border-t pt-4">
                  <p><strong>Paid at:</strong> {formatDate(detail.paid_at)}</p>
                  {detail.payment_method && <p><strong>Payment method:</strong> {PAYMENT_METHOD_OPTIONS.find((o) => o.value === detail.payment_method)?.label || detail.payment_method}</p>}
                  {detail.payment_reference && <p><strong>Payment reference:</strong> {detail.payment_reference}</p>}
                  {detail.payment_notes && <p><strong>Notes:</strong> {detail.payment_notes}</p>}
                </div>
              )}
              {detail.history && detail.history.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">History</h4>
                  <ul className="text-sm space-y-2">
                    {detail.history.map((h, i) => (
                      <li key={i}>
                        {h.action} {h.created_at ? formatDate(h.created_at) : ''} {h.notes ? `— ${h.notes}` : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}

export default function ClientApprovalsPage() {
  return (
    <EntitlementProtectedRoute requiredFeature="invoicing">
      <ClientApprovalsPageInner />
    </EntitlementProtectedRoute>
  );
}
