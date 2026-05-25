import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Loader2, Check, X, FileText, AlertTriangle, RotateCcw } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { toast } from '@/utils/portalNotifications';
import api, { adminAPI } from '../api/client';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { getExtractionStatusPresentation } from '../utils/adminOperationalPresentation';
import { runGovernedAdminMutation } from '../utils/adminGovernedMutation';

const AdminExtractionQueuePage = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(null);

  const fetchQueue = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/documents/admin/extraction-queue');
      setItems(res.data?.items || []);
    } catch (err) {
      toast.error('Failed to load extraction queue');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchQueue(); }, [fetchQueue]);

  const handleConfirm = async (documentId) => {
    setActing(documentId);
    try {
      await api.post('/documents/admin/extraction-queue/confirm', { document_id: documentId });
      toast.success('Extraction applied');
      fetchQueue();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Failed to apply');
    } finally {
      setActing(null);
    }
  };

  const handleReject = async (documentId) => {
    setActing(documentId);
    try {
      await api.post('/documents/admin/extraction-queue/reject', { document_id: documentId, reason: 'Admin rejected' });
      toast.info('Extraction rejected');
      fetchQueue();
    } catch (err) {
      toast.error('Failed to reject');
    } finally {
      setActing(null);
    }
  };

  const handleRetry = async (documentId) => {
    const reason = window.prompt('Support reason for extraction retry (min 10 characters):');
    if (!reason || reason.trim().length < 10) {
      toast.error('Reason of at least 10 characters is required');
      return;
    }
    setActing(documentId);
    try {
      const res = await runGovernedAdminMutation({
        actionId: 'retry_document_extraction',
        reason: reason.trim(),
        resourceKey: documentId,
        mutate: (headers) =>
          adminAPI.retryDocumentExtraction(documentId, { reason: reason.trim() }, { headers }),
      });
      toast.success(res.data?.message || 'Extraction retry enqueued');
      fetchQueue();
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Retry failed';
      toast.error(typeof detail === 'string' ? detail : 'Retry failed');
    } finally {
      setActing(null);
    }
  };

  const formatDate = (d) => {
    if (!d) return '—';
    return new Date(d).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
  };

  return (
    <UnifiedAdminLayout>
    <div className="max-w-7xl mx-auto">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Extraction Review Queue
          </CardTitle>
          <CardDescription>
            Documents needing extraction review or that failed automated extraction. Confirm to apply extracted data to the requirement, or reject for manual entry.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex justify-end mb-4">
            <Button variant="outline" onClick={fetchQueue} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Refresh
            </Button>
          </div>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : items.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">No extractions in queue.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="extraction-queue-table">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 font-medium">File</th>
                    <th className="text-left py-2 font-medium">Client ID</th>
                    <th className="text-left py-2 font-medium">Status</th>
                    <th className="text-left py-2 font-medium">Extracted (type / expiry)</th>
                    <th className="text-left py-2 font-medium">Updated</th>
                    <th className="text-right py-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr key={row.extraction_id} className="border-b" data-testid={`queue-row-${row.document_id}`}>
                      <td className="py-2">{row.file_name || row.document_id}</td>
                      <td className="py-2 font-mono text-xs">{row.client_id}</td>
                      <td className="py-2">
                        {(() => {
                          const pres = getExtractionStatusPresentation(row.status);
                          return (
                        <span className={pres.badgeClass} title={pres.canonicalValue ? `Canonical: ${pres.canonicalValue}` : undefined}>
                          {pres.label}
                        </span>
                          );
                        })()}
                        {row.errors?.message && (
                          <span className="ml-1 text-red-600 text-xs" title={row.errors.message}>
                            <AlertTriangle className="inline w-3 h-3" />
                          </span>
                        )}
                      </td>
                      <td className="py-2">
                        {row.extracted?.doc_type || '—'} / {row.extracted?.expiry_date || '—'}
                      </td>
                      <td className="py-2">{formatDate(row.updated_at)}</td>
                      <td className="py-2 text-right">
                        {(row.status === 'NEEDS_REVIEW' || row.status === 'FAILED') && (
                          <>
                            {row.status === 'NEEDS_REVIEW' && (
                              <>
                                <Button
                                  size="sm"
                                  className="mr-2"
                                  disabled={acting === row.document_id}
                                  onClick={() => handleConfirm(row.document_id)}
                                  data-testid={`confirm-extraction-${row.document_id}`}
                                >
                                  {acting === row.document_id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
                                  Confirm
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={acting === row.document_id}
                                  onClick={() => handleReject(row.document_id)}
                                  data-testid={`reject-extraction-${row.document_id}`}
                                >
                                  <X className="h-3 w-3" />
                                  Reject
                                </Button>
                              </>
                            )}
                            <Button
                              size="sm"
                              variant="secondary"
                              className="ml-2"
                              disabled={acting === row.document_id}
                              onClick={() => handleRetry(row.document_id)}
                              data-testid={`retry-extraction-${row.document_id}`}
                            >
                              {acting === row.document_id ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                <RotateCcw className="h-3 w-3" />
                              )}
                              Retry
                            </Button>
                          </>
                        )}
                        {row.status === 'PENDING' && (
                          <span className="text-muted-foreground text-xs">Extraction in progress…</span>
                        )}
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
    </UnifiedAdminLayout>
  );
};

export default AdminExtractionQueuePage;
