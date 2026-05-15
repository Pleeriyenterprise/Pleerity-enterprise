import React from 'react';
import { Button } from '../ui/button';
import { Loader2, Download, Send } from 'lucide-react';

function fmt(value) {
  if (!value) return '—';
  const t = new Date(value).getTime();
  if (Number.isNaN(t)) return '—';
  return new Date(value).toLocaleString('en-GB');
}

export default function AdminPaymentHistoryTable({
  rows,
  loading,
  error,
  actionKey = null,
  onDownload,
  onResend,
  compact = false,
  reconciliationHint = '',
}) {
  if (loading && (!rows || rows.length === 0)) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500 py-6 justify-center">
        <Loader2 className="w-5 h-5 animate-spin text-electric-teal" />
        Loading payment history…
      </div>
    );
  }
  if (error) {
    return <p className="text-sm text-red-700 py-6 text-center border border-red-200 rounded-md bg-red-50/60">{error}</p>;
  }
  if (!rows || rows.length === 0) {
    return (
      <div className="space-y-3">
        {reconciliationHint ? (
          <p className="text-sm text-amber-900 border border-amber-200 bg-amber-50/80 rounded-md px-3 py-2">{reconciliationHint}</p>
        ) : null}
        <p className="text-sm text-gray-600 py-6 text-center border border-dashed rounded-md bg-gray-50/50">
          No payment history rows in this view (checkout PDFs, paid ledger, or orders).
        </p>
      </div>
    );
  }

  if (compact) {
    return (
      <div className="mt-2 space-y-2 max-h-64 overflow-y-auto" data-testid="control-panel-payment-history">
        {rows.slice(0, 12).map((r) => (
          <div key={r.receipt_key} className="flex items-center justify-between text-sm border border-gray-100 rounded-lg p-2 gap-2">
            <div className="min-w-0">
              <div className="font-medium truncate">{r.invoice_number || r.order_reference || r.receipt_key}</div>
              <div className="text-xs text-gray-600">{r.amount_display || '—'} / {fmt(r.date_issued)}</div>
              <div className="text-[11px] text-gray-500 mt-0.5">{r.payment_method || '—'} · {r.payment_reference_display || '—'}</div>
              {r.failed_attempt_marker ? <div className="text-[11px] text-red-700">{r.failed_attempt_reason || 'Payment requires support follow-up.'}</div> : null}
              <div className="text-[11px] text-gray-500">
                {r.retry_state_label || 'No retry in progress'}
                {r.next_retry_at_utc ? ` · Next retry ${fmt(r.next_retry_at_utc)}` : ''}
                {r.grace_period_ends_at_utc ? ` · Grace ends ${fmt(r.grace_period_ends_at_utc)}` : ''}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button type="button" className={`text-xs ${r.download_available ? 'text-electric-teal hover:underline' : 'text-gray-400 cursor-not-allowed'}`} disabled={!r.download_available} onClick={() => onDownload?.(r)} title={r.download_available ? 'Download receipt PDF' : (r.download_unavailable_reason || 'Download unavailable')}>Download</button>
              <button type="button" className={`text-xs ${r.resend_available ? 'text-gray-700 hover:underline' : 'text-gray-400 cursor-not-allowed'}`} disabled={!r.resend_available} onClick={() => onResend?.(r)} title={r.resend_available ? 'Resend receipt confirmation email' : (r.resend_unavailable_reason || 'Resend unavailable')}>Resend</button>
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto border rounded-md">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 text-left border-b">
            <th className="p-2 font-medium">Invoice #</th><th className="p-2 font-medium">Invoice Date</th><th className="p-2 font-medium">Amount</th><th className="p-2 font-medium">Status</th><th className="p-2 font-medium">Payment Method / Reference</th><th className="p-2 font-medium">Stripe Reference</th><th className="p-2 font-medium">Failed / Retry Timeline</th><th className="p-2 font-medium text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const rk = row.receipt_key || '';
            const busyDl = actionKey === `dl-${rk}`;
            const busyRs = actionKey === `rs-${rk}`;
            return (
              <tr key={rk} className="border-b last:border-0 hover:bg-gray-50/80">
                <td className="p-2 font-mono text-xs">{row.invoice_number || '—'}</td>
                <td className="p-2 whitespace-nowrap">{fmt(row.date_issued)}</td>
                <td className="p-2">{row.amount_display || '—'}</td>
                <td className="p-2">{row.payment_status || '—'}</td>
                <td className="p-2 text-xs"><div>{row.payment_method || '—'}</div><div className="text-gray-600 font-mono">{row.payment_reference_display || '—'}</div></td>
                <td className="p-2 text-xs font-mono max-w-[220px] truncate">{row.stripe_reference_display || row.stripe_invoice_id || '—'}</td>
                <td className="p-2 text-xs">
                  <div>{row.failed_attempt_marker ? 'Failed payment recorded' : 'No failed payment marker'}</div>
                  <div className="text-gray-600">{row.retry_state_label || 'No retry in progress'}</div>
                  <div className="text-gray-600">{row.next_retry_at_utc ? `Next retry: ${fmt(row.next_retry_at_utc)}` : 'Next retry: Not scheduled'}</div>
                  <div className="text-gray-600">{row.grace_period_ends_at_utc ? `Grace period ends: ${fmt(row.grace_period_ends_at_utc)}` : 'Grace period: No billing timestamp available yet'}</div>
                </td>
                <td className="p-2 text-right whitespace-nowrap">
                  <Button type="button" variant="ghost" size="sm" className="h-8 px-2" disabled={!row.download_available || busyDl} onClick={() => onDownload?.(row)} data-testid={`receipt-download-${rk}`} title={row.download_available ? 'Download receipt PDF' : (row.download_unavailable_reason || 'Download unavailable')}>{busyDl ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}</Button>
                  <Button type="button" variant="ghost" size="sm" className="h-8 px-2" disabled={!row.resend_available || busyRs} onClick={() => onResend?.(row)} data-testid={`receipt-resend-${rk}`} title={row.resend_available ? 'Resend receipt confirmation email' : (row.resend_unavailable_reason || 'Resend unavailable')}>{busyRs ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}</Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
