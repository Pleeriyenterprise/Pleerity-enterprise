import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { clientAPI } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { UpgradeRequired } from '../components/UpgradePrompt';
import EmptyState from '../components/EmptyState';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { 
  FileText, 
  Upload, 
  ArrowLeft, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Sparkles,
  Calendar,
  User,
  Building2,
  Hash,
  AlertTriangle,
  RefreshCw,
  Eye,
  Edit3,
  Check,
  X,
  Shield,
  Wrench,
  Award,
  FileCheck,
  Files
} from 'lucide-react';

const DocumentsPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { hasFeature } = useEntitlements();
  const [documents, setDocuments] = useState([]);
  const [properties, setProperties] = useState([]);
  const [requirements, setRequirements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(null);
  const [reviewModal, setReviewModal] = useState(null);
  const [applying, setApplying] = useState(false);
  const [editedData, setEditedData] = useState({});
  const [upgradeRequiredDetail, setUpgradeRequiredDetail] = useState(null);
  const [uploadForm, setUploadForm] = useState({
    property_id: '',
    requirement_id: '',
    file: null
  });
  const [filterPropertyId, setFilterPropertyId] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [confirmDetailsModal, setConfirmDetailsModal] = useState(null);
  const [confirmExpiryDate, setConfirmExpiryDate] = useState('');
  const [confirmIssueDate, setConfirmIssueDate] = useState('');
  const [confirmCertificateNumber, setConfirmCertificateNumber] = useState('');
  const [confirmDetailsSaving, setConfirmDetailsSaving] = useState(false);
  const [extractingDocumentId, setExtractingDocumentId] = useState(null);
  const extractingContextRef = useRef(null);
  const pollRef = useRef(null);
  const timeoutRef = useRef(null);

  useEffect(() => {
    fetchData();
  }, []);

  // Pre-fill confirm modal from extraction when document_id is available (e.g. after upload)
  useEffect(() => {
    if (!confirmDetailsModal?.document_id) return;
    let cancelled = false;
    api.get(`/documents/${confirmDetailsModal.document_id}/extraction`)
      .then((res) => {
        if (cancelled) return;
        const ext = res.data?.extraction?.data || res.data?.extraction?.extracted || {};
        if (ext.expiry_date) setConfirmExpiryDate(String(ext.expiry_date).slice(0, 10));
        if (ext.issue_date) setConfirmIssueDate(String(ext.issue_date).slice(0, 10));
        if (ext.certificate_number) setConfirmCertificateNumber(ext.certificate_number);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [confirmDetailsModal?.document_id]);

  // Poll extraction status after upload; open confirm modal when completed or failed (or timeout)
  useEffect(() => {
    if (!extractingDocumentId || !extractingContextRef.current) return;
    const ctx = extractingContextRef.current;
    const POLL_INTERVAL_MS = 2500;
    const TIMEOUT_MS = 90000;

    const clearTimersOnly = () => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    };

    const stopPolling = () => {
      clearTimersOnly();
      setExtractingDocumentId(null);
      extractingContextRef.current = null;
    };

    const openConfirmModal = (extractionFailed = false, extractionErrorCode = null) => {
      stopPolling();
      setConfirmExpiryDate('');
      setConfirmIssueDate('');
      setConfirmCertificateNumber('');
      setConfirmDetailsModal({
        ...ctx,
        document_id: extractingDocumentId,
        extractionFailed,
        extractionErrorCode,
      });
      fetchData();
    };

    const poll = async () => {
      try {
        const res = await api.get(`/documents/${extractingDocumentId}/extraction`);
        const status = res.data?.extraction?.status;
        if (status === 'completed') {
          openConfirmModal(false);
          return;
        }
        if (status === 'failed') {
          openConfirmModal(true, res.data?.extraction?.error_code || null);
          return;
        }
      } catch {
        // keep polling on network error
      }
    };

    pollRef.current = setInterval(poll, POLL_INTERVAL_MS);
    poll();

    timeoutRef.current = setTimeout(() => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
      timeoutRef.current = null;
      openConfirmModal(true, 'TIMEOUT');
      toast.info('Extraction is taking longer than expected. You can enter details manually.');
    }, TIMEOUT_MS);

    // Cleanup: only clear timers so a new upload's context in the ref is not wiped before the next effect runs
    return clearTimersOnly;
  }, [extractingDocumentId]);

  const fetchData = async () => {
    try {
      const [docsRes, propsRes, reqsRes] = await Promise.all([
        api.get('/documents'),
        clientAPI.getProperties(),
        clientAPI.getRequirements()
      ]);
      setDocuments(docsRes.data.documents || []);
      setProperties(propsRes.data.properties || []);
      setRequirements(reqsRes.data.requirements || []);
    } catch (error) {
      toast.error('Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setUploadForm({ ...uploadForm, file });
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!uploadForm.file || !uploadForm.property_id || !uploadForm.requirement_id) {
      toast.error('Please fill all fields');
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadForm.file);
      formData.append('property_id', uploadForm.property_id);
      formData.append('requirement_id', uploadForm.requirement_id);

      const res = await api.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      toast.success('Document uploaded. Extracting details…');
      const documentId = res.data?.document_id;
      const prop = properties.find(p => p.property_id === uploadForm.property_id);
      const req = requirements.find(r => r.requirement_id === uploadForm.requirement_id);
      extractingContextRef.current = {
        property_id: uploadForm.property_id,
        property_name: prop ? `${prop.address_line_1 || ''}, ${prop.city || ''}`.trim() || prop.property_id : uploadForm.property_id,
        requirement_id: uploadForm.requirement_id,
        requirement_type: req?.description || req?.requirement_type || uploadForm.requirement_id,
      };
      setExtractingDocumentId(documentId);
      setConfirmExpiryDate('');
      setConfirmIssueDate('');
      setConfirmCertificateNumber('');
      setUploadForm({ property_id: '', requirement_id: '', file: null });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to upload document');
    } finally {
      setUploading(false);
    }
  };

  const analyzeDocument = async (documentId) => {
    setAnalyzing(documentId);
    setUpgradeRequiredDetail(null);
    try {
      const returnAdvanced = hasFeature('ai_extraction_advanced');
      const response = await api.post(`/documents/analyze/${documentId}`, null, {
        params: { return_advanced: returnAdvanced }
      });
      
      if (response.data.extraction?.status === 'completed' || response.data.success) {
        toast.success('Document analyzed successfully');
        // Update the document in state
        setDocuments(docs => docs.map(d => 
          d.document_id === documentId 
            ? { ...d, ai_extraction: response.data.extraction || { status: 'completed', data: response.data.extracted_data } }
            : d
        ));
      } else {
        toast.error(response.data.error || 'Analysis failed');
      }
    } catch (error) {
      if (error.isPlanGateDenied && error.upgradeDetail) {
        setUpgradeRequiredDetail(error.upgradeDetail);
        return;
      }
      const d = error.response?.data?.detail;
      const msg = typeof d === 'string'
        ? d
        : (d?.message && d?.hint ? `${d.message} ${d.hint}` : d?.message || (d?.hint ? `Analysis failed. ${d.hint}` : null) || 'Failed to analyze document');
      toast.error(msg);
    } finally {
      setAnalyzing(null);
    }
  };

  const openReviewModal = async (doc) => {
    let extraction = doc.ai_extraction;
    if (doc.extraction_id) {
      try {
        const res = await api.get(`/documents/${doc.document_id}/extraction`);
        extraction = res.data?.extraction || null;
      } catch (e) {
        toast.error('Failed to load extraction');
        return;
      }
    }
    const data = extraction?.data || {};
    setEditedData({
      document_type: data.document_type || data.doc_type || '',
      certificate_number: data.certificate_number || '',
      issue_date: data.issue_date || '',
      expiry_date: data.expiry_date || '',
      engineer_name: data.engineer_details?.name || data.inspector_company || data.inspector_id || '',
      engineer_registration: data.engineer_details?.registration_number || '',
      company_name: data.engineer_details?.company_name || data.inspector_company || '',
      result: data.result_summary?.overall_result || data.result || ''
    });
    setReviewModal({ ...doc, extraction });
  };

  const applyExtraction = async () => {
    if (!reviewModal) return;
    
    setApplying(true);
    try {
      // Build the confirmed data object
      const confirmedData = {
        document_type: editedData.document_type,
        certificate_number: editedData.certificate_number,
        issue_date: editedData.issue_date,
        expiry_date: editedData.expiry_date,
        engineer_details: {
          name: editedData.engineer_name,
          registration_number: editedData.engineer_registration,
          company_name: editedData.company_name
        },
        result_summary: {
          overall_result: editedData.result
        }
      };

      await api.post(`/documents/${reviewModal.document_id}/apply-extraction`, {
        confirmed_data: confirmedData
      });

      toast.success('Extraction data applied successfully');
      setReviewModal(null);
      fetchData();
    } catch (error) {
      if (error.isPlanGateDenied && error.upgradeDetail) {
        setReviewModal(null);
        setUpgradeRequiredDetail(error.upgradeDetail);
        return;
      }
      toast.error(error.response?.data?.detail || 'Failed to apply extraction');
    } finally {
      setApplying(false);
    }
  };

  const rejectExtraction = async () => {
    if (!reviewModal) return;
    
    try {
      await api.post(`/documents/${reviewModal.document_id}/reject-extraction`, {
        reason: 'User chose manual entry'
      });
      toast.info('Extraction rejected - please enter data manually');
      setReviewModal(null);
      fetchData();
    } catch (error) {
      toast.error('Failed to reject extraction');
    }
  };

  const handleConfirmDetailsSubmit = async () => {
    if (!confirmDetailsModal) return;
    const payload = {};
    if (confirmExpiryDate.trim()) payload.confirmed_expiry_date = confirmExpiryDate.trim();
    if (confirmIssueDate.trim()) payload.issue_date = confirmIssueDate.trim();
    if (confirmCertificateNumber.trim()) payload.certificate_number = confirmCertificateNumber.trim();
    if (Object.keys(payload).length === 0) {
      setConfirmDetailsModal(null);
      setConfirmExpiryDate('');
      setConfirmIssueDate('');
      setConfirmCertificateNumber('');
      return;
    }
    setConfirmDetailsSaving(true);
    try {
      await api.patch(
        `/properties/${confirmDetailsModal.property_id}/requirements/${confirmDetailsModal.requirement_id}`,
        payload
      );
      toast.success('Details saved. Calendar and reminders will use the confirmed date.');
      setConfirmDetailsModal(null);
      setConfirmExpiryDate('');
      setConfirmIssueDate('');
      setConfirmCertificateNumber('');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save details');
    } finally {
      setConfirmDetailsSaving(false);
    }
  };

  const handleConfirmDetailsSkip = () => {
    setConfirmDetailsModal(null);
    setConfirmExpiryDate('');
    setConfirmIssueDate('');
    setConfirmCertificateNumber('');
  };

  const openConfirmDetailsForDocument = (doc) => {
    if (!doc.requirement_id || !doc.property_id) return;
    const prop = properties.find(p => p.property_id === doc.property_id);
    const req = requirements.find(r => r.requirement_id === doc.requirement_id);
    setConfirmExpiryDate('');
    setConfirmIssueDate('');
    setConfirmCertificateNumber('');
    setConfirmDetailsModal({
      property_id: doc.property_id,
      property_name: prop ? `${prop.address_line_1 || ''}, ${prop.city || ''}`.trim() || prop.property_id : doc.property_id,
      requirement_id: doc.requirement_id,
      requirement_type: req?.description || req?.requirement_type || doc.requirement_id,
      document_id: doc.document_id,
      extractionFailed: doc.ai_extraction?.status === 'failed',
    });
  };

  const getStatusBadge = (status) => {
    const badges = {
      PENDING: { icon: Clock, color: 'bg-yellow-100 text-yellow-800' },
      UPLOADED: { icon: Clock, color: 'bg-blue-100 text-blue-800' },
      VERIFIED: { icon: CheckCircle, color: 'bg-green-100 text-green-800' },
      REJECTED: { icon: XCircle, color: 'bg-red-100 text-red-800' }
    };
    const badge = badges[status] || badges.PENDING;
    const Icon = badge.icon;
    return (
      <span data-testid={`doc-status-${status?.toLowerCase()}`} className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full ${badge.color}`}>
        <Icon className="w-3 h-3" />
        {status}
      </span>
    );
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return 'text-green-600';
    if (confidence >= 0.5) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getQualityBadge = (quality) => {
    const badges = {
      high: { color: 'bg-green-100 text-green-700', label: 'High Quality' },
      medium: { color: 'bg-yellow-100 text-yellow-700', label: 'Medium Quality' },
      low: { color: 'bg-red-100 text-red-700', label: 'Low Quality' }
    };
    const badge = badges[quality] || badges.low;
    return (
      <span className={`text-xs px-2 py-0.5 rounded-full ${badge.color}`}>
        {badge.label}
      </span>
    );
  };

  const getExtractionStatusBadge = (doc, extractingId = null) => {
    if (extractingId && doc.document_id === extractingId) {
      return (
        <span data-testid="extraction-status-extracting" className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded bg-blue-100 text-blue-800">
          <RefreshCw className="w-3 h-3 animate-spin" />
          Extracting…
        </span>
      );
    }
    const status = doc.extraction_status || (doc.ai_extraction?.status === 'completed'
      ? (doc.ai_extraction?.review_status === 'approved' ? 'CONFIRMED' : doc.ai_extraction?.review_status === 'rejected' ? 'REJECTED' : 'NEEDS_REVIEW')
      : doc.ai_extraction?.status === 'failed' ? 'FAILED' : 'PENDING');
    const config = {
      PENDING: { label: 'Pending', color: 'bg-gray-100 text-gray-700' },
      EXTRACTED: { label: 'Extracted', color: 'bg-teal-100 text-teal-800' },
      NEEDS_REVIEW: { label: 'Needs review', color: 'bg-amber-100 text-amber-800' },
      CONFIRMED: { label: 'Confirmed', color: 'bg-green-100 text-green-800' },
      REJECTED: { label: 'Rejected', color: 'bg-red-100 text-red-800' },
      FAILED: { label: 'Failed', color: 'bg-red-100 text-red-800' }
    };
    const { label, color } = config[status] || config.PENDING;
    return (
      <span data-testid={`extraction-status-${(status || '').toLowerCase()}`} className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded ${color}`}>
        {label}
      </span>
    );
  };

  const getReviewStatusBadge = (status) => {
    if (status === 'approved') {
      return <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">✓ Applied</span>;
    }
    if (status === 'rejected') {
      return <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">Manual Entry</span>;
    }
    return <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">Review Needed</span>;
  };

  // Helper to get engineer name from enhanced or legacy format
  const getEngineerName = (data) => {
    if (data.engineer_details?.name) return data.engineer_details.name;
    if (data.engineer_name) return data.engineer_name;
    return null;
  };

  // Helper to get result from enhanced or legacy format
  const getResult = (data) => {
    if (data.result_summary?.overall_result) return data.result_summary.overall_result;
    if (data.result) return data.result;
    return null;
  };

  const filteredRequirements = requirements.filter(r => 
    r.property_id === uploadForm.property_id
  );

  const filteredDocuments = documents.filter((doc) => {
    if (filterPropertyId && doc.property_id !== filterPropertyId) return false;
    if (filterStatus && (doc.status || '').toUpperCase() !== filterStatus.toUpperCase()) return false;
    return true;
  });

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" data-testid="documents-loading">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" data-testid="documents-page">
      {/* Header */}
      <header className="bg-midnight-blue text-white py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button 
                onClick={() => navigate('/dashboard')} 
                className="text-gray-300 hover:text-white"
                data-testid="back-to-dashboard-btn"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <h1 className="text-xl font-bold">Documents</h1>
            </div>
            <div className="flex items-center gap-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/documents/bulk-upload')}
                className="bg-transparent border-white/30 text-white hover:bg-white/10"
                data-testid="bulk-upload-nav-btn"
              >
                <Files className="w-4 h-4 mr-2" />
                Bulk Upload
              </Button>
              <span className="text-sm text-gray-300">{user?.email}</span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {upgradeRequiredDetail ? (
          <div className="flex flex-col items-center justify-center py-12" data-testid="documents-upgrade-required">
            <UpgradeRequired upgradeDetail={upgradeRequiredDetail} showBackToDashboard />
            <Button variant="ghost" className="mt-4" onClick={() => setUpgradeRequiredDetail(null)}>Continue to documents</Button>
          </div>
        ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Upload Form */}
          <div className="lg:col-span-1">
            <Card data-testid="upload-form-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Upload className="w-5 h-5" />
                  Upload Document
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleUpload} className="space-y-4" data-testid="upload-form">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Property</label>
                    <select
                      value={uploadForm.property_id}
                      onChange={(e) => setUploadForm({ ...uploadForm, property_id: e.target.value, requirement_id: '' })}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                      required
                      data-testid="property-select"
                    >
                      <option value="">Select property...</option>
                      {properties.map(p => (
                        <option key={p.property_id} value={p.property_id}>
                          {p.address_line_1}, {p.city}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Requirement</label>
                    <select
                      value={uploadForm.requirement_id}
                      onChange={(e) => setUploadForm({ ...uploadForm, requirement_id: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                      required
                      disabled={!uploadForm.property_id}
                      data-testid="requirement-select"
                    >
                      <option value="">Select requirement...</option>
                      {filteredRequirements.map(r => (
                        <option key={r.requirement_id} value={r.requirement_id}>
                          {r.description}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">File</label>
                    <input
                      type="file"
                      onChange={handleFileChange}
                      accept=".pdf,.jpg,.jpeg,.png"
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                      required
                      data-testid="file-input"
                    />
                    <p className="text-xs text-gray-500 mt-1">PDF, JPG, PNG (max 10MB)</p>
                  </div>

                  <Button type="submit" disabled={uploading} className="w-full" data-testid="upload-btn">
                    {uploading ? (
                      <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Upload className="w-4 h-4 mr-2" />
                    )}
                    Upload Document
                  </Button>
                </form>
              </CardContent>
            </Card>

            {/* Enhanced AI Analysis Info */}
            <Card className="mt-6" data-testid="ai-info-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-electric-teal" />
                  Enhanced AI Scanner
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-gray-600">
                <p className="mb-3">
                  Our AI extracts key compliance data from your certificates:
                </p>
                <ul className="space-y-2">
                  <li className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-electric-teal" />
                    <span><strong>Priority:</strong> Issue & expiry dates</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Hash className="w-4 h-4 text-electric-teal" />
                    Certificate/report numbers
                  </li>
                  <li className="flex items-center gap-2">
                    <User className="w-4 h-4 text-electric-teal" />
                    Engineer name & registration
                  </li>
                  <li className="flex items-center gap-2">
                    <Award className="w-4 h-4 text-electric-teal" />
                    Pass/Fail results & ratings
                  </li>
                </ul>
                
                <div className="mt-4 p-3 bg-amber-50 rounded-lg border border-amber-200">
                  <div className="flex items-start gap-2">
                    <Shield className="w-4 h-4 text-amber-600 mt-0.5" />
                    <div>
                      <p className="text-xs font-medium text-amber-800">AI is Assistive Only</p>
                      <p className="text-xs text-amber-700 mt-1">
                        All extracted data requires your review before being applied. 
                        Compliance status is determined by our rules engine, not AI.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="mt-3 text-xs text-gray-500">
                  <strong>Supported documents:</strong>
                  <div className="flex flex-wrap gap-1 mt-1">
                    <span className="px-2 py-0.5 bg-gray-100 rounded">Gas Safety (CP12)</span>
                    <span className="px-2 py-0.5 bg-gray-100 rounded">EICR</span>
                    <span className="px-2 py-0.5 bg-gray-100 rounded">EPC</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Documents List */}
          <div className="lg:col-span-2">
            <Card data-testid="documents-list-card">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <FileText className="w-5 h-5" />
                    Your Documents ({filteredDocuments.length}{filteredDocuments.length !== documents.length ? ` of ${documents.length}` : ''})
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {documents.length === 0 ? (
                  <EmptyState
                    icon={FileText}
                    title="No documents uploaded yet"
                    description="Upload your compliance certificates to get started"
                    testId="no-documents"
                    className="py-12"
                  />
                ) : (
                  <>
                    <div className="flex flex-wrap gap-3 mb-4">
                      <select
                        value={filterPropertyId}
                        onChange={(e) => setFilterPropertyId(e.target.value)}
                        className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-electric-teal"
                        data-testid="filter-by-property"
                      >
                        <option value="">All properties</option>
                        {properties.map((p) => (
                          <option key={p.property_id} value={p.property_id}>
                            {p.address_line_1 || p.property_id}
                          </option>
                        ))}
                      </select>
                      <select
                        value={filterStatus}
                        onChange={(e) => setFilterStatus(e.target.value)}
                        className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-electric-teal"
                        data-testid="filter-by-status"
                      >
                        <option value="">All statuses</option>
                        <option value="PENDING">Pending</option>
                        <option value="UPLOADED">Uploaded</option>
                        <option value="VERIFIED">Verified</option>
                        <option value="REJECTED">Rejected</option>
                      </select>
                      {(filterPropertyId || filterStatus) && (
                        <Button variant="ghost" size="sm" onClick={() => { setFilterPropertyId(''); setFilterStatus(''); }} data-testid="clear-filters">
                          Clear filters
                        </Button>
                      )}
                    </div>
                    {filteredDocuments.length === 0 ? (
                      <EmptyState
                        title="No documents match"
                        description="No documents match the current filters."
                        testId="no-documents-match"
                        className="py-8"
                      />
                    ) : (
                  <div className="space-y-4" data-testid="documents-list">
                    {filteredDocuments.map((doc) => (
                      <div 
                        key={doc.document_id}
                        className="border border-gray-200 rounded-lg p-4 hover:border-electric-teal transition-colors"
                        data-testid={`document-${doc.document_id}`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-3 mb-2 flex-wrap">
                              <FileText className="w-5 h-5 text-electric-teal" />
                              <span className="font-medium text-midnight-blue">
                                {doc.file_name || doc.original_filename || 'Document'}
                              </span>
                              {getStatusBadge(doc.status)}
                              {(doc.extraction_id || doc.ai_extraction || extractingDocumentId === doc.document_id) && getExtractionStatusBadge(doc, extractingDocumentId)}
                            </div>
                            <p className="text-sm text-gray-500 mb-2">
                              Uploaded: {new Date(doc.uploaded_at).toLocaleDateString()}
                            </p>
                            
                            {/* AI Extraction Results - Enhanced Display */}
                            {doc.ai_extraction?.status === 'completed' && doc.ai_extraction?.data && (
                              <div className="mt-3 p-3 bg-gradient-to-r from-teal-50 to-blue-50 rounded-lg border border-teal-100">
                                <div className="flex items-center justify-between mb-2">
                                  <div className="flex items-center gap-2">
                                    <Sparkles className="w-4 h-4 text-electric-teal" />
                                    <span className="text-sm font-medium text-electric-teal">AI Extracted Data</span>
                                    <span className={`text-xs ${getConfidenceColor(doc.ai_extraction.data.confidence_scores?.overall || 0)}`}>
                                      ({Math.round((doc.ai_extraction.data.confidence_scores?.overall || 0) * 100)}% confidence)
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-2">
                                    {doc.ai_extraction.extraction_quality && getQualityBadge(doc.ai_extraction.extraction_quality)}
                                    {getReviewStatusBadge(doc.ai_extraction.review_status)}
                                  </div>
                                </div>
                                
                                <div className="grid grid-cols-2 gap-2 text-sm">
                                  {doc.ai_extraction.data.document_type && (
                                    <div>
                                      <span className="text-gray-500">Type:</span>{' '}
                                      <span className="font-medium">{doc.ai_extraction.data.document_type}</span>
                                    </div>
                                  )}
                                  {doc.ai_extraction.data.certificate_number && (
                                    <div>
                                      <span className="text-gray-500">Cert #:</span>{' '}
                                      <span className="font-medium">{doc.ai_extraction.data.certificate_number}</span>
                                    </div>
                                  )}
                                  {doc.ai_extraction.data.issue_date && (
                                    <div>
                                      <span className="text-gray-500">Issued:</span>{' '}
                                      <span className="font-medium">{doc.ai_extraction.data.issue_date}</span>
                                    </div>
                                  )}
                                  {doc.ai_extraction.data.expiry_date && (
                                    <div className="font-semibold">
                                      <span className="text-gray-500">Expires:</span>{' '}
                                      <span className="text-electric-teal">{doc.ai_extraction.data.expiry_date}</span>
                                    </div>
                                  )}
                                  {getEngineerName(doc.ai_extraction.data) && (
                                    <div>
                                      <span className="text-gray-500">Engineer:</span>{' '}
                                      <span className="font-medium">{getEngineerName(doc.ai_extraction.data)}</span>
                                    </div>
                                  )}
                                  {getResult(doc.ai_extraction.data) && (
                                    <div>
                                      <span className="text-gray-500">Result:</span>{' '}
                                      <span className={`font-medium ${['PASS', 'SATISFACTORY'].includes(getResult(doc.ai_extraction.data)?.toUpperCase()) ? 'text-green-600' : 'text-red-600'}`}>
                                        {getResult(doc.ai_extraction.data)}
                                      </span>
                                    </div>
                                  )}
                                </div>

                                {/* Engineer registration details */}
                                {doc.ai_extraction.data.engineer_details?.registration_number && (
                                  <div className="mt-2 text-xs text-gray-500">
                                    <Wrench className="w-3 h-3 inline mr-1" />
                                    Reg: {doc.ai_extraction.data.engineer_details.registration_number}
                                    {doc.ai_extraction.data.engineer_details.registration_scheme && 
                                      ` (${doc.ai_extraction.data.engineer_details.registration_scheme})`}
                                  </div>
                                )}

                                {/* Review button if not yet reviewed (Pro only) */}
                                {hasFeature('ai_review_interface') && doc.ai_extraction.review_status === 'pending' && (
                                  <div className="mt-3 pt-3 border-t border-teal-200">
                                    <Button
                                      size="sm"
                                      onClick={() => openReviewModal(doc)}
                                      className="w-full"
                                      data-testid={`review-btn-${doc.document_id}`}
                                    >
                                      <FileCheck className="w-4 h-4 mr-2" />
                                      Review & Apply Data
                                    </Button>
                                  </div>
                                )}
                              </div>
                            )}
                            
                            {(doc.extraction_status === 'EXTRACTED' || doc.extraction_status === 'NEEDS_REVIEW') && (
                              <div className="mt-3 p-3 bg-teal-50 rounded-lg border border-teal-100">
                                <p className="text-sm text-teal-800 mb-2">Evidence readiness extraction ready for review.</p>
                                {hasFeature('ai_review_interface') && (
                                  <Button size="sm" onClick={() => openReviewModal(doc)} className="w-full" data-testid={`review-extraction-btn-${doc.document_id}`}>
                                    <FileCheck className="w-4 h-4 mr-2" />
                                    Review extraction
                                  </Button>
                                )}
                              </div>
                            )}
                            {extractingDocumentId === doc.document_id && (
                              <div className="mt-3 p-3 bg-blue-50 rounded-lg border border-blue-200 flex items-center gap-2">
                                <RefreshCw className="w-4 h-4 animate-spin text-electric-teal" />
                                <span className="text-sm text-gray-700">Extracting…</span>
                              </div>
                            )}
                            {(doc.extraction_status === 'PENDING') && extractingDocumentId !== doc.document_id && (
                              <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                                <span className="text-sm text-gray-600">Extraction pending…</span>
                              </div>
                            )}
                            {(doc.ai_extraction?.status === 'failed' || doc.extraction_status === 'FAILED') && (
                              <div className="mt-3 p-3 bg-red-50 rounded-lg border border-red-100">
                                <div className="flex items-center gap-2 text-red-600">
                                  <AlertTriangle className="w-4 h-4" />
                                  <span className="text-sm">Extraction failed - enter data manually or re-upload</span>
                                </div>
                              </div>
                            )}
                          </div>
                          
                          <div className="flex flex-col items-end gap-2 ml-4">
                            {doc.requirement_id && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => openConfirmDetailsForDocument(doc)}
                                data-testid={`confirm-details-btn-${doc.document_id}`}
                              >
                                <Calendar className="w-4 h-4 mr-1" />
                                Confirm details
                              </Button>
                            )}
                            {!doc.ai_extraction?.data && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => analyzeDocument(doc.document_id)}
                                disabled={analyzing === doc.document_id}
                                data-testid={`analyze-btn-${doc.document_id}`}
                              >
                                {analyzing === doc.document_id ? (
                                  <RefreshCw className="w-4 h-4 animate-spin" />
                                ) : (
                                  <>
                                    <Sparkles className="w-4 h-4 mr-1" />
                                    Analyze
                                  </>
                                )}
                              </Button>
                            )}
                            {hasFeature('ai_review_interface') && doc.ai_extraction?.data && doc.ai_extraction.review_status !== 'pending' && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => openReviewModal(doc)}
                                data-testid={`edit-extraction-btn-${doc.document_id}`}
                              >
                                <Edit3 className="w-4 h-4" />
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
        )}
      </main>

      {/* Review Modal */}
      {reviewModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="review-modal">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-xl font-bold text-midnight-blue">Review Extracted Data</h2>
                  <p className="text-sm text-gray-500 mt-1">
                    Verify and correct the AI-extracted information before applying
                  </p>
                </div>
                <button 
                  onClick={() => setReviewModal(null)}
                  className="text-gray-400 hover:text-gray-600"
                  data-testid="close-review-modal"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
                <div className="flex items-start gap-3">
                  <Shield className="w-5 h-5 text-amber-600 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-amber-800">Important</p>
                    <p className="text-sm text-amber-700 mt-1">
                      Review all fields carefully. The <strong>expiry date</strong> will be used to update 
                      the requirement's due date. Compliance status is determined by dates, not AI.
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Document Type</label>
                  <input
                    type="text"
                    value={editedData.document_type}
                    onChange={(e) => setEditedData({...editedData, document_type: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    data-testid="edit-document-type"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Certificate Number</label>
                  <input
                    type="text"
                    value={editedData.certificate_number}
                    onChange={(e) => setEditedData({...editedData, certificate_number: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    data-testid="edit-certificate-number"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Issue Date</label>
                  <input
                    type="date"
                    value={editedData.issue_date}
                    onChange={(e) => setEditedData({...editedData, issue_date: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    data-testid="edit-issue-date"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Expiry Date <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    value={editedData.expiry_date}
                    onChange={(e) => setEditedData({...editedData, expiry_date: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal font-medium"
                    data-testid="edit-expiry-date"
                  />
                  <p className="text-xs text-gray-500 mt-1">This will update the requirement's due date</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Engineer Name</label>
                  <input
                    type="text"
                    value={editedData.engineer_name}
                    onChange={(e) => setEditedData({...editedData, engineer_name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    data-testid="edit-engineer-name"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Registration Number</label>
                  <input
                    type="text"
                    value={editedData.engineer_registration}
                    onChange={(e) => setEditedData({...editedData, engineer_registration: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    data-testid="edit-engineer-registration"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Company Name</label>
                  <input
                    type="text"
                    value={editedData.company_name}
                    onChange={(e) => setEditedData({...editedData, company_name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    data-testid="edit-company-name"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Result</label>
                  <select
                    value={editedData.result}
                    onChange={(e) => setEditedData({...editedData, result: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    data-testid="edit-result"
                  >
                    <option value="">Select...</option>
                    <option value="PASS">PASS</option>
                    <option value="FAIL">FAIL</option>
                    <option value="SATISFACTORY">SATISFACTORY</option>
                    <option value="UNSATISFACTORY">UNSATISFACTORY</option>
                  </select>
                </div>
              </div>

              <div className="flex gap-3 mt-6 pt-6 border-t">
                <Button
                  variant="outline"
                  onClick={rejectExtraction}
                  className="flex-1"
                  data-testid="reject-extraction-btn"
                >
                  <X className="w-4 h-4 mr-2" />
                  Enter Manually
                </Button>
                <Button
                  onClick={applyExtraction}
                  disabled={applying}
                  className="flex-1"
                  data-testid="apply-extraction-btn"
                >
                  {applying ? (
                    <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Check className="w-4 h-4 mr-2" />
                  )}
                  Apply & Save
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Confirm document details modal (after upload) */}
      {confirmDetailsModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="confirm-details-modal">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-midnight-blue">Confirm document details</h2>
                <button
                  onClick={handleConfirmDetailsSkip}
                  className="text-gray-400 hover:text-gray-600"
                  data-testid="close-confirm-details-modal"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <p className="text-sm text-gray-600 mb-4">
                Confirm or edit the certificate details so the calendar and reminders use the correct date.
              </p>
              {confirmDetailsModal.extractionFailed && (
                <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-4" data-testid="extraction-failed-message">
                  {confirmDetailsModal.extractionErrorCode === 'AI_NOT_CONFIGURED'
                    ? 'AI extraction is not configured on this server. Enter the details below manually.'
                    : 'Extraction could not read this file. Enter details manually or re-upload.'}
                </p>
              )}
              <div className="space-y-3 mb-6">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-0.5">Property</label>
                  <p className="text-sm text-midnight-blue font-medium">{confirmDetailsModal.property_name}</p>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-0.5">Requirement type</label>
                  <p className="text-sm text-midnight-blue font-medium">{confirmDetailsModal.requirement_type}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Expiry date</label>
                  <input
                    type="date"
                    value={confirmExpiryDate}
                    onChange={(e) => setConfirmExpiryDate(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    data-testid="confirm-expiry-date-input"
                  />
                  <p className="text-xs text-gray-500 mt-1">Confirm expiry so calendar and reminders use this date.</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Issue date</label>
                  <input
                    type="date"
                    value={confirmIssueDate}
                    onChange={(e) => setConfirmIssueDate(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    data-testid="confirm-issue-date-input"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Certificate number</label>
                  <input
                    type="text"
                    value={confirmCertificateNumber}
                    onChange={(e) => setConfirmCertificateNumber(e.target.value)}
                    placeholder="Optional"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    data-testid="confirm-certificate-number-input"
                  />
                </div>
              </div>
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  onClick={handleConfirmDetailsSkip}
                  className="flex-1"
                  data-testid="confirm-details-skip-btn"
                >
                  Skip
                </Button>
                <Button
                  onClick={handleConfirmDetailsSubmit}
                  disabled={confirmDetailsSaving}
                  className="flex-1"
                  data-testid="confirm-details-submit-btn"
                >
                  {confirmDetailsSaving ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : <Check className="w-4 h-4 mr-2" />}
                  Save
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DocumentsPage;
