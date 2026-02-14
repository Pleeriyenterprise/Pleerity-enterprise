/**
 * ClearForm Document View Page
 * 
 * Displays generated document with download options and PDF preview.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { 
  FileText, 
  ArrowLeft, 
  Download,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  Copy,
  Trash2,
  Eye,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  FileCode,
  X
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { documentsApi } from '../api/clearformApi';
import { toast } from 'sonner';

// Configure PDF.js worker - use local worker file
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';

const ClearFormDocumentPage = () => {
  const navigate = useNavigate();
  const { documentId } = useParams();
  const [document, setDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [activeTab, setActiveTab] = useState('preview');
  
  // PDF viewer state
  const [pdfUrl, setPdfUrl] = useState(null);
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1.0);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const loadDocument = async () => {
      try {
        const doc = await documentsApi.getDocument(documentId);
        if (!cancelled) setDocument(doc);
      } catch (error) {
        if (!cancelled) {
          toast.error('Document not found');
          navigate('/clearform/vault');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadDocument();
    return () => { cancelled = true; };
  }, [documentId, navigate]);

  useEffect(() => {
    // Poll for updates if document is generating
    if (document?.status === 'PENDING' || document?.status === 'GENERATING') {
      setPolling(true);
      const interval = setInterval(async () => {
        try {
          const updated = await documentsApi.getDocument(documentId);
          setDocument(updated);
          if (updated.status === 'COMPLETED' || updated.status === 'FAILED') {
            setPolling(false);
            clearInterval(interval);
          }
        } catch (error) {
          console.error('Polling error:', error);
        }
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [document?.status, documentId]);

  const loadPdf = useCallback(async () => {
    if (!document?.document_id) return;
    setPdfLoading(true);
    setPdfError(null);
    try {
      const API_BASE = process.env.REACT_APP_BACKEND_URL;
      const token = localStorage.getItem('clearform_token');
      const response = await fetch(
        `${API_BASE}/api/clearform/documents/${document.document_id}/download?format=pdf`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!response.ok) throw new Error('Failed to load PDF');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      setPdfUrl(url);
    } catch (error) {
      console.error('PDF load error:', error);
      setPdfError('Could not load PDF preview');
    } finally {
      setPdfLoading(false);
    }
  }, [document?.document_id]);

  // Load PDF when document is completed
  useEffect(() => {
    if (document?.status === 'COMPLETED' && document?.document_id) {
      loadPdf();
    }
  }, [document?.status, document?.document_id, loadPdf]);

  const onDocumentLoadSuccess = ({ numPages }) => {
    setNumPages(numPages);
    setPageNumber(1);
  };

  const onDocumentLoadError = (error) => {
    console.error('PDF load error:', error);
    setPdfError('Could not load PDF preview');
  };

  const handleCopy = () => {
    if (document?.content_plain) {
      navigator.clipboard.writeText(document.content_plain);
      toast.success('Copied to clipboard');
    }
  };

  // Clean markdown content (remove code fences and AI preamble)
  const cleanMarkdown = (content) => {
    if (!content) return '';
    let cleaned = content;
    
    // First, try to extract content from within code blocks (handles ```markdown ... ```)
    const codeBlockMatch = cleaned.match(/```(?:markdown|md)?\s*\n([\s\S]*?)```/i);
    if (codeBlockMatch) {
      cleaned = codeBlockMatch[1];
    } else {
      // No full code block found, just strip any fence markers
      cleaned = cleaned
        .replace(/```(?:markdown|md)?\s*\n?/gi, '')
        .replace(/\n?```\s*$/gi, '');
    }
    
    // Remove common AI preambles that appear before the actual content
    const preamblePatterns = [
      /^(?:okay,?\s*)?(?:i can help you with that\.?\s*)?/i,
      /^(?:here'?s?\s+)?(?:a\s+)?(?:draft\s+)?(?:of\s+)?(?:a\s+)?(?:formal\s+)?(?:professional\s+)?(?:[\w\s]+)?(?:letter|document|cv|resume|template)(?:\s+you\s+can\s+use)?(?:\s+to[\w\s]+)?(?:\s+based\s+on[\w\s,]+)?(?:\s+formatted\s+in\s+markdown)?:?\s*/i,
      /^(?:sure[,!]?\s*)?(?:here'?s?\s+)?/i,
      /^(?:certainly[,!]?\s*)?/i,
    ];
    
    for (const pattern of preamblePatterns) {
      cleaned = cleaned.replace(pattern, '');
    }
    
    return cleaned.trim();
  };

  const handleDownload = async (format) => {
    try {
      if (format === 'pdf') {
        // Use backend PDF generation
        const API_BASE = process.env.REACT_APP_BACKEND_URL;
        const token = localStorage.getItem('clearform_token');
        const response = await fetch(
          `${API_BASE}/api/clearform/documents/${document.document_id}/download?format=pdf`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!response.ok) throw new Error('PDF download failed');
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = window.document.createElement('a');
        a.href = url;
        a.download = `${document.title}.pdf`;
        window.document.body.appendChild(a);
        a.click();
        window.document.body.removeChild(a);
        URL.revokeObjectURL(url);
        toast.success('Downloaded as PDF');
        return;
      }
      
      // For text formats, use local generation
      const content = format === 'markdown' ? cleanMarkdown(document.content_markdown) : document.content_plain;
      const blob = new Blob([content], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = window.document.createElement('a');
      a.href = url;
      a.download = `${document.title}.${format === 'markdown' ? 'md' : 'txt'}`;
      window.document.body.appendChild(a);
      a.click();
      window.document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success(`Downloaded as ${format}`);
    } catch (error) {
      toast.error('Download failed');
    }
  };

  const handleArchive = async () => {
    try {
      await documentsApi.archiveDocument(documentId);
      toast.success('Document archived');
      navigate('/clearform/vault');
    } catch (error) {
      toast.error('Failed to archive document');
    }
  };

  const getStatusDisplay = () => {
    switch (document?.status) {
      case 'COMPLETED':
        return { icon: CheckCircle, color: 'text-emerald-500', label: 'Completed' };
      case 'FAILED':
        return { icon: XCircle, color: 'text-red-500', label: 'Failed' };
      case 'GENERATING':
        return { icon: Loader2, color: 'text-blue-500', label: 'Generating...' };
      default:
        return { icon: Clock, color: 'text-yellow-500', label: 'Pending' };
    }
  };

  // PDF navigation handlers
  const goToPrevPage = () => setPageNumber(prev => Math.max(prev - 1, 1));
  const goToNextPage = () => setPageNumber(prev => Math.min(prev + 1, numPages || 1));
  const zoomIn = () => setScale(prev => Math.min(prev + 0.25, 2.5));
  const zoomOut = () => setScale(prev => Math.max(prev - 0.25, 0.5));

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
      </div>
    );
  }

  const status = getStatusDisplay();
  const StatusIcon = status.icon;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/clearform/dashboard" className="flex items-center gap-3">
            <img 
              src="/pleerity-logo.jpg" 
              alt="Pleerity" 
              className="h-8 w-auto"
            />
            <div className="flex flex-col">
              <span className="text-lg font-bold text-slate-900">ClearForm</span>
              <span className="text-xs text-slate-500">by Pleerity</span>
            </div>
          </Link>
        </div>
      </header>

      {/* Main */}
      <main className="container mx-auto px-4 py-8 max-w-5xl">
        <Button variant="ghost" className="mb-6" onClick={() => navigate('/clearform/dashboard')}>
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to Dashboard
        </Button>

        {/* Document Header */}
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-start justify-between flex-wrap gap-4">
              <div>
                <CardTitle className="text-xl">{document?.title}</CardTitle>
                <div className="flex items-center gap-4 mt-2 text-sm text-slate-500 flex-wrap">
                  <span className="capitalize">{document?.document_type?.replace('_', ' ')}</span>
                  <span>•</span>
                  <span>{new Date(document?.created_at).toLocaleDateString()}</span>
                  <span>•</span>
                  <span className={`flex items-center gap-1 ${status.color}`}>
                    <StatusIcon className={`w-4 h-4 ${document?.status === 'GENERATING' ? 'animate-spin' : ''}`} />
                    {status.label}
                  </span>
                </div>
              </div>
              
              {document?.status === 'COMPLETED' && (
                <div className="flex gap-2 flex-wrap">
                  <Button variant="outline" size="sm" onClick={handleCopy} data-testid="copy-btn">
                    <Copy className="w-4 h-4 mr-2" /> Copy
                  </Button>
                  <Button variant="default" size="sm" onClick={() => handleDownload('pdf')} data-testid="download-pdf-btn" className="bg-emerald-600 hover:bg-emerald-700">
                    <Download className="w-4 h-4 mr-2" /> PDF
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => handleDownload('plain')} data-testid="download-txt-btn">
                    <Download className="w-4 h-4 mr-2" /> TXT
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => handleDownload('markdown')} data-testid="download-md-btn">
                    <Download className="w-4 h-4 mr-2" /> MD
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
        </Card>

        {/* Document Content */}
        <Card>
          <CardContent className="p-6">
            {polling && (
              <div className="flex items-center justify-center py-12">
                <div className="text-center">
                  <Loader2 className="w-12 h-12 animate-spin text-emerald-500 mx-auto mb-4" />
                  <p className="text-slate-600">Generating your document...</p>
                  <p className="text-sm text-slate-400 mt-1">This usually takes 10-30 seconds</p>
                </div>
              </div>
            )}

            {document?.status === 'FAILED' && (
              <div className="text-center py-12">
                <XCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
                <p className="text-slate-900 font-medium">Generation Failed</p>
                <p className="text-sm text-slate-500 mt-2">{document.error_message || 'An error occurred'}</p>
                <p className="text-sm text-emerald-600 mt-2">Your credit has been refunded.</p>
                <Button className="mt-6" onClick={() => navigate('/clearform/create')}>
                  <RefreshCw className="w-4 h-4 mr-2" /> Try Again
                </Button>
              </div>
            )}

            {document?.status === 'COMPLETED' && document?.content_markdown && (
              <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="grid w-full grid-cols-2 mb-4">
                  <TabsTrigger value="preview" className="flex items-center gap-2" data-testid="tab-preview">
                    <Eye className="w-4 h-4" /> PDF Preview
                  </TabsTrigger>
                  <TabsTrigger value="text" className="flex items-center gap-2" data-testid="tab-text">
                    <FileCode className="w-4 h-4" /> Text View
                  </TabsTrigger>
                </TabsList>

                {/* PDF Preview Tab */}
                <TabsContent value="preview" className="mt-0">
                  <div className="bg-slate-100 rounded-lg p-4">
                    {pdfLoading && (
                      <div className="flex items-center justify-center py-12">
                        <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
                        <span className="ml-2 text-slate-600">Loading PDF...</span>
                      </div>
                    )}

                    {pdfError && (
                      <div className="text-center py-12">
                        <XCircle className="w-8 h-8 text-red-400 mx-auto mb-2" />
                        <p className="text-slate-600">{pdfError}</p>
                        <Button variant="outline" size="sm" className="mt-4" onClick={loadPdf}>
                          <RefreshCw className="w-4 h-4 mr-2" /> Retry
                        </Button>
                      </div>
                    )}

                    {pdfUrl && !pdfLoading && !pdfError && (
                      <div className="flex flex-col items-center">
                        {/* PDF Controls */}
                        <div className="flex items-center gap-4 mb-4 p-2 bg-white rounded-lg shadow-sm">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={goToPrevPage}
                            disabled={pageNumber <= 1}
                            data-testid="pdf-prev-page"
                          >
                            <ChevronLeft className="w-4 h-4" />
                          </Button>
                          <span className="text-sm text-slate-600 min-w-[100px] text-center">
                            Page {pageNumber} of {numPages || '?'}
                          </span>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={goToNextPage}
                            disabled={pageNumber >= (numPages || 1)}
                            data-testid="pdf-next-page"
                          >
                            <ChevronRight className="w-4 h-4" />
                          </Button>
                          <div className="w-px h-6 bg-slate-200" />
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={zoomOut}
                            disabled={scale <= 0.5}
                            data-testid="pdf-zoom-out"
                          >
                            <ZoomOut className="w-4 h-4" />
                          </Button>
                          <span className="text-sm text-slate-600 min-w-[60px] text-center">
                            {Math.round(scale * 100)}%
                          </span>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={zoomIn}
                            disabled={scale >= 2.5}
                            data-testid="pdf-zoom-in"
                          >
                            <ZoomIn className="w-4 h-4" />
                          </Button>
                        </div>

                        {/* PDF Document */}
                        <div 
                          className="bg-white shadow-lg rounded overflow-auto max-h-[70vh]"
                          data-testid="pdf-container"
                        >
                          <Document
                            file={pdfUrl}
                            onLoadSuccess={onDocumentLoadSuccess}
                            onLoadError={onDocumentLoadError}
                            loading={
                              <div className="flex items-center justify-center p-8">
                                <Loader2 className="w-6 h-6 animate-spin text-emerald-500" />
                              </div>
                            }
                          >
                            <Page
                              pageNumber={pageNumber}
                              scale={scale}
                              renderTextLayer={true}
                              renderAnnotationLayer={true}
                            />
                          </Document>
                        </div>
                      </div>
                    )}
                  </div>
                </TabsContent>

                {/* Text View Tab */}
                <TabsContent value="text" className="mt-0">
                  <div 
                    className="prose prose-slate max-w-none"
                    data-testid="document-content"
                  >
                    <pre className="whitespace-pre-wrap font-sans text-slate-800 bg-slate-50 p-6 rounded-lg">
                      {cleanMarkdown(document.content_markdown)}
                    </pre>
                  </div>
                </TabsContent>
              </Tabs>
            )}
          </CardContent>
        </Card>

        {/* Actions */}
        {document?.status === 'COMPLETED' && (
          <div className="flex justify-end mt-6">
            <Button variant="ghost" className="text-red-600 hover:text-red-700 hover:bg-red-50" onClick={handleArchive}>
              <Trash2 className="w-4 h-4 mr-2" /> Archive Document
            </Button>
          </div>
        )}
      </main>
    </div>
  );
};

export default ClearFormDocumentPage;
