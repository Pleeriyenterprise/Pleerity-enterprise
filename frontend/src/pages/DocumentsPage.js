import React, { useEffect, useMemo, useState, useRef } from 'react';
import { useNavigate, Link, useSearchParams } from 'react-router-dom';
import api, { clientAPI, parseApiError, parseStructuredApiDetail } from '../api/client';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { UpgradeRequired } from '../components/UpgradePrompt';
import EmptyState from '../components/EmptyState';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from '@/utils/portalNotifications';
import { complianceActionToastOptions } from '../utils/confidenceUxCopy';
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
  Download,
  Edit3,
  Check,
  X,
  Shield,
  Wrench,
  Award,
  FileCheck,
  Files,
  Trash2,
  Link2,
} from 'lucide-react';
import {
  PortalFilterStack,
  PortalPageShell,
  PortalSectionSkeleton,
  PortalStaleRefreshBanner,
  portalPageRoot,
} from '../components/client/ClientPortalPatterns';
import {
  fetchOperational,
  OPERATIONAL_CACHE_KEYS,
} from '../utils/clientOperationalFetch';
import PropagationNoticeCallout from '../components/client/PropagationNoticeCallout';
import { normalizeRequirementCode, documentListStatusLabel } from '../domain/presentDomain';
import { WORKSPACE_DOCUMENTS_SUBTITLE, WORKSPACE_DOCUMENTS_EMPTY_DESCRIPTION, WORKSPACE_DOCUMENTS_QUEUE_EMPTY_DESCRIPTION } from '../utils/workspaceOrientationCopy';
import {
  reviewStateLabel,
} from '../utils/evidenceReviewUi';
import {
  getClientDocumentEvidenceBadge,
  getClientExtractionPipelineBadge,
  hasAdminSupersededExtractionConfirmation,
  isExtractionConfirmationPending,
  shouldShowAiExtractedDataPanel,
  shouldShowReviewAndApplyData,
  shouldShowViewExtractedDataAction,
  getClientDocumentLinkageBadge,
  linkageReconciliationRequired,
} from '../utils/documentClientPresentation';
import {
  countAttentionRequiredDocuments,
  filterDocumentsForQueueView,
  getClientDocumentVisibilityBadge,
} from '../utils/documentVisibilityRegistry';
import { isRequirementIncludedInAttentionViews } from '../utils/portalRequirementAttention';
import { filterUploadEligibleRequirementsForProperty } from '../utils/documentEvidenceAuthority';
import { resolveClientRequirementLifecycle } from '../utils/clientRequirementLifecycle';
import { isRequirementMissingDocument } from '../utils/propertyDocumentsMatrix';
import {
  openClientDocumentFileInNewTab,
  downloadClientDocumentFile,
} from '../utils/clientDocumentPreview';

const EVIDENCE_DOCUMENT_TYPES = [
  { value: '', label: 'Select type (optional)' },
  { value: 'Gas Safety Certificate', label: 'Gas Safety Certificate' },
  { value: 'EICR', label: 'EICR' },
  { value: 'EPC', label: 'EPC' },
  { value: 'Fire Risk Assessment', label: 'Fire Risk Assessment' },
  { value: 'Legionella Assessment', label: 'Legionella Assessment' },
  { value: 'Smoke/CO evidence', label: 'Smoke/CO documentation' },
  { value: 'Other', label: 'Other (link requirement later)' },
];

const DocumentsPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const uploadDeepLinkApplied = useRef('');
  const uploadTypeLookupLoggedRef = useRef(new Set());
  const [uploadDocTypeMap, setUploadDocTypeMap] = useState({});
  const [uploadDocTypeMapLoaded, setUploadDocTypeMapLoaded] = useState(false);
  const { hasFeature } = useEntitlements();
  const [documents, setDocuments] = useState([]);
  const [properties, setProperties] = useState([]);
  const [requirements, setRequirements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [registryLoading, setRegistryLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadEvidenceBanner, setUploadEvidenceBanner] = useState(null);
  const [analyzing, setAnalyzing] = useState(null);
  const [reviewModal, setReviewModal] = useState(null);
  const [applying, setApplying] = useState(false);
  const [editedData, setEditedData] = useState({});
  const [upgradeRequiredDetail, setUpgradeRequiredDetail] = useState(null);
  /** Optional L-009 `propagation_notice` from last document mutation — read-only async honesty. */
  const [documentPropagationNotice, setDocumentPropagationNotice] = useState(null);
  const [linkageReconcileModal, setLinkageReconcileModal] = useState(null);
  const [linkageReconcileSaving, setLinkageReconcileSaving] = useState(false);
  const [linkageReconcileForm, setLinkageReconcileForm] = useState({
    property_id: '',
    requirement_id: '',
    reason: '',
  });
  const [uploadForm, setUploadForm] = useState({
    property_id: '',
    requirement_id: '',
    document_type: '',
    notes: '',
    file: null
  });
  const [filterPropertyId, setFilterPropertyId] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [queueView, setQueueView] = useState('attention');
  const [attentionRequiredCount, setAttentionRequiredCount] = useState(0);
  const [confirmDetailsModal, setConfirmDetailsModal] = useState(null);
  const [confirmExpiryDate, setConfirmExpiryDate] = useState('');
  const [confirmIssueDate, setConfirmIssueDate] = useState('');
  const [confirmCertificateNumber, setConfirmCertificateNumber] = useState('');
  const [confirmDetailsSaving, setConfirmDetailsSaving] = useState(false);
  const [extractingDocumentId, setExtractingDocumentId] = useState(null);
  const [deletingDocumentId, setDeletingDocumentId] = useState(null);
  const extractingContextRef = useRef(null);
  const pollRef = useRef(null);
  const timeoutRef = useRef(null);

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    api
      .get('/public/presentation/requirement-upload-document-type-map')
      .then((res) => {
        const m = res.data?.map;
        setUploadDocTypeMap(m && typeof m === 'object' ? m : {});
      })
      .catch(() => setUploadDocTypeMap({}))
      .finally(() => setUploadDocTypeMapLoaded(true));
  }, []);

  /**
   * Property-scoped upload deep links: /documents?property_id=&requirement_id= or &requirement_code=
   * Optional document_type= (must match a select value) or inferred from backend requirement_code → document_type map.
   * focus=upload scrolls to the form (still applied when requirement is bound without focus).
   */
  useEffect(() => {
    if (loading) return;
    const pid = searchParams.get('property_id');
    if (!pid) return;

    const ridParam = searchParams.get('requirement_id');
    const rcode = searchParams.get('requirement_code');
    const focusUpload = searchParams.get('focus') === 'upload';
    const docTypeParam = searchParams.get('document_type');
    const allowedParamType = docTypeParam && EVIDENCE_DOCUMENT_TYPES.some((o) => o.value === docTypeParam && o.value !== '');

    let resolvedRid = ridParam || '';
    const nk = rcode ? normalizeRequirementCode(rcode) : '';
    if (!resolvedRid && rcode) {
      const match = requirements.find((req) => {
        if (req.property_id !== pid) return false;
        const rc = normalizeRequirementCode(req.requirement_code || req.requirement_type);
        return rc === nk;
      });
      if (match?.requirement_id) resolvedRid = match.requirement_id;
    }

    const inferredFromMap =
      uploadDocTypeMapLoaded && nk ? String(uploadDocTypeMap[nk] || '').trim() : '';
    const inferredDocType = (allowedParamType ? docTypeParam : '') || inferredFromMap;

    if (uploadDocTypeMapLoaded && rcode && nk && !allowedParamType && !inferredFromMap) {
      const lk = `lookup:${nk}`;
      if (!uploadTypeLookupLoggedRef.current.has(lk)) {
        uploadTypeLookupLoggedRef.current.add(lk);
        api
          .get('/public/presentation/requirement-upload-document-type-lookup', { params: { requirement_code: rcode } })
          .catch(() => {});
      }
    }

    const sig = `${pid}|${resolvedRid}|${rcode || ''}|${inferredDocType}|${focusUpload}`;
    if (uploadDeepLinkApplied.current === sig) {
      if (focusUpload || resolvedRid || rcode) {
        document.getElementById('upload-form-anchor')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      return;
    }
    uploadDeepLinkApplied.current = sig;

    setUploadForm((f) => ({
      ...f,
      property_id: pid,
      ...(resolvedRid ? { requirement_id: resolvedRid } : {}),
      ...(inferredDocType ? { document_type: inferredDocType } : {}),
    }));

    if (focusUpload || resolvedRid || rcode) {
      requestAnimationFrame(() => {
        document.getElementById('upload-form-anchor')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
  }, [loading, uploadDocTypeMapLoaded, uploadDocTypeMap, searchParams, requirements]);

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
      const [docsData, propsData] = await Promise.all([
        fetchOperational(OPERATIONAL_CACHE_KEYS.documents, () =>
          api.get('/documents', { params: { projection: 'list', limit: 120 } }).then((r) => r.data),
        ).then((r) => r.data),
        fetchOperational(OPERATIONAL_CACHE_KEYS.properties, () =>
          clientAPI.getProperties().then((r) => r.data),
        ).then((r) => r.data),
      ]);
      setDocuments(docsData.documents || []);
      setAttentionRequiredCount(
        typeof docsData.attention_required_count === 'number'
          ? docsData.attention_required_count
          : countAttentionRequiredDocuments(docsData.documents || []),
      );
      setProperties(propsData.properties || []);
      setLoading(false);

      fetchOperational(OPERATIONAL_CACHE_KEYS.requirements, () =>
        clientAPI.getRequirements({ projection: 'full' }).then((r) => r.data),
      )
        .then((reqsData) => setRequirements(reqsData?.requirements || []))
        .catch(() => {});
    } catch (error) {
      toast.error('Failed to load documents');
      setLoading(false);
    }
  };

  const handleViewDocument = async (doc) => {
    try {
      await openClientDocumentFileInNewTab(api, doc.document_id);
    } catch (err) {
      toast.error(err?.message || 'Could not open document');
    }
  };

  const handleDownloadDocument = async (doc) => {
    try {
      await downloadClientDocumentFile(api, doc, {
        showSuccessToast: (msg) => toast.success(msg),
      });
    } catch (err) {
      toast.error(err?.message || 'Could not download document');
    }
  };

  const handleRemoveDocument = async (doc) => {
    if (!window.confirm(`Remove "${doc.file_name || doc.original_filename || 'this document'}"? This cannot be undone.`)) return;
    setDeletingDocumentId(doc.document_id);
    try {
      await api.delete(`/documents/${doc.document_id}`);
      toast.success('Document removed from vault—linked requirements may show as missing until a new file is uploaded.');
      await fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to remove document');
    } finally {
      setDeletingDocumentId(null);
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
    const requireRequirement = uploadForm.document_type !== 'Other';
    if (!uploadForm.file || !uploadForm.property_id) {
      toast.error('Please select property and file');
      return;
    }
    if (requireRequirement && !uploadForm.requirement_id) {
      toast.error('Please select a requirement (or choose document type "Other" to link later)');
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadForm.file);
      formData.append('property_id', uploadForm.property_id);
      if (uploadForm.requirement_id) formData.append('requirement_id', uploadForm.requirement_id);
      if (uploadForm.document_type) formData.append('document_type', uploadForm.document_type);
      if (uploadForm.notes && uploadForm.notes.trim()) formData.append('notes', uploadForm.notes.trim());

      const res = await api.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      const em = res.data?.evidence_match && typeof res.data.evidence_match === 'object' ? res.data.evidence_match : null;
      const satisfies = em?.evidence_satisfies_requirement;
      const outcome = res.data?.outcome;
      if (satisfies === false) {
        setUploadEvidenceBanner({
          document_id: res.data?.document_id,
          evidence_match: em,
          at: Date.now(),
        });
        const mismatchMsg =
          em?.mismatch_reason_text ||
          (Array.isArray(em?.user_messages) && em.user_messages.length ? em.user_messages.join(' ') : null) ||
          'Automated checks could not confirm this file matches the selected obligation.';
        toast.warning(
          `Uploaded, but evidence is not confirmed for this requirement — ${mismatchMsg} Replace the file or wait for review before treating this as satisfied.`,
          { duration: 9000 },
        );
      } else {
        setUploadEvidenceBanner(null);
        const base =
          'Document uploaded — saved to your vault. Confirm extracted dates when prompted so this requirement can move forward accurately.';
        toast.success(
          base,
          complianceActionToastOptions(outcome, {
            fallbackDescription:
              'Background scoring may refresh; requirement dates are finalized after you confirm extraction (or enter dates if extraction is unavailable).',
          }),
        );
      }
      if (typeof window !== 'undefined') {
        const detail =
          res.data?.outcome && typeof res.data.outcome === 'object'
            ? { ...res.data.outcome, report_hint_eligible: true }
            : { report_hint_eligible: true };
        window.dispatchEvent(new CustomEvent('compliance-outcome', { detail }));
      }
      const documentId = res.data?.document_id;
      const prop = properties.find(p => p.property_id === uploadForm.property_id);
      const req = requirements.find(r => r.requirement_id === uploadForm.requirement_id);
      extractingContextRef.current = {
        property_id: uploadForm.property_id,
        property_name: prop ? `${prop.address_line_1 || ''}, ${prop.city || ''}`.trim() || prop.property_id : uploadForm.property_id,
        requirement_id: uploadForm.requirement_id || '',
        requirement_type: req?.description || req?.requirement_type || uploadForm.requirement_id || '—',
      };
      setExtractingDocumentId(documentId);
      setConfirmExpiryDate('');
      setConfirmIssueDate('');
      setConfirmCertificateNumber('');
      setUploadForm({ property_id: '', requirement_id: '', document_type: '', notes: '', file: null });
      fetchData();
    } catch (error) {
      const st = error.response?.status;
      const s = parseStructuredApiDetail(error);
      if (st === 400 && s?.error_code === 'EVIDENCE_DOCUMENT_TYPE_MISMATCH') {
        toast.error(
          s.message || 'This file does not match the selected obligation.',
          { duration: 10000 },
        );
        return;
      }
      toast.error(parseApiError(error, 'Failed to upload document'));
    } finally {
      setUploading(false);
    }
  };

  const openLinkageReconcileModal = (doc) => {
    setLinkageReconcileForm({
      property_id: doc.property_id || '',
      requirement_id: '',
      reason: '',
    });
    setLinkageReconcileModal(doc);
  };

  const submitLinkageReconcile = async (action) => {
    if (!linkageReconcileModal?.document_id) return;
    setLinkageReconcileSaving(true);
    try {
      const payload = {
        action,
        reason: linkageReconcileForm.reason?.trim() || undefined,
      };
      if (action === 'link_requirement') {
        if (!linkageReconcileForm.requirement_id) {
          toast.error('Select a requirement to link');
          return;
        }
        payload.requirement_id = linkageReconcileForm.requirement_id;
      }
      if (action === 'update_property') {
        if (!linkageReconcileForm.property_id) {
          toast.error('Select a property');
          return;
        }
        payload.property_id = linkageReconcileForm.property_id;
      }
      const res = await api.post(
        `/documents/${linkageReconcileModal.document_id}/reconcile-linkage`,
        payload,
      );
      if (res.data?.propagation_notice) {
        setDocumentPropagationNotice(res.data.propagation_notice);
      }
      toast.success(
        action === 'mark_intentionally_unlinked'
          ? 'Document marked as intentionally unlinked'
          : 'Document linkage updated',
      );
      setLinkageReconcileModal(null);
      fetchData();
    } catch (error) {
      toast.error(parseApiError(error, 'Failed to reconcile document linkage'));
    } finally {
      setLinkageReconcileSaving(false);
    }
  };

  const linkageReconcileCount = useMemo(
    () => documents.filter((d) => linkageReconciliationRequired(d)).length,
    [documents],
  );

  const linkageReconcileRequirements = useMemo(() => {
    const pid = linkageReconcileForm.property_id || linkageReconcileModal?.property_id;
    if (!pid) return requirements;
    return requirements.filter((r) => r.property_id === pid);
  }, [requirements, linkageReconcileForm.property_id, linkageReconcileModal?.property_id]);

  const getLinkageBadge = (doc) => {
    const badge = getClientDocumentLinkageBadge(doc);
    if (!badge) return null;
    return (
      <span
        data-testid={`doc-linkage-${String(badge.key || '').toLowerCase()}`}
        className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full ${badge.color}`}
      >
        <Link2 className="w-3 h-3" />
        {badge.label}
      </span>
    );
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
        toast.success(
          'Extraction finished—review dates in the modal before applying so renewal and overdue logic stay accurate.',
        );
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

      const response = await api.post(`/documents/${reviewModal.document_id}/apply-extraction`, {
        confirmed_data: confirmedData
      });

      const outcome = response.data?.outcome;
      const outcomeMsg = outcome?.message;
      const base =
        outcomeMsg ||
        'Linked fields applied. This requirement can move toward verified compliance once rules confirm the dates.';
      toast.success(
        base,
        complianceActionToastOptions(outcome, {
          fallbackDescription: 'Linked fields applied—requirement status updates on the next recalculation.',
        }),
      );
      if (response.data?.outcome && typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('compliance-outcome', { detail: response.data.outcome }));
      }
      setDocumentPropagationNotice(
        response.data?.propagation_notice && typeof response.data.propagation_notice === 'object'
          ? response.data.propagation_notice
          : null,
      );
      setReviewModal(null);
      fetchData();
    } catch (error) {
      if (error.isPlanGateDenied && error.upgradeDetail) {
        setReviewModal(null);
        setUpgradeRequiredDetail(error.upgradeDetail);
        return;
      }
      const st = error.response?.status;
      const s = parseStructuredApiDetail(error);
      if (st === 409 && s?.error_code === 'EVIDENCE_MATCH_BLOCKS_APPLY') {
        toast.error(
          s.message ||
            'The confirmed extraction does not match the linked obligation. Relink the document or ask an administrator to review.',
          { duration: 12000 },
        );
        return;
      }
      toast.error(parseApiError(error, 'Failed to apply extraction'));
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
      if (confirmDetailsModal.document_id && !confirmDetailsModal.extractionFailed) {
        if (!confirmExpiryDate.trim()) {
          toast.error('Please confirm an expiry date before saving.');
          return;
        }
        let extractionPayload = {};
        try {
          const extRes = await api.get(`/documents/${confirmDetailsModal.document_id}/extraction`);
          const d = extRes.data?.extraction?.data || {};
          extractionPayload = {
            document_type: d.document_type || d.doc_type || '',
            certificate_number: confirmCertificateNumber.trim() || d.certificate_number || '',
            issue_date: confirmIssueDate.trim() || d.issue_date || '',
            expiry_date: confirmExpiryDate.trim() || d.expiry_date || '',
            engineer_details:
              typeof d.engineer_details === 'object' && d.engineer_details !== null ? d.engineer_details : {},
            result_summary:
              typeof d.result_summary === 'object' && d.result_summary !== null ? d.result_summary : {},
            confidence_scores:
              typeof d.confidence_scores === 'object' && d.confidence_scores !== null
                ? d.confidence_scores
                : undefined,
          };
        } catch (_) {
          extractionPayload = {
            document_type: '',
            certificate_number: confirmCertificateNumber.trim(),
            issue_date: confirmIssueDate.trim(),
            expiry_date: confirmExpiryDate.trim(),
            engineer_details: {},
            result_summary: {},
          };
        }
        const response = await api.post(`/documents/${confirmDetailsModal.document_id}/apply-extraction`, {
          confirmed_data: extractionPayload,
        });
        const outcome = response.data?.outcome;
        toast.success(
          outcome?.message ||
            'Dates applied — this document is marked confirmed and linked fields are updated.',
          complianceActionToastOptions(outcome, {
            fallbackDescription: 'Compliance refreshes on the next recalculation.',
          }),
        );
        if (response.data?.outcome && typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('compliance-outcome', { detail: response.data.outcome }));
        }
        setDocumentPropagationNotice(
          response.data?.propagation_notice && typeof response.data.propagation_notice === 'object'
            ? response.data.propagation_notice
            : null,
        );
      } else {
        await api.patch(
          `/properties/${confirmDetailsModal.property_id}/requirements/${confirmDetailsModal.requirement_id}`,
          payload,
        );
        toast.success(
          'Details saved. Calendar and reminders now use these dates—overdue views update on the next compliance recalculation.',
        );
        if (confirmDetailsModal.property_id && typeof window !== 'undefined') {
          window.dispatchEvent(
            new CustomEvent('compliance-outcome', { detail: { property_id: confirmDetailsModal.property_id } }),
          );
        }
      }
      setConfirmDetailsModal(null);
      setConfirmExpiryDate('');
      setConfirmIssueDate('');
      setConfirmCertificateNumber('');
      fetchData();
    } catch (error) {
      toast.error(parseApiError(error, 'Failed to save details'));
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

  const getStatusBadge = (doc) => {
    const badge = getClientDocumentEvidenceBadge(doc);
    const iconByKey = {
      REJECTED: XCircle,
      VERIFIED: CheckCircle,
      ACCEPTED_UNVERIFIED: Shield,
      UNDER_REVIEW: Clock,
      NEEDS_INFORMATION: AlertTriangle,
      EXTRACTION_PENDING: AlertTriangle,
      PROCESSING: RefreshCw,
    };
    const Icon = iconByKey[badge.key] || Clock;
    const externallyVerified = badge.key === 'VERIFIED' && String(doc?.assurance_tier || '').toUpperCase() === 'EXTERNALLY_VERIFIED';
    return (
      <span
        data-testid={`doc-status-${String(badge.key || '').toLowerCase()}`}
        title={externallyVerified ? 'Externally verified assurance' : undefined}
        className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full ${badge.color}`}
      >
        <Icon className="w-3 h-3" />
        {badge.label}
        {externallyVerified ? <Award className="w-3 h-3 shrink-0" aria-hidden /> : null}
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
    const pipeline = getClientExtractionPipelineBadge(doc, extractingId);
    if (!pipeline) return null;
    const isSpinning = extractingId && doc.document_id === extractingId;
    return (
      <span
        data-testid={`extraction-status-${pipeline.label.replace(/\s+/g, '-').toLowerCase()}`}
        className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded ${pipeline.color}`}
      >
        {isSpinning ? <RefreshCw className="w-3 h-3 animate-spin" /> : null}
        {pipeline.label}
      </span>
    );
  };

  const getReviewStatusBadge = (doc, status) => {
    if (hasAdminSupersededExtractionConfirmation(doc)) {
      return <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">Confirmed by review</span>;
    }
    if (status === 'approved') {
      return <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">✓ Applied</span>;
    }
    if (status === 'rejected') {
      return <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">Manual Entry</span>;
    }
    const u = String(status || '').toUpperCase();
    if (u === 'AWAITING_USER_CONFIRM') {
      return <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">Awaiting confirmation</span>;
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

  const filteredRequirements = useMemo(
    () => filterUploadEligibleRequirementsForProperty(uploadForm.property_id, requirements),
    [requirements, uploadForm.property_id],
  );

  const requirementsNeedingDocuments = useMemo(
    () =>
      requirements.filter((r) => {
        if (!isRequirementIncludedInAttentionViews(r)) return false;
        if (resolveClientRequirementLifecycle(r).state !== 'ACTION_REQUIRED') return false;
        const ev = String(r.evidence_state || '').toUpperCase();
        return (
          isRequirementMissingDocument(r) ||
          ev === 'AWAITING_USER_CONFIRM' ||
          ev === 'MISMATCH_FLAGGED' ||
          ev === 'MISSING'
        );
      }).length,
    [requirements],
  );

  const requirementsAwaitingInternalReview = useMemo(
    () =>
      requirements.filter((r) => {
        if (!isRequirementIncludedInAttentionViews(r)) return false;
        return resolveClientRequirementLifecycle(r).state === 'PENDING_REVIEW';
      }).length,
    [requirements],
  );

  const requirementsAwaitingEvidenceConfirm = useMemo(
    () =>
      requirements.filter((r) => {
        if (!isRequirementIncludedInAttentionViews(r)) return false;
        return String(r.evidence_state || '').toUpperCase() === 'AWAITING_USER_CONFIRM';
      }).length,
    [requirements],
  );

  const requirementsEvidenceMismatch = useMemo(
    () =>
      requirements.filter((r) => {
        if (!isRequirementIncludedInAttentionViews(r)) return false;
        return String(r.evidence_state || '').toUpperCase() === 'MISMATCH_FLAGGED';
      }).length,
    [requirements],
  );

  const selectedUploadRequirementLabel = useMemo(() => {
    if (!uploadForm.requirement_id) return '';
    const r = requirements.find((x) => x.requirement_id === uploadForm.requirement_id);
    if (!r) return '';
    return String(r.display_label || r.description || r.requirement_type || r.requirement_code || '').trim();
  }, [uploadForm.requirement_id, requirements]);

  const filteredDocuments = useMemo(() => {
    const queueFiltered = filterDocumentsForQueueView(documents, queueView);
    return queueFiltered.filter((doc) => {
      if (filterPropertyId && doc.property_id !== filterPropertyId) return false;
      if (filterStatus && (doc.status || '').toUpperCase() !== filterStatus.toUpperCase()) return false;
      return true;
    });
  }, [documents, queueView, filterPropertyId, filterStatus]);

  const attentionCount = attentionRequiredCount || countAttentionRequiredDocuments(documents);

  if (loading && documents.length === 0) {
    return (
      <PortalPageShell
        title="Document operations"
        subtitle={WORKSPACE_DOCUMENTS_SUBTITLE}
        refreshing={refreshing}
        testId="documents-loading"
      >
        <PortalSectionSkeleton rows={6} />
      </PortalPageShell>
    );
  }

  return (
    <div className={portalPageRoot} data-testid="documents-page">
      <PortalStaleRefreshBanner refreshing={refreshing} />
      {registryLoading ? (
        <p className="text-xs text-gray-500 mb-3" data-testid="documents-registry-loading">
          Loading property and requirement registry…
        </p>
      ) : null}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-6">
        <div className="flex items-start gap-3 min-w-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/dashboard'))}
            className="text-gray-600 hover:text-midnight-blue shrink-0 mt-0.5"
            data-testid="back-to-dashboard-btn"
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div className="min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold text-midnight-blue">Document operations</h1>
            <p className="text-sm text-gray-500 mt-0.5">{WORKSPACE_DOCUMENTS_SUBTITLE}</p>
            {attentionCount > 0 ? (
              <p className="text-xs text-amber-800 mt-1" data-testid="documents-attention-count">
                {attentionCount} {attentionCount === 1 ? 'document needs' : 'documents need'} operator action.
              </p>
            ) : null}
          </div>
        </div>
        <Button
          variant="outline"
          className="w-full sm:w-auto min-h-11 shrink-0"
          onClick={() => navigate('/documents/bulk-upload')}
          data-testid="bulk-upload-nav-btn"
        >
          <Files className="w-4 h-4 mr-2 shrink-0" />
          Bulk upload
        </Button>
      </div>

      <div className="max-w-7xl mx-auto w-full">
        {documentPropagationNotice ? (
          <PropagationNoticeCallout
            className="mb-6"
            notice={documentPropagationNotice}
            onDismiss={() => setDocumentPropagationNotice(null)}
          />
        ) : null}
        {linkageReconcileCount > 0 && (
          <div
            className="mb-6 rounded-xl border border-orange-200 bg-orange-50/90 px-4 py-3"
            data-testid="documents-linkage-reconciliation-banner"
          >
            <p className="text-sm text-orange-950">
              <span className="font-semibold">{linkageReconcileCount}</span>{' '}
              {linkageReconcileCount === 1 ? 'document needs' : 'documents need'} requirement linkage reconciliation.
              Use <strong>Resolve linkage</strong> on each row — link to a requirement, or mark as intentionally unlinked
              for non-compliance files.
            </p>
          </div>
        )}
        {requirementsNeedingDocuments > 0 && (
          <div
            className="mb-6 rounded-xl border border-amber-200 bg-amber-50/90 px-4 py-3 flex flex-col gap-3"
            data-testid="documents-missing-requirements-banner"
          >
            <p className="text-sm text-amber-950">
              <span className="font-semibold">{requirementsNeedingDocuments}</span>{' '}
              {requirementsNeedingDocuments === 1 ? 'requirement currently has' : 'requirements currently have'} no
              uploaded evidence (from the requirement list on this page).
            </p>
            <p className="text-xs text-amber-900/90 max-w-prose">
              Command Center may show a different number for “missing evidence” because it uses your latest{' '}
              <strong>compliance score snapshot</strong> (portfolio-wide, score-impacting count)—not this page’s live
              filter alone.
            </p>
            <div className="flex flex-col sm:flex-row gap-2 shrink-0">
            <Button variant="outline" size="sm" className="border-amber-300 shrink-0 min-h-10" asChild>
              <Link to="/requirements?status=OVERDUE_OR_MISSING">View affected requirements</Link>
            </Button>
            <Button variant="ghost" size="sm" className="text-amber-950 shrink-0 min-h-10" asChild>
              <Link to="/compliance-score">How score counts missing evidence</Link>
            </Button>
            </div>
          </div>
        )}
        {requirementsAwaitingInternalReview > 0 && (
          <div
            className="mb-6 rounded-xl border border-amber-200 bg-amber-50/90 px-4 py-3"
            data-testid="documents-awaiting-review-banner"
          >
            <p className="text-sm text-amber-950">
              <span className="font-semibold">{requirementsAwaitingInternalReview}</span>{' '}
              {requirementsAwaitingInternalReview === 1 ? 'requirement has' : 'requirements have'} evidence submitted
              and awaiting review (no further upload required unless we request it).
            </p>
          </div>
        )}
        {requirementsAwaitingEvidenceConfirm > 0 && (
          <div
            className="mb-6 rounded-xl border border-teal-200 bg-teal-50/90 px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
            data-testid="documents-awaiting-confirm-banner"
          >
            <p className="text-sm text-teal-950">
              <span className="font-semibold">{requirementsAwaitingEvidenceConfirm}</span>{' '}
              {requirementsAwaitingEvidenceConfirm === 1 ? 'requirement has' : 'requirements have'} a file uploaded with
              extracted dates that still need your confirmation before they fully apply.
            </p>
            <Button variant="outline" size="sm" className="border-teal-300 shrink-0 min-h-10" asChild>
              <a href="#upload-form-anchor">Review on this page</a>
            </Button>
          </div>
        )}
        {requirementsEvidenceMismatch > 0 && (
          <div
            className="mb-6 rounded-xl border border-red-200 bg-red-50/90 px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
            data-testid="documents-mismatch-banner"
          >
            <p className="text-sm text-red-950">
              <span className="font-semibold">{requirementsEvidenceMismatch}</span>{' '}
              {requirementsEvidenceMismatch === 1 ? 'upload may' : 'uploads may'} not match the selected requirement
              (wrong document type detected). Open the document row to review or re-upload.
            </p>
            <Button variant="outline" size="sm" className="border-red-300 shrink-0 min-h-10" asChild>
              <a href="#upload-form-anchor">Go to documents</a>
            </Button>
          </div>
        )}
        {uploadEvidenceBanner?.evidence_match && (
          <div
            className="mb-6 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3"
            data-testid="upload-evidence-match-warning"
          >
            <div className="text-sm text-amber-950">
              <p className="font-semibold">Latest upload: evidence not confirmed for the selected requirement</p>
              <p className="mt-1 text-amber-900">
                {uploadEvidenceBanner.evidence_match.mismatch_reason_text ||
                  (Array.isArray(uploadEvidenceBanner.evidence_match.user_messages)
                    ? uploadEvidenceBanner.evidence_match.user_messages.join(' ')
                    : null) ||
                  'Do not treat this upload as satisfying the obligation until extraction is confirmed or an administrator has reviewed it.'}
              </p>
              {uploadEvidenceBanner.document_id && (
                <p className="mt-1 text-xs font-mono text-amber-800">Document {uploadEvidenceBanner.document_id}</p>
              )}
            </div>
            <div className="flex flex-col gap-2 shrink-0">
              <Button variant="outline" size="sm" className="border-amber-400" asChild>
                <a href="#upload-form-anchor">Replace file</a>
              </Button>
              <Button variant="ghost" size="sm" className="text-amber-950" onClick={() => setUploadEvidenceBanner(null)}>
                Dismiss
              </Button>
            </div>
          </div>
        )}
        {upgradeRequiredDetail ? (
          <div className="flex flex-col items-center justify-center py-12" data-testid="documents-upgrade-required">
            <UpgradeRequired upgradeDetail={upgradeRequiredDetail} showBackToDashboard />
            <Button variant="ghost" className="mt-4" onClick={() => setUpgradeRequiredDetail(null)}>Continue to documents</Button>
          </div>
        ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Upload Form */}
          <div className="lg:col-span-1">
            <Card id="upload-form-anchor" data-testid="upload-form-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Upload className="w-5 h-5 shrink-0" />
                  Upload document
                </CardTitle>
                <p className="text-sm text-gray-500 mt-1">
                  This document is required to keep the selected property compliant once linked and verified. Need help?{' '}
                  <Link to="/help?article=uploading-evidence" className="text-electric-teal hover:underline">
                    Uploading documents
                  </Link>{' '}
                  in Help Centre.
                </p>
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
                      required={uploadForm.document_type !== 'Other'}
                      disabled={!uploadForm.property_id}
                      data-testid="requirement-select"
                    >
                      <option value="">{uploadForm.document_type === 'Other' ? 'Link later (optional)' : 'Select requirement...'}</option>
                      {filteredRequirements.map(r => (
                        <option key={r.requirement_id} value={r.requirement_id}>
                          {r.display_label || r.description || r.requirement_type || r.requirement_code || r.requirement_id}
                        </option>
                      ))}
                    </select>
                    {uploadForm.property_id && filteredRequirements.length === 0 ? (
                      <p className="text-xs text-amber-800 mt-2" data-testid="upload-requirement-empty-notice">
                        No upload targets for this property right now. Verified evidence is in Property → Documents (Evidence Registry).
                      </p>
                    ) : null}
                    {selectedUploadRequirementLabel ? (
                      <p className="text-xs text-midnight-blue font-medium mt-2" data-testid="upload-requirement-context">
                        Uploading this will update: {selectedUploadRequirementLabel}
                      </p>
                    ) : null}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Document type (optional)</label>
                    <select
                      value={uploadForm.document_type}
                      onChange={(e) => setUploadForm({ ...uploadForm, document_type: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                      data-testid="document-type-select"
                    >
                      {EVIDENCE_DOCUMENT_TYPES.map(opt => (
                        <option key={opt.value || 'none'} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
                    <textarea
                      value={uploadForm.notes}
                      onChange={(e) => setUploadForm({ ...uploadForm, notes: e.target.value })}
                      placeholder="e.g. Annual check, contractor reference"
                      rows={2}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                      data-testid="upload-notes"
                    />
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

                  <Button type="submit" disabled={uploading} className="w-full bg-electric-teal hover:bg-electric-teal/90 text-white" data-testid="upload-btn">
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
                    Your operations queue ({filteredDocuments.length}{filteredDocuments.length !== documents.length ? ` of ${documents.length}` : ''})
                  </span>
                </CardTitle>
                <p className="text-sm text-gray-500 mt-1">
                  Default view shows documents needing action. Settled evidence is in Property → Documents (Evidence Registry).
                  Upload ≠ verified; confirm extracted details before requirements treat files as final evidence.
                </p>
              </CardHeader>
              <CardContent>
                {documents.length === 0 ? (
                  <EmptyState
                    icon={FileText}
                    title="No documents uploaded yet"
                    description={WORKSPACE_DOCUMENTS_EMPTY_DESCRIPTION}
                    testId="no-documents"
                    className="py-12"
                  />
                ) : (
                  <>
                    <PortalFilterStack className="mb-4">
                      <select
                        value={queueView}
                        onChange={(e) => setQueueView(e.target.value)}
                        className="w-full md:w-auto min-h-11 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-electric-teal font-medium"
                        data-testid="filter-queue-view"
                      >
                        <option value="attention">Needs action (default)</option>
                        <option value="all">All documents (searchable)</option>
                        <option value="active_evidence">Active evidence only</option>
                        <option value="operational_attachments">Operational attachments</option>
                        <option value="historical">Historical / superseded</option>
                      </select>
                      <select
                        value={filterPropertyId}
                        onChange={(e) => setFilterPropertyId(e.target.value)}
                        className="w-full md:w-auto min-h-11 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-electric-teal"
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
                        className="w-full md:w-auto min-h-11 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-electric-teal"
                        data-testid="filter-by-status"
                      >
                        <option value="">All statuses</option>
                        <option value="PENDING">Awaiting confirmation</option>
                        <option value="UPLOADED">Received (confirm to apply)</option>
                        <option value="VERIFIED">Confirmed</option>
                        <option value="REJECTED">Rejected</option>
                      </select>
                      {(filterPropertyId || filterStatus || queueView !== 'attention') && (
                        <Button variant="ghost" size="sm" className="min-h-11 w-full md:w-auto" onClick={() => { setFilterPropertyId(''); setFilterStatus(''); setQueueView('attention'); }} data-testid="clear-filters">
                          Clear filters
                        </Button>
                      )}
                    </PortalFilterStack>
                    {filteredDocuments.length === 0 ? (
                      <EmptyState
                        title={queueView === 'attention' ? 'Operations queue clear' : 'No documents match'}
                        description={
                          queueView === 'attention'
                            ? WORKSPACE_DOCUMENTS_QUEUE_EMPTY_DESCRIPTION
                            : 'No files match the current filters. Clear filters or switch queue view.'
                        }
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
                              {getStatusBadge(doc)}
                              {getClientDocumentVisibilityBadge(doc) ? (
                                <span className={`px-2 py-0.5 rounded text-xs font-medium ${getClientDocumentVisibilityBadge(doc).color}`}>
                                  {getClientDocumentVisibilityBadge(doc).label}
                                </span>
                              ) : null}
                              {getLinkageBadge(doc)}
                              {(doc.extraction_id || doc.ai_extraction || extractingDocumentId === doc.document_id) && getExtractionStatusBadge(doc, extractingDocumentId)}
                            </div>
                            {doc.property_id && (
                              <p className="text-sm text-gray-600 mb-1 flex items-center gap-1.5">
                                <Building2 className="w-4 h-4 text-gray-400" />
                                {(() => {
                                  const prop = properties.find(p => p.property_id === doc.property_id);
                                  return prop ? (prop.nickname || `${prop.address_line_1 || ''}, ${prop.city || ''}`.trim() || doc.property_id) : doc.property_id;
                                })()}
                              </p>
                            )}
                            <p className="text-sm text-gray-500 mb-2">
                              Uploaded: {new Date(doc.uploaded_at).toLocaleDateString()}
                            </p>
                            {doc.requirement_evidence_mismatch ? (
                              <div
                                className="mb-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950"
                                data-testid={`doc-mismatch-${doc.document_id}`}
                              >
                                <span className="font-medium">Possible wrong document for this requirement.</span>{' '}
                                {doc.requirement_evidence_mismatch_reason ||
                                  'Check the file matches the selected requirement, or correct the extracted type before applying.'}
                              </div>
                            ) : null}
                            {linkageReconciliationRequired(doc) ? (
                              <div
                                className="mb-3 rounded-lg border border-orange-300 bg-orange-50 px-3 py-2 text-sm text-orange-950"
                                data-testid={`doc-linkage-callout-${doc.document_id}`}
                              >
                                <span className="font-medium">
                                  {String(doc.document_linkage_state || '').toUpperCase() === 'BROKEN_LINKAGE'
                                    ? 'This document is linked to a requirement that is no longer active.'
                                    : 'This document is not linked to a compliance requirement.'}
                                </span>{' '}
                                Use Resolve linkage to connect it to the correct requirement, or mark it as intentionally
                                unlinked if it is not compliance evidence.
                              </div>
                            ) : null}

                            {/* AI Extraction Results - only when extraction succeeded (no false confidence when failed) */}
                            {(() => {
                              if (!shouldShowAiExtractedDataPanel(doc)) return null;
                              return (
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
                                    {getReviewStatusBadge(doc, doc.ai_extraction.review_status)}
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

                                {shouldShowReviewAndApplyData(doc) && (
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
                                {shouldShowViewExtractedDataAction(doc) && !shouldShowReviewAndApplyData(doc) && (
                                  <div className="mt-3 pt-3 border-t border-teal-200">
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={() => openReviewModal(doc)}
                                      className="w-full"
                                      data-testid={`view-extracted-data-${doc.document_id}`}
                                    >
                                      <Eye className="w-4 h-4 mr-2" />
                                      View extracted data
                                    </Button>
                                  </div>
                                )}
                              </div>
                            );
                            })()}
                            
                            {shouldShowReviewAndApplyData(doc) && !doc.ai_extraction?.data && (
                              <div className="mt-3 p-3 bg-teal-50 rounded-lg border border-teal-100">
                                <p className="text-sm text-teal-800 mb-2">Extracted document details are ready for review.</p>
                                <Button size="sm" onClick={() => openReviewModal(doc)} className="w-full" data-testid={`review-extraction-btn-${doc.document_id}`}>
                                  <FileCheck className="w-4 h-4 mr-2" />
                                  Review extraction
                                </Button>
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
                            <div className="flex items-center gap-2">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleViewDocument(doc)}
                                data-testid={`view-doc-btn-${doc.document_id}`}
                              >
                                <Eye className="w-4 h-4 mr-1" />
                                View
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleDownloadDocument(doc)}
                                data-testid={`download-doc-btn-${doc.document_id}`}
                              >
                                <Download className="w-4 h-4 mr-1" />
                                Download
                              </Button>
                              {linkageReconciliationRequired(doc) ? (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => openLinkageReconcileModal(doc)}
                                  className="border-orange-300 text-orange-900 hover:bg-orange-50"
                                  data-testid={`resolve-linkage-btn-${doc.document_id}`}
                                >
                                  <Link2 className="w-4 h-4 mr-1" />
                                  Resolve linkage
                                </Button>
                              ) : null}
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleRemoveDocument(doc)}
                                disabled={deletingDocumentId === doc.document_id}
                                className="text-red-600 border-red-200 hover:bg-red-50 hover:border-red-300"
                                data-testid={`remove-doc-btn-${doc.document_id}`}
                              >
                                {deletingDocumentId === doc.document_id ? (
                                  <RefreshCw className="w-4 h-4 animate-spin" />
                                ) : (
                                  <>
                                    <Trash2 className="w-4 h-4 mr-1" />
                                    Remove
                                  </>
                                )}
                              </Button>
                            </div>
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
                            {doc.ai_extraction?.data && !isExtractionConfirmationPending(doc) && (
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
      </div>

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

      {linkageReconcileModal && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          data-testid="linkage-reconcile-modal"
        >
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between mb-4">
              <h3 className="text-lg font-semibold text-midnight-blue">Resolve document linkage</h3>
              <Button variant="ghost" size="sm" onClick={() => setLinkageReconcileModal(null)} data-testid="close-linkage-reconcile-modal">
                <X className="w-4 h-4" />
              </Button>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              {linkageReconcileModal.file_name || 'Document'} — link to a compliance requirement or mark as intentionally
              unlinked (non-compliance file).
            </p>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Property</label>
                <select
                  value={linkageReconcileForm.property_id}
                  onChange={(e) => setLinkageReconcileForm({ ...linkageReconcileForm, property_id: e.target.value, requirement_id: '' })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg"
                  data-testid="linkage-reconcile-property-select"
                >
                  <option value="">Select property…</option>
                  {properties.map((p) => (
                    <option key={p.property_id} value={p.property_id}>
                      {p.nickname || p.address_line_1 || p.property_id}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Requirement (to link)</label>
                <select
                  value={linkageReconcileForm.requirement_id}
                  onChange={(e) => setLinkageReconcileForm({ ...linkageReconcileForm, requirement_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg"
                  data-testid="linkage-reconcile-requirement-select"
                >
                  <option value="">Select requirement…</option>
                  {linkageReconcileRequirements.map((r) => (
                    <option key={r.requirement_id} value={r.requirement_id}>
                      {r.display_label || r.description || r.requirement_type || r.requirement_id}
                    </option>
                  ))}
                </select>
              </div>
              {(linkageReconcileModal.linkage_suggested_requirement_ids || []).length > 0 ? (
                <p className="text-xs text-gray-500" data-testid="linkage-suggested-requirements">
                  Suggested: {(linkageReconcileModal.linkage_suggested_requirement_ids || []).slice(0, 3).join(', ')}
                </p>
              ) : null}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Reason (optional)</label>
                <textarea
                  value={linkageReconcileForm.reason}
                  onChange={(e) => setLinkageReconcileForm({ ...linkageReconcileForm, reason: e.target.value })}
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg"
                  data-testid="linkage-reconcile-reason"
                />
              </div>
            </div>
            <div className="flex flex-col gap-2 mt-6">
              {String(linkageReconcileModal.document_linkage_state || '').toUpperCase() === 'BROKEN_LINKAGE' ? (
                <Button
                  variant="outline"
                  disabled={linkageReconcileSaving}
                  onClick={() => submitLinkageReconcile('clear_broken_linkage')}
                  data-testid="linkage-reconcile-clear-broken-btn"
                >
                  Clear broken linkage
                </Button>
              ) : null}
              <Button
                disabled={linkageReconcileSaving}
                onClick={() => submitLinkageReconcile('link_requirement')}
                data-testid="linkage-reconcile-link-btn"
              >
                {linkageReconcileSaving ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : null}
                Link to requirement
              </Button>
              <Button
                variant="outline"
                disabled={linkageReconcileSaving}
                onClick={() => submitLinkageReconcile('mark_intentionally_unlinked')}
                data-testid="linkage-reconcile-intentional-btn"
              >
                Mark intentionally unlinked
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DocumentsPage;
