import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Loader2, Check, X, FileText, AlertTriangle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { toast } from 'sonner';
import api from '../api/client';

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

  const formatDate = (d) => {
    if (!d) return '—';
    return new Date(d).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Extraction Review Queue
          </CardTitle>
          <CardDescription>
            Documents with extraction status NEEDS_REVIEW or FAILED. Confirm to apply extracted data to the requirement, or reject for manual entry.
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
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                          row.status === 'FAILED' ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800'
                        }`}>
                          {row.status}
                        </span>
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
                        {row.status === 'FAILED' && (
                          <span className="text-muted-foreground text-xs">No action (failed)</span>
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
  );
};

export default AdminExtractionQueuePage;
