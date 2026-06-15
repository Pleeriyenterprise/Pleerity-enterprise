import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { clientAPI } from '../api/client';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Label } from './ui/label';
import { toast } from '../utils/portalNotifications';
import { dispatchComplianceOutcome, toastComplianceActionOutcome } from '../utils/complianceActionOutcome';
import { summarizeSubmittedEvidenceRecord } from '../utils/complianceEvidenceSubmissionView';
import { validateDepositStructuredDeclarationFields } from '../utils/depositStructuredDeclarationValidation';
import { normalizeRequirementCode } from '../domain/presentDomain';
import { validateLeadTestingStructuredDeclarationFields } from '../utils/leadTestingStructuredValidation';
import { validateLegionellaStructuredDeclarationFields } from '../utils/legionellaStructuredValidation';
import { validateWalesOccupationContractStructuredDeclarationFields } from '../utils/walesOccupationContractStructuredValidation';
import { validateTenancyAgreementStructuredDeclarationFields } from '../utils/tenancyAgreementStructuredValidation';
import {
  evaluateStructuredDeclarationConditionalRules,
  RIGHT_TO_RENT_STRUCTURED_DECLARATION_CONDITIONAL_RULES,
} from '../utils/structuredDeclarationConditionalValidation';
import {
  dispatchSupportingUploadAttribution,
  requirementHasPersistedClientSubmission,
  resolveExistingSubmissionBannerCopy,
  resolveStaticSupportingUploadDisclaimer,
} from '../utils/clientPersistedSubmissionPresentation';
import { supportingUploadSuccessToast } from '../utils/supportingUploadToastCopy';
import RequirementEvidenceGuidancePanel from './operational/RequirementEvidenceGuidancePanel';
import { getRequirementGuidance, heroPrimaryFromCognition, sortEvidenceModesByGuidance } from '../utils/operationalCognition';
import {
  MODAL_CTA_FOCUS_FALLBACK_COPY,
  focusModalCtaTarget,
  resolveModalCtaFocusKey,
} from '../utils/requirementModalCtaFocus';

/** YYYY-MM-DD for native date input; tolerates other stored strings without coercing. */
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export function dateInputValueFromStored(raw) {
  if (raw == null || raw === '') return '';
  const s = String(raw).trim();
  return ISO_DATE_RE.test(s) ? s : '';
}

/**
 * Guided "Resolve requirement" flow: loads allowed evidence modes from registry policy,
 * then submits non-document evidence via POST /client/properties/.../compliance-evidence.
 */
export default function ComplianceEvidenceResolveModal({
  open,
  onOpenChange,
  propertyId,
  requirement,
  initialEvidenceMode = null,
  initialCtaFocusKey = null,
  onSubmitted,
}) {
  const rid = requirement?.requirement_id;
  const [loading, setLoading] = useState(false);
  const [info, setInfo] = useState(null);
  const [selectedMode, setSelectedMode] = useState('');
  const [declStatement, setDeclStatement] = useState('');
  const [declFields, setDeclFields] = useState({});
  const [cName, setCName] = useState('');
  const [cCompany, setCCompany] = useState('');
  const [cEmail, setCEmail] = useState('');
  const [cPhone, setCPhone] = useState('');
  const [cTradeType, setCTradeType] = useState('');
  const [cAccreditation, setCAccreditation] = useState('');
  const [cDate, setCDate] = useState('');
  const [cSummary, setCSummary] = useState('');
  const [inspDate, setInspDate] = useState('');
  const [inspPerson, setInspPerson] = useState('');
  const [inspAnswers, setInspAnswers] = useState({});
  const [inspNotes, setInspNotes] = useState('');
  const [supportingFiles, setSupportingFiles] = useState([]);
  const [supportingUploads, setSupportingUploads] = useState([]);
  const [supportingUploading, setSupportingUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [structuredValidationError, setStructuredValidationError] = useState('');
  const [submitSummaryRecord, setSubmitSummaryRecord] = useState(null);
  const [pendingCtaFocusKey, setPendingCtaFocusKey] = useState(null);
  const [ctaFocusFallback, setCtaFocusFallback] = useState('');
  const [ctaFocusAnnounce, setCtaFocusAnnounce] = useState('');
  const modalScrollRef = useRef(null);

  const resetLocal = useCallback(() => {
    setInfo(null);
    setSelectedMode('');
    setDeclStatement('');
    setDeclFields({});
    setCName('');
    setCCompany('');
    setCEmail('');
    setCPhone('');
    setCTradeType('');
    setCAccreditation('');
    setCDate('');
    setCSummary('');
    setInspDate('');
    setInspPerson('');
    setInspAnswers({});
    setInspNotes('');
    setSupportingFiles([]);
    setSupportingUploads([]);
    setStructuredValidationError('');
    setSubmitSummaryRecord(null);
    setPendingCtaFocusKey(null);
    setCtaFocusFallback('');
    setCtaFocusAnnounce('');
  }, []);

  useEffect(() => {
    if (!open || !propertyId || !rid) return;
    let cancelled = false;
    setLoading(true);
    resetLocal();
    clientAPI
      .getRequirementEvidenceResolution(propertyId, rid)
      .then((res) => {
        if (!cancelled) setInfo(res.data || null);
      })
      .catch((e) => {
        if (!cancelled) {
          setInfo(null);
          toast.error(e?.response?.data?.detail || 'Could not load evidence options');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, propertyId, rid, resetLocal]);

  useEffect(() => {
    if (!open || loading || !initialEvidenceMode || !info) return;
    const im = String(initialEvidenceMode).trim().toUpperCase();
    const list = (info.allowed_evidence_modes || []).filter((m) => m && m !== 'DOCUMENT_UPLOAD');
    if (list.includes(im)) setSelectedMode(im);
  }, [open, loading, initialEvidenceMode, info]);

  useEffect(() => {
    if (!open || loading || !initialCtaFocusKey || submitSummaryRecord) return undefined;
    setPendingCtaFocusKey(String(initialCtaFocusKey).trim());
  }, [open, loading, initialCtaFocusKey, submitSummaryRecord]);

  useEffect(() => {
    if (!open || loading || !info?.reopen_context) return;
    const ctx = info.reopen_context;
    const mode = String(ctx.evidence_mode || '').trim().toUpperCase();
    if (mode) setSelectedMode(mode);
    if (ctx.declaration_statement) setDeclStatement(String(ctx.declaration_statement));
    if (ctx.structured_fields_prefill && typeof ctx.structured_fields_prefill === 'object') {
      setDeclFields(ctx.structured_fields_prefill);
    }
    if (ctx.checklist_answers_prefill && typeof ctx.checklist_answers_prefill === 'object') {
      setInspAnswers(ctx.checklist_answers_prefill);
    }
    if (ctx.inspection_date) setInspDate(dateInputValueFromStored(ctx.inspection_date));
    if (ctx.responsible_person) setInspPerson(String(ctx.responsible_person));
    if (ctx.optional_notes) setInspNotes(String(ctx.optional_notes));
    const contractor = ctx.contractor_confirmation_prefill;
    if (contractor && typeof contractor === 'object') {
      if (contractor.contractor_name) setCName(String(contractor.contractor_name));
      if (contractor.company_name) setCCompany(String(contractor.company_name));
      if (contractor.contractor_email) setCEmail(String(contractor.contractor_email));
      if (contractor.contractor_phone) setCPhone(String(contractor.contractor_phone));
      if (contractor.trade_type) setCTradeType(String(contractor.trade_type));
      if (contractor.accreditation_number) setCAccreditation(String(contractor.accreditation_number));
      if (contractor.completion_date) setCDate(dateInputValueFromStored(contractor.completion_date));
      if (contractor.work_summary) setCSummary(String(contractor.work_summary));
    }
  }, [open, loading, info]);

  const guidance = useMemo(
    () => getRequirementGuidance(info || requirement),
    [info, requirement],
  );

  useEffect(() => {
    if (!open || loading || !info || selectedMode || initialEvidenceMode) return;
    const recommended = guidance?.recommended_evidence_mode;
    const list = (info.allowed_evidence_modes || []).filter((m) => m && m !== 'DOCUMENT_UPLOAD');
    if (recommended && list.includes(recommended)) {
      setSelectedMode(recommended);
    }
  }, [open, loading, info, guidance, selectedMode, initialEvidenceMode]);

  const modes = useMemo(() => {
    const raw = (info?.allowed_evidence_modes || []).filter((m) => m && m !== 'DOCUMENT_UPLOAD');
    return sortEvidenceModesByGuidance(raw, guidance);
  }, [info, guidance]);
  const primaryMode = guidance?.strongest_evidence_method && modes.includes(guidance.strongest_evidence_method)
    ? guidance.strongest_evidence_method
    : modes[0] || null;
  const secondaryModes = modes.filter((m) => m !== primaryMode);
  const cognitionEntity = info?.operational_cognition ? info : requirement;
  const cta = info?.primary_client_cta || 'Add compliance evidence';
  const modalTitle = String(info?.modal_title || 'Add compliance evidence').trim() || 'Add compliance evidence';
  const clientEvidenceDisclosure = String(info?.client_evidence_disclosure || '').trim();
  const isTenantDelivery =
    String(info?.primary_resolution_workflow || '')
      .trim()
      .toUpperCase() === 'TENANT_DELIVERY';
  const isGuidedDeclaration =
    String(info?.primary_resolution_workflow || '')
      .trim()
      .toUpperCase() === 'GUIDED_DECLARATION';
  const reqSlug = String(requirement?.requirement_type || requirement?.requirement_code || '')
    .trim()
    .toLowerCase();
  const canonicalReqCode = normalizeRequirementCode(requirement?.requirement_code || requirement?.requirement_type || '');
  const reqJur = String(requirement?.jurisdiction || requirement?.property_jurisdiction || '')
    .trim()
    .toLowerCase();
  const isRightToRentFamily = reqSlug === 'right_to_rent' || reqSlug === 'right_to_rent_checks';
  const isDepositFamily =
    reqSlug === 'deposit_pi' || reqSlug === 'deposit_prescribed_info' || reqSlug === 'tenancy_deposit_protection';
  const isWalesOccupationFamily = reqSlug === 'wales_occupation_contract' || (reqSlug === 'occupation_contract' && reqJur === 'wales');
  const isLegionella = reqSlug === 'legionella';
  const isLeadTesting = canonicalReqCode === 'lead_testing';
  const isTenancyAgreement = canonicalReqCode === 'tenancy_agreement';
  const selectedMethod = (info?.guided_methods || []).find((x) => x.evidence_mode === selectedMode) || null;
  const selectedChecklistSchema = Array.isArray(selectedMethod?.checklist_schema) ? selectedMethod.checklist_schema : [];
  const mergedRequirement = useMemo(
    () => ({ ...(requirement || {}), ...(info?.requirement || {}) }),
    [requirement, info],
  );
  const hasExistingAuthoritativeSubmission = requirementHasPersistedClientSubmission(mergedRequirement);
  const existingSubmissionBanner = useMemo(() => {
    const fromApi = String(info?.existing_submission_banner || '').trim();
    if (fromApi) return fromApi;
    return resolveExistingSubmissionBannerCopy(mergedRequirement);
  }, [info, mergedRequirement]);
  const componentGuidanceLines = useMemo(() => {
    const fromApi = Array.isArray(info?.component_guidance_lines) ? info.component_guidance_lines.filter(Boolean) : [];
    if (fromApi.length > 0) return fromApi;
    const fromGuidance = Array.isArray(guidance?.missing_actions) ? guidance.missing_actions.filter(Boolean) : [];
    return fromGuidance;
  }, [info, guidance]);
  const staticSupportingDisclaimer = resolveStaticSupportingUploadDisclaimer(requirement);
  const reviewBlocked = Boolean(
    guidance?.submitted_not_verified && !guidance?.rejected_requires_action && !guidance?.reviewer_requested_changes,
  );

  const handleGuidancePrimary = useCallback(() => {
    setCtaFocusFallback('');
    const primary = heroPrimaryFromCognition(cognitionEntity);
    const focusKey = resolveModalCtaFocusKey({
      primary,
      guidance,
      selectedMode,
    });
    const recommended = guidance?.recommended_evidence_mode;
    if (recommended && modes.includes(recommended)) {
      setSelectedMode(recommended);
    } else if (primaryMode) {
      setSelectedMode(primaryMode);
    }
    setPendingCtaFocusKey(focusKey);
  }, [cognitionEntity, guidance, modes, primaryMode, selectedMode]);

  useEffect(() => {
    if (!open || !pendingCtaFocusKey || submitSummaryRecord) return undefined;
    const timer = window.setTimeout(() => {
      const ok = focusModalCtaTarget({
        scrollRoot: modalScrollRef.current,
        ctaKey: pendingCtaFocusKey,
        onMissing: () => setCtaFocusFallback(MODAL_CTA_FOCUS_FALLBACK_COPY),
        announce: (msg) => setCtaFocusAnnounce(msg),
      });
      if (!ok) setCtaFocusFallback(MODAL_CTA_FOCUS_FALLBACK_COPY);
      setPendingCtaFocusKey(null);
    }, 120);
    return () => window.clearTimeout(timer);
  }, [open, pendingCtaFocusKey, selectedMode, submitSummaryRecord, loading, modes.length]);

  const setChecklistAnswer = (mode, id, patch) => {
    if (mode === 'STRUCTURED_DECLARATION') setStructuredValidationError('');
    const targetSetter = mode === 'STRUCTURED_DECLARATION' ? setDeclFields : setInspAnswers;
    targetSetter((prev) => {
      const prior = prev?.[id] && typeof prev[id] === 'object' ? prev[id] : {};
      return { ...prev, [id]: { ...prior, ...patch } };
    });
  };

  const toChecklistPayload = (source, schema) => {
    const out = {};
    (schema || []).forEach((row) => {
      const key = String(row?.id || '').trim();
      if (!key) return;
      const answerType = String(row?.answer_type || 'YES_NO').toUpperCase();
      const raw = source?.[key] || {};
      let answer = raw.answer;
      if ((answerType === 'YES_NO' || answerType === 'PASS_FAIL') && typeof answer === 'string') {
        if (answer === 'YES' || answer === 'PASS') answer = true;
        else if (answer === 'NO' || answer === 'FAIL') answer = false;
      }
      if (answerType === 'NUMERIC' && answer !== '' && answer != null) {
        const n = Number(answer);
        answer = Number.isFinite(n) ? n : null;
      }
      if (answerType === 'DATE' && answer !== '' && answer != null) {
        answer = String(answer).trim();
      }
      if (answerType === 'SELECT' && answer !== '' && answer != null) {
        answer = String(answer).trim();
      }
      out[key] = {
        answer: answer ?? null,
        notes: raw.notes || null,
        observation: raw.observation || null,
      };
    });
    return out;
  };

  const uploadSupportingFiles = async () => {
    if (!propertyId || supportingFiles.length === 0) return;
    setSupportingUploading(true);
    try {
      const uploaded = [];
      for (const file of supportingFiles) {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('property_id', propertyId);
        fd.append('source', 'supporting_evidence_attachment');
        fd.append('notes', `Supporting evidence attachment for ${rid}`);
        const res = await clientAPI.uploadComplianceSupportingAttachment(fd);
        if (res?.data?.document_id) {
          uploaded.push({
            document_id: res.data.document_id,
            filename: file.name,
            content_type: file.type || '',
          });
        }
      }
      setSupportingUploads((prev) => [...prev, ...uploaded]);
      setSupportingFiles([]);
      if (uploaded.length > 0) {
        toast.success(supportingUploadSuccessToast(requirement, uploaded.length));
        dispatchSupportingUploadAttribution({
          requirement_id: rid,
          property_id: propertyId,
          document_count: uploaded.length,
        });
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not upload supporting files');
    } finally {
      setSupportingUploading(false);
    }
  };

  const submit = async () => {
    if (!propertyId || !rid || !selectedMode) return;
    let body = { evidence_mode: selectedMode };
    if (selectedMode === 'STRUCTURED_DECLARATION') {
      const structuredPayload = toChecklistPayload(declFields, selectedChecklistSchema);
      const rulesFromPolicy = info?.policy?.structured_declaration_conditional_rules;
      const rules =
        Array.isArray(rulesFromPolicy) && rulesFromPolicy.length > 0
          ? rulesFromPolicy
          : isGuidedDeclaration && isRightToRentFamily
            ? RIGHT_TO_RENT_STRUCTURED_DECLARATION_CONDITIONAL_RULES
            : null;
      const condErr = evaluateStructuredDeclarationConditionalRules(rules, structuredPayload);
      const mergedErrors = [];
      if (condErr) mergedErrors.push(condErr);
      if (isDepositFamily) {
        const depErr = validateDepositStructuredDeclarationFields(structuredPayload);
        if (depErr) {
          setStructuredValidationError(depErr);
          toast.error(depErr);
          return;
        }
      }
      if (isWalesOccupationFamily) {
        const walErr = validateWalesOccupationContractStructuredDeclarationFields(structuredPayload);
        if (walErr) {
          setStructuredValidationError(walErr);
          toast.error(walErr);
          return;
        }
      }
      if (isLegionella) {
        const legErr = validateLegionellaStructuredDeclarationFields(structuredPayload);
        if (legErr) {
          mergedErrors.push(legErr);
        }
      }
      if (isLeadTesting) {
        const leadErr = validateLeadTestingStructuredDeclarationFields(structuredPayload);
        if (leadErr) {
          mergedErrors.push(leadErr);
        }
      }
      if (isTenancyAgreement) {
        const taErr = validateTenancyAgreementStructuredDeclarationFields(structuredPayload);
        if (taErr) {
          mergedErrors.push(taErr);
        }
      }
      if (mergedErrors.length > 0) {
        const mergedMessage = mergedErrors.join('\n');
        setStructuredValidationError(mergedMessage);
        toast.error(mergedMessage);
        return;
      }
      setStructuredValidationError('');
      body.structured_declaration = {
        declaration_statement: declStatement,
        structured_fields: structuredPayload,
      };
    } else if (selectedMode === 'CONTRACTOR_CONFIRMATION') {
      body.contractor_confirmation = {
        contractor_name: cName,
        completion_date: cDate,
        work_summary: cSummary,
        company_name: cCompany || null,
        contractor_email: cEmail || null,
        contractor_phone: cPhone || null,
        trade_type: cTradeType || null,
        accreditation_number: cAccreditation || null,
      };
    } else if (selectedMode === 'INSPECTION_CHECKLIST') {
      body.inspection_checklist = {
        inspection_date: inspDate,
        checklist_answers: toChecklistPayload(inspAnswers, selectedChecklistSchema),
        responsible_person: inspPerson,
        optional_notes: inspNotes || null,
      };
    } else {
      toast.error('Select an evidence method.');
      return;
    }
    body.supporting_attachment_document_ids = supportingUploads.map((x) => x.document_id);
    setSaving(true);
    try {
      const res = await clientAPI.postComplianceEvidence(propertyId, rid, body);
      const data = res?.data || {};
      const evidenceRecord =
        data.evidence_record && typeof data.evidence_record === 'object' ? data.evidence_record : null;
      const complete = toastComplianceActionOutcome(data, {
        defaultSuccess: 'Requirement recorded and compliance status is updating.',
      });
      if (complete && evidenceRecord) {
        dispatchComplianceOutcome(propertyId, { requirement_id: rid });
        setSubmitSummaryRecord(evidenceRecord);
      } else if (complete) {
        dispatchComplianceOutcome(propertyId, { requirement_id: rid });
        onOpenChange(false);
        onSubmitted?.();
      }
    } catch (e) {
      const d = e?.response?.data?.detail;
      const msg =
        typeof d === 'object' && d != null && d.message ? d.message : typeof d === 'string' ? d : 'Could not save evidence';
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const renderEvidenceModeButton = (m, { primary = false } = {}) => {
    const row = (info?.guided_methods || []).find((x) => x.evidence_mode === m) || {};
    const label = row.label || m;
    const desc = row.description || '';
    const conf = row.typical_confidence || '';
    const ver = row.verification_note || '';
    const isPrimaryRecommended = primary || m === primaryMode;
    return (
      <button
        key={m}
        type="button"
        data-testid={`guided-evidence-mode-${m}`}
        data-guided-evidence-tier={isPrimaryRecommended ? 'primary' : 'secondary'}
        onClick={() => setSelectedMode(m)}
        className={`text-left rounded-lg border p-3 transition-colors ${
          selectedMode === m
            ? 'border-electric-teal bg-teal-50/40 ring-1 ring-electric-teal/30'
            : isPrimaryRecommended
              ? 'border-teal-200 bg-teal-50/20 hover:border-teal-300'
              : 'border-gray-200 hover:border-gray-300 opacity-90'
        }`}
      >
        {isPrimaryRecommended ? (
          <p className="text-[10px] font-semibold uppercase tracking-wide text-teal-800 mb-1">Recommended path</p>
        ) : (
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Alternative — lower confidence</p>
        )}
        <p className="font-semibold text-midnight-blue text-sm">{label}</p>
        {desc ? <p className="text-xs text-gray-600 mt-1">{desc}</p> : null}
        {conf ? <p className="text-xs text-gray-500 mt-1">Typical confidence: {conf}</p> : null}
        {ver ? <p className="text-xs text-gray-500 mt-1">{ver}</p> : null}
      </button>
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        ref={modalScrollRef}
        className="max-w-lg max-h-[90vh] overflow-y-auto"
        data-testid="compliance-evidence-resolve-modal"
      >
        <DialogHeader>
          <DialogTitle>{modalTitle}</DialogTitle>
          <DialogDescription>
            {isTenantDelivery ? (
              <>
                Use structured delivery details as the main record. The Documents page (or “Upload delivery proof”
                on the requirement) is for optional supporting files only.
              </>
            ) : isGuidedDeclaration && isDepositFamily ? (
              <>
                Use the structured record for deposit protection and prescribed information. The Documents page (or
                “Upload deposit evidence” on the requirement) is for optional supporting files only.
              </>
            ) : isGuidedDeclaration && isWalesOccupationFamily ? (
              <>
                Use the structured record as the main Wales occupation contract evidence. The Documents page (or
                “Upload occupation contract” on the requirement) is for optional supporting files only.
              </>
            ) : isLegionella ? (
              <>
                Use the structured record as the main Legionella assessment evidence. The Documents page (or “Upload
                assessment report” on the requirement) is for optional supporting files only.
              </>
            ) : isGuidedDeclaration && isTenancyAgreement ? (
              <>
                Use the structured tenancy record as the primary evidence. The Documents page (or "Upload signed
                agreement" on the requirement) is for optional supporting files only.
              </>
            ) : isGuidedDeclaration ? (
              <>
                Use the structured check record as the main evidence. The Documents page (or “Upload supporting
                evidence” on the requirement) is for optional supporting files only.
              </>
            ) : (
              <>
                Choose how you want to evidence this obligation. Uploading a certificate stays on the Documents page
                (or use “Upload document” on the requirement when offered). Other methods create a compliance
                evidence record for review.
              </>
            )}
          </DialogDescription>
        </DialogHeader>
        <p className="sr-only" aria-live="polite" data-testid="modal-cta-focus-announce">
          {ctaFocusAnnounce}
        </p>
        {ctaFocusFallback ? (
          <p
            className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-md px-3 py-2"
            role="status"
            data-testid="modal-cta-focus-fallback"
          >
            {ctaFocusFallback}
          </p>
        ) : null}
        {!submitSummaryRecord && !loading && info ? (
          <RequirementEvidenceGuidancePanel
            cognitionEntity={cognitionEntity}
            onPrimaryClick={reviewBlocked ? undefined : handleGuidancePrimary}
            primaryDisabled={reviewBlocked || modes.length === 0}
            truthLines={staticSupportingDisclaimer}
            componentGuidanceLines={componentGuidanceLines}
          />
        ) : !submitSummaryRecord && !loading ? (
          <div
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 space-y-1.5 -mt-1"
            data-testid="supporting-upload-truth-banner"
          >
            <p className="text-xs font-semibold text-midnight-blue">Supporting files vs authoritative submission</p>
            {staticSupportingDisclaimer.map((line) => (
              <p key={line} className="text-xs text-slate-700">
                {line}
              </p>
            ))}
          </div>
        ) : null}
        {hasExistingAuthoritativeSubmission && existingSubmissionBanner ? (
          <p
            className="text-xs font-medium text-amber-900 bg-amber-50 border border-amber-200 rounded-md px-3 py-2"
            data-testid="existing-submission-on-file-banner"
          >
            {existingSubmissionBanner}
          </p>
        ) : null}
        {clientEvidenceDisclosure ? (
          <p className="text-sm text-gray-600 -mt-1 mb-1" data-testid="client-evidence-disclosure">
            {clientEvidenceDisclosure}
          </p>
        ) : null}
        {structuredValidationError ? (
          <p
            className="text-sm text-red-600 -mt-1 mb-1"
            data-testid="structured-declaration-validation-error"
            role="alert"
          >
            {structuredValidationError}
          </p>
        ) : null}
        {submitSummaryRecord ? (
          <div
            className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4 space-y-3"
            data-testid="compliance-evidence-submit-summary"
          >
            <p className="text-sm font-semibold text-midnight-blue">Submission recorded</p>
            <p className="text-xs text-gray-600">
              This is what we saved. Your requirement status will update after review where applicable.
            </p>
            <ul className="text-sm text-gray-800 space-y-1 list-disc list-inside" data-testid="submit-summary-lines">
              {summarizeSubmittedEvidenceRecord(submitSummaryRecord).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {!submitSummaryRecord && loading ? (
          <p className="text-sm text-gray-600">Loading allowed methods…</p>
        ) : !submitSummaryRecord && modes.length === 0 ? (
          <p className="text-sm text-gray-600">
            This requirement only accepts a document upload. Use “Upload document” instead.
          </p>
        ) : !submitSummaryRecord ? (
          <div className="space-y-4">
            <div
              className="flex flex-col gap-3"
              data-testid="guided-evidence-mode-list"
              data-modal-focus-target="modal-focus-evidence-method"
              data-modal-focus-label="Evidence method"
            >
              {primaryMode ? renderEvidenceModeButton(primaryMode, { primary: true }) : null}
              {secondaryModes.length > 0 ? (
                <details className="rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 group">
                  <summary className="text-xs font-semibold text-slate-700 cursor-pointer list-none">
                    Other evidence methods ({secondaryModes.length})
                  </summary>
                  <div className="mt-3 flex flex-col gap-3">
                    {secondaryModes.map((m) => renderEvidenceModeButton(m))}
                  </div>
                </details>
              ) : null}
            </div>
            {selectedMode === 'STRUCTURED_DECLARATION' ? (
              <div
                className="space-y-2"
                data-modal-focus-target="modal-focus-declaration-form"
                data-modal-focus-label="Declaration form"
              >
                <Label>Declaration statement</Label>
                <textarea
                  className="w-full min-h-[100px] border rounded-md p-2 text-sm"
                  value={declStatement}
                  onChange={(e) => setDeclStatement(e.target.value)}
                />
                <ChecklistEditor
                  schema={selectedChecklistSchema}
                  values={declFields}
                  onChange={(id, patch) => setChecklistAnswer('STRUCTURED_DECLARATION', id, patch)}
                />
              </div>
            ) : null}
            {selectedMode === 'CONTRACTOR_CONFIRMATION' ? (
              <div
                className="space-y-2"
                data-modal-focus-target="modal-focus-contractor-confirmation"
                data-modal-focus-label="Contractor confirmation"
              >
                <Label>Contractor name</Label>
                <input className="w-full border rounded-md p-2 text-sm" value={cName} onChange={(e) => setCName(e.target.value)} />
                <Label>Company (optional)</Label>
                <input className="w-full border rounded-md p-2 text-sm" value={cCompany} onChange={(e) => setCCompany(e.target.value)} />
                <Label>Contractor email (optional)</Label>
                <input className="w-full border rounded-md p-2 text-sm" value={cEmail} onChange={(e) => setCEmail(e.target.value)} />
                <Label>Contractor phone (optional)</Label>
                <input className="w-full border rounded-md p-2 text-sm" value={cPhone} onChange={(e) => setCPhone(e.target.value)} />
                <Label>Trade type (optional)</Label>
                <input className="w-full border rounded-md p-2 text-sm" value={cTradeType} onChange={(e) => setCTradeType(e.target.value)} />
                <Label>Accreditation number (optional)</Label>
                <input className="w-full border rounded-md p-2 text-sm" value={cAccreditation} onChange={(e) => setCAccreditation(e.target.value)} />
                <Label>Completion date</Label>
                <input type="date" className="w-full border rounded-md p-2 text-sm" value={cDate} onChange={(e) => setCDate(e.target.value)} />
                <Label>Work / evidence summary</Label>
                <textarea className="w-full min-h-[80px] border rounded-md p-2 text-sm" value={cSummary} onChange={(e) => setCSummary(e.target.value)} />
              </div>
            ) : null}
            {selectedMode === 'INSPECTION_CHECKLIST' ? (
              <div className="space-y-2">
                <Label>Inspection date</Label>
                <input type="date" className="w-full border rounded-md p-2 text-sm" value={inspDate} onChange={(e) => setInspDate(e.target.value)} />
                <Label>Responsible person</Label>
                <input className="w-full border rounded-md p-2 text-sm" value={inspPerson} onChange={(e) => setInspPerson(e.target.value)} />
                <ChecklistEditor
                  schema={selectedChecklistSchema}
                  values={inspAnswers}
                  onChange={(id, patch) => setChecklistAnswer('INSPECTION_CHECKLIST', id, patch)}
                />
                <Label>Optional notes</Label>
                <textarea className="w-full min-h-[60px] border rounded-md p-2 text-sm" value={inspNotes} onChange={(e) => setInspNotes(e.target.value)} />
              </div>
            ) : null}
            <div
              className="space-y-2 border-t pt-3"
              data-modal-focus-target="modal-focus-supporting-upload"
              data-modal-focus-label="Supporting file upload"
            >
              <p className="text-sm font-medium text-midnight-blue">
                {isTenantDelivery
                  ? 'Upload delivery proof (optional)'
                  : isGuidedDeclaration && isTenancyAgreement
                    ? 'Upload signed agreement (optional)'
                  : isGuidedDeclaration
                    ? 'Upload supporting evidence (optional)'
                    : 'Supporting evidence uploads'}
              </p>
              <p className="text-xs text-gray-600" data-testid="supporting-upload-section-hint">
                {hasExistingAuthoritativeSubmission
                  ? 'Attach additional scans or references to supplement your submission on file. This upload alone does not submit or fulfil the obligation.'
                  : isTenantDelivery
                    ? 'Attach emails, scans, or references that support your delivery record. These are reviewed as supporting material only until you submit the form.'
                    : isGuidedDeclaration && isTenancyAgreement
                      ? 'Attach the signed agreement copy as supporting material after recording tenancy details.'
                      : isGuidedDeclaration
                        ? 'Attach copies or scans that support your check record. These are reviewed as supporting material only until you press Submit evidence.'
                        : 'Supporting files improve verification confidence. They are not linked to a formal submission until you complete and submit the form below.'}
              </p>
              <input
                type="file"
                multiple
                onChange={(e) => setSupportingFiles(Array.from(e.target.files || []))}
                className="text-sm"
              />
              <div className="flex gap-2">
                <Button type="button" variant="outline" onClick={uploadSupportingFiles} disabled={supportingUploading || supportingFiles.length === 0}>
                  {supportingUploading ? 'Uploading…' : 'Upload supporting files'}
                </Button>
              </div>
              {supportingUploads.length > 0 ? (
                <ul className="text-xs text-gray-700 space-y-1">
                  {supportingUploads.map((u) => (
                    <li key={u.document_id}>Attached: {u.filename || u.document_id}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          </div>
        ) : null}
        <DialogFooter
          className="gap-2 sm:gap-0"
          data-modal-focus-target="modal-focus-submit-evidence"
          data-modal-focus-label="Submit evidence"
        >
          {submitSummaryRecord ? (
            <Button
              type="button"
              className="bg-electric-teal text-white"
              data-testid="compliance-evidence-submit-summary-done"
              onClick={() => {
                onOpenChange(false);
                onSubmitted?.();
              }}
            >
              Done
            </Button>
          ) : (
            <>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                type="button"
                className="bg-electric-teal text-white"
                disabled={saving || !selectedMode || modes.length === 0 || reviewBlocked}
                onClick={submit}
              >
                {saving ? 'Saving…' : 'Submit evidence'}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ChecklistEditor({ schema, values, onChange }) {
  if (!Array.isArray(schema) || schema.length === 0) {
    return <p className="text-xs text-gray-500">No checklist schema configured.</p>;
  }
  return (
    <div className="space-y-3 rounded-md border p-3">
      {schema.map((row) => {
        const id = String(row?.id || '');
        const type = String(row?.answer_type || 'YES_NO').toUpperCase();
        const value = values?.[id] || {};
        const legacyDateField =
          type === 'TEXT' &&
          (id === 'issue_date' || id === 'expiry_date');
        const isoForPicker = dateInputValueFromStored(value.answer);
        const isDateRow = type === 'DATE' || legacyDateField;
        const hasNonIsoDateAnswer =
          isDateRow && value.answer != null && String(value.answer).trim() !== '' && !isoForPicker;
        return (
          <div key={id} className="space-y-1">
            <Label>{row.label}</Label>
            {(type === 'YES_NO' || type === 'PASS_FAIL') ? (
              <select
                className="w-full border rounded-md p-2 text-sm"
                data-testid={`checklist-field-${id}`}
                value={value.answer ?? ''}
                onChange={(e) => onChange(id, { answer: e.target.value })}
              >
                <option value="">Select</option>
                <option value={type === 'YES_NO' ? 'YES' : 'PASS'}>{type === 'YES_NO' ? 'Yes' : 'Pass'}</option>
                <option value={type === 'YES_NO' ? 'NO' : 'FAIL'}>{type === 'YES_NO' ? 'No' : 'Fail'}</option>
              </select>
            ) : null}
            {isDateRow && hasNonIsoDateAnswer ? (
              <textarea
                className="w-full border rounded-md p-2 text-sm min-h-[60px]"
                data-testid={`checklist-field-${id}`}
                value={value.answer ?? ''}
                onChange={(e) => onChange(id, { answer: e.target.value })}
              />
            ) : null}
            {isDateRow && !hasNonIsoDateAnswer ? (
              <input
                type="date"
                className="w-full border rounded-md p-2 text-sm"
                data-testid={`checklist-field-${id}`}
                value={isoForPicker}
                onChange={(e) => onChange(id, { answer: e.target.value })}
              />
            ) : null}
            {type === 'SELECT' && Array.isArray(row?.choices) && row.choices.length > 0 ? (
              <select
                className="w-full border rounded-md p-2 text-sm"
                data-testid={`checklist-field-${id}`}
                value={value.answer ?? ''}
                onChange={(e) => onChange(id, { answer: e.target.value })}
              >
                <option value="">Select</option>
                {row.choices.map((c) => {
                  const v = String(c?.value ?? '').trim();
                  const lab = String(c?.label ?? '').trim() || v;
                  return (
                    <option key={v} value={v}>
                      {lab}
                    </option>
                  );
                })}
              </select>
            ) : null}
            {(type === 'TEXT' || type === 'OBSERVATION') && !legacyDateField ? (
              <textarea
                className="w-full border rounded-md p-2 text-sm min-h-[60px]"
                data-testid={`checklist-field-${id}`}
                value={value.answer ?? ''}
                onChange={(e) => onChange(id, { answer: e.target.value })}
              />
            ) : null}
            {type === 'NUMERIC' ? (
              <input
                type="number"
                className="w-full border rounded-md p-2 text-sm"
                data-testid={`checklist-field-${id}`}
                value={value.answer ?? ''}
                onChange={(e) => onChange(id, { answer: e.target.value })}
              />
            ) : null}
            <input
              className="w-full border rounded-md p-2 text-xs"
              placeholder="Optional note"
              value={value.notes ?? ''}
              onChange={(e) => onChange(id, { notes: e.target.value })}
            />
            <input
              className="w-full border rounded-md p-2 text-xs"
              placeholder="Observation"
              value={value.observation ?? ''}
              onChange={(e) => onChange(id, { observation: e.target.value })}
            />
          </div>
        );
      })}
    </div>
  );
}
