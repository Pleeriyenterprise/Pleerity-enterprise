import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Download, ExternalLink, Loader2 } from 'lucide-react';
import {
  fetchClientDocumentFileBlob,
  openClientDocumentFileInNewTab,
  resolveClientDocumentFileErrorMessage,
  downloadClientDocumentFile,
} from '../../utils/clientDocumentPreview';
import { toast } from '@/utils/portalNotifications';

/**
 * In-property-context document preview (blob from GET /documents/:id/file).
 * Does not change authority or routes; workspace link is a separate honest navigation CTA.
 */
export default function ClientDocumentPreviewModal({
  open,
  onOpenChange,
  api,
  doc,
  documentsWorkspacePath,
  requirementLabel,
  uploaderLabel,
}) {
  const [blobUrl, setBlobUrl] = useState(null);
  const [mimeType, setMimeType] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [openingTab, setOpeningTab] = useState(false);

  const fileName = doc ? doc.file_name || doc.original_filename || doc.document_id : '';

  const revokeObjectUrl = useCallback(() => {
    setBlobUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    setMimeType('');
  }, []);

  const resetUi = useCallback(() => {
    revokeObjectUrl();
    setError(null);
    setLoading(false);
    setOpeningTab(false);
  }, [revokeObjectUrl]);

  useEffect(() => {
    if (!open || !doc?.document_id || !api) {
      resetUi();
      return undefined;
    }

    let cancelled = false;
    revokeObjectUrl();
    setError(null);
    setLoading(true);

    (async () => {
      try {
        const blob = await fetchClientDocumentFileBlob(api, doc.document_id);
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        setBlobUrl(url);
        setMimeType(blob.type || '');
        setError(null);
    } catch (err) {
      if (cancelled) return;
      const msg = await resolveClientDocumentFileErrorMessage(err, 'Could not load document');
      setError(msg);
    } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
    // resetUi / revokeObjectUrl are stable callbacks (blob cleanup only).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, doc?.document_id, api]);

  const handleOpenChange = (next) => {
    if (!next) resetUi();
    onOpenChange(next);
  };

  const lowerName = (fileName || '').toLowerCase();
  const isPdf =
    (mimeType && mimeType.toLowerCase().includes('pdf')) ||
    lowerName.endsWith('.pdf') ||
    mimeType === 'application/octet-stream';
  const isImage = mimeType && mimeType.toLowerCase().startsWith('image/');

  const handleDownload = async () => {
    if (!doc) return;
    try {
      await downloadClientDocumentFile(api, doc, {
        onError: (m) => {
          setError(m);
          toast.error(m);
        },
      });
    } catch {
      /* handled via onError */
    }
  };

  const handleTryNewTab = async () => {
    if (!doc?.document_id) return;
    setOpeningTab(true);
    setError(null);
    try {
      await openClientDocumentFileInNewTab(api, doc.document_id);
    } catch (e) {
      const msg = e?.message || 'Could not open document';
      setError(msg);
      toast.error(msg);
    } finally {
      setOpeningTab(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="max-h-[min(92vh,880px)] w-[min(96vw,56rem)] max-w-[min(96vw,56rem)] gap-0 p-0 flex flex-col overflow-hidden sm:max-w-[min(96vw,56rem)]"
        data-testid="property-document-preview-modal"
      >
        <DialogHeader className="px-6 pt-6 pb-3 shrink-0 border-b border-gray-100 text-left">
          <DialogTitle className="pr-8 text-base sm:text-lg font-semibold text-midnight-blue break-words">
            {fileName || 'Document preview'}
          </DialogTitle>
          <DialogDescription className="text-xs sm:text-sm text-gray-600 space-y-1">
            {requirementLabel && requirementLabel !== '—' ? (
              <p>
                <span className="font-medium text-gray-700">Linked requirement:</span> {requirementLabel}
              </p>
            ) : null}
            {uploaderLabel && uploaderLabel !== '—' ? (
              <p>
                <span className="font-medium text-gray-700">Uploaded by:</span> {uploaderLabel}
              </p>
            ) : null}
            {(!requirementLabel || requirementLabel === '—') && (!uploaderLabel || uploaderLabel === '—') ? (
              <span className="sr-only">Document file preview</span>
            ) : null}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 min-h-[200px] max-h-[min(70vh,640px)] bg-slate-100 mx-4 my-3 rounded-lg border border-gray-200 overflow-hidden flex items-center justify-center">
          {loading ? (
            <div className="flex flex-col items-center gap-2 py-12 text-gray-600">
              <Loader2 className="h-8 w-8 animate-spin text-electric-teal" aria-hidden />
              <span className="text-sm">Loading preview…</span>
            </div>
          ) : error ? (
            <div className="p-6 text-center text-sm text-red-800 max-w-md">{error}</div>
          ) : blobUrl && isImage ? (
            <img src={blobUrl} alt="" className="max-h-full max-w-full object-contain" />
          ) : blobUrl && isPdf ? (
            <iframe title="Document preview" src={blobUrl} className="w-full h-full min-h-[min(60vh,520px)] bg-white" />
          ) : blobUrl ? (
            <div className="p-6 text-center text-sm text-gray-700 space-y-3 max-w-md">
              <p>Preview is not available for this file type in the property view.</p>
              <div className="flex flex-col sm:flex-row gap-2 justify-center">
                <Button type="button" variant="outline" size="sm" onClick={handleDownload}>
                  <Download className="w-4 h-4 mr-1" aria-hidden />
                  Download
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={handleTryNewTab} disabled={openingTab}>
                  {openingTab ? 'Opening…' : 'Try in new tab'}
                </Button>
              </div>
            </div>
          ) : null}
        </div>

        <DialogFooter className="px-4 py-4 border-t border-gray-100 flex-col sm:flex-row gap-2 sm:justify-between sm:items-center shrink-0 bg-white">
          <div className="flex flex-wrap gap-2 w-full sm:w-auto justify-stretch sm:justify-start">
            <Button type="button" variant="outline" size="sm" className="min-h-10" onClick={handleDownload} disabled={!doc}>
              <Download className="w-4 h-4 mr-1 shrink-0" aria-hidden />
              Download
            </Button>
            {documentsWorkspacePath ? (
              <Button type="button" variant="ghost" size="sm" className="min-h-10 text-gray-700" asChild>
                <Link to={documentsWorkspacePath} data-testid="property-preview-open-documents-workspace">
                  <ExternalLink className="w-4 h-4 mr-1 shrink-0" aria-hidden />
                  Open in Documents workspace
                </Link>
              </Button>
            ) : null}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="min-h-10 text-gray-600"
              onClick={handleTryNewTab}
              disabled={!doc?.document_id || openingTab || loading}
            >
              {openingTab ? 'Opening…' : 'Open in new tab'}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
