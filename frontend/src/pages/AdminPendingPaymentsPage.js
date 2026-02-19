import React, { useState, useEffect, useCallback } from 'react';
import {
  RefreshCw,
  Send,
  Copy,
  Loader2,
  AlertCircle,
  Search,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { toast } from 'sonner';
import api from '../api/client';

const AdminPendingPaymentsPage = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  const fetchPendingPayments = useCallback(async (q) => {
    setLoading(true);
    try {
      const params = q && q.trim() ? { q: q.trim() } : {};
      const response = await api.get('/admin/intake/pending-payments', { params });
      setItems(response.data?.items || []);
    } catch (error) {
      console.error('Failed to fetch pending payments:', error);
      toast.error('Failed to load pending payments');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => fetchPendingPayments(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery, fetchPendingPayments]);

  const handleSendPaymentLink = async (clientId) => {
    setSending(clientId);
    try {
      const response = await api.post(`/admin/intake/${clientId}/send-payment-link`);
      const { checkout_url, email_sent, reused } = response.data;
      toast.success(email_sent ? 'Payment link sent by email' : reused ? 'Existing link returned' : 'Payment link created');
      if (!email_sent && checkout_url) {
        toast.info('Email not configured. Use Copy link to share.');
      }
      await fetchPendingPayments(searchQuery);
    } catch (error) {
      const detail = error.response?.data?.detail;
      const msg = typeof detail === 'object' ? detail?.message : detail || 'Failed to send payment link';
      toast.error(msg);
    } finally {
      setSending(null);
    }
  };

  const handleCopyLink = (item) => {
    const url = item.latest_checkout_url;
    if (!url) {
      toast.error('No link available. Click Send payment link first.');
      return;
    }
    navigator.clipboard.writeText(url).then(
      () => toast.success('Link copied to clipboard'),
      () => toast.error('Failed to copy')
    );
  };

  const formatDate = (d) => {
    if (!d) return '—';
    const dt = typeof d === 'string' ? new Date(d) : d;
    return dt.toLocaleDateString(undefined, { dateStyle: 'short', timeStyle: 'short' });
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <Card>
        <CardHeader>
          <CardTitle>Pending Payments</CardTitle>
          <CardDescription>
            Clients who completed intake but have not paid. Send payment links or copy links to share. Recovery endpoints never modify subscription or provisioning status.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-4 mb-4">
            <div className="relative flex-1 min-w-[200px] max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search by CRN, email, or name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-3 py-2 w-full border rounded-md text-sm"
              />
            </div>
            <Button onClick={() => fetchPendingPayments(searchQuery)} variant="outline" disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Refresh
            </Button>
          </div>

          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : items.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">No pending payments.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 font-medium">CRN</th>
                    <th className="text-left py-2 font-medium">Name</th>
                    <th className="text-left py-2 font-medium">Email</th>
                    <th className="text-left py-2 font-medium">Plan</th>
                    <th className="text-left py-2 font-medium">Created</th>
                    <th className="text-left py-2 font-medium">Last link sent</th>
                    <th className="text-left py-2 font-medium">Lifecycle</th>
                    <th className="text-left py-2 font-medium">Last error</th>
                    <th className="text-left py-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.client_id} className="border-b hover:bg-muted/50">
                      <td className="py-2">{item.customer_reference || '—'}</td>
                      <td className="py-2">{item.full_name || '—'}</td>
                      <td className="py-2">{item.email || '—'}</td>
                      <td className="py-2">{item.billing_plan || '—'}</td>
                      <td className="py-2">{formatDate(item.created_at)}</td>
                      <td className="py-2">{formatDate(item.checkout_link_sent_at)}</td>
                      <td className="py-2">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${
                          item.lifecycle_status === 'abandoned' ? 'bg-amber-100 text-amber-800' :
                          item.lifecycle_status === 'archived' ? 'bg-gray-100 text-gray-700' :
                          'bg-blue-100 text-blue-800'
                        }`}>
                          {item.lifecycle_status || 'pending_payment'}
                        </span>
                      </td>
                      <td className="py-2">
                        {item.last_checkout_error_code ? (
                          <span className="inline-flex items-center gap-1 text-amber-600" title={item.last_checkout_error_message}>
                            <AlertCircle className="h-3 w-3" />
                            {item.last_checkout_error_code}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="py-2">
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            onClick={() => handleSendPaymentLink(item.client_id)}
                            disabled={sending === item.client_id}
                          >
                            {sending === item.client_id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Send className="h-3 w-3" />}
                            Send link
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleCopyLink(item)}
                            disabled={!item.latest_checkout_url}
                            title={item.latest_checkout_url ? 'Copy payment link' : 'Send payment link first'}
                          >
                            <Copy className="h-3 w-3" />
                            Copy link
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default AdminPendingPaymentsPage;
