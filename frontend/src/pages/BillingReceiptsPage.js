/**
 * CVP portal: subscription receipts / invoices (self-service).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FileText, Download, Loader2, ArrowLeft, Receipt } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { toast } from 'sonner';
import client from '../api/client';

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

export default function BillingReceiptsPage() {
  const [loading, setLoading] = useState(true);
  const [receipts, setReceipts] = useState([]);
  const [latest, setLatest] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [listRes, latestRes] = await Promise.all([
        client.get('/client/billing/receipts'),
        client.get('/client/billing/receipt/latest'),
      ]);
      setReceipts(listRes.data.receipts || []);
      setLatest(latestRes.data.receipt || null);
    } catch (e) {
      console.error(e);
      toast.error('Failed to load receipts');
      setReceipts([]);
      setLatest(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleDownload = async (invoiceNumber) => {
    if (!invoiceNumber) return;
    try {
      const path = `/client/billing/receipt/${encodeURIComponent(invoiceNumber)}/download`;
      const response = await client.get(path, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${invoiceNumber}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Download started');
    } catch (e) {
      console.error(e);
      toast.error('Download failed');
    }
  };

  return (
    <div>
      <div className="mb-6">
        <Link
          to="/settings/billing"
          className="inline-flex items-center text-sm text-gray-600 hover:text-midnight-blue mb-2"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back to Billing
        </Link>
        <h2 className="text-xl font-semibold text-midnight-blue flex items-center gap-2">
          <Receipt className="w-6 h-6 text-electric-teal" />
          Receipts &amp; invoices
        </h2>
        <p className="text-gray-600 text-sm mt-1">
          Download PDF receipts for your Compliance Vault Pro subscription payments.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <Loader2 className="w-8 h-8 animate-spin mr-2" />
          Loading receipts…
        </div>
      ) : (
        <>
          {latest && (
            <Card className="mb-6 border-electric-teal/30 bg-teal-50/30">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Latest payment</CardTitle>
                <CardDescription>Most recent subscription checkout receipt</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="font-mono text-sm font-medium text-midnight-blue">{latest.invoice_number}</p>
                  <p className="text-sm text-gray-600">{formatDate(latest.date_issued)}</p>
                  {latest.amount_display && (
                    <p className="text-sm font-semibold mt-1">{latest.amount_display}</p>
                  )}
                  <p className="text-xs text-gray-500 mt-1">Status: {latest.payment_status}</p>
                </div>
                <Button
                  className="bg-electric-teal hover:bg-teal-700"
                  onClick={() => handleDownload(latest.invoice_number)}
                  disabled={!latest.invoice_number}
                >
                  <Download className="w-4 h-4 mr-2" />
                  Download PDF
                </Button>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">All receipts</CardTitle>
              <CardDescription>
                {receipts.length === 0
                  ? 'No stored receipts yet. After you complete a subscription checkout, your receipt will appear here.'
                  : `${receipts.length} receipt(s) on file`}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {receipts.length === 0 ? (
                <div className="text-center py-10 text-gray-500">
                  <FileText className="w-12 h-12 mx-auto mb-3 opacity-40" />
                  <p>No receipts to show.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-gray-500">
                        <th className="py-2 pr-4">Invoice #</th>
                        <th className="py-2 pr-4">Date</th>
                        <th className="py-2 pr-4">Amount</th>
                        <th className="py-2 pr-4">Status</th>
                        <th className="py-2 text-right">Download</th>
                      </tr>
                    </thead>
                    <tbody>
                      {receipts.map((r) => (
                        <tr key={r.invoice_number || r.stripe_checkout_session_id} className="border-b border-gray-100">
                          <td className="py-3 pr-4 font-mono text-xs">{r.invoice_number}</td>
                          <td className="py-3 pr-4">{formatDate(r.date_issued)}</td>
                          <td className="py-3 pr-4">{r.amount_display || '—'}</td>
                          <td className="py-3 pr-4">{r.payment_status}</td>
                          <td className="py-3 text-right">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleDownload(r.invoice_number)}
                              disabled={!r.invoice_number}
                            >
                              <Download className="w-4 h-4 mr-1" />
                              PDF
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
