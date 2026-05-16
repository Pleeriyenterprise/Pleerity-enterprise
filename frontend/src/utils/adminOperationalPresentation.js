/**
 * Admin / operational presentation for evidence verification surfaces.
 * Maps canonical backend tokens to human labels and badge styling only.
 * @see docs/governance/PRESENTATION_LANGUAGE_GOVERNANCE.md
 */

import {
  operationalLabelForToken,
  normalizePresentationKey,
  humanizeSnakeFallback,
} from './presentationLanguage';
import {
  assuranceTierLabel,
  effectiveAssuranceTier,
  effectiveEvidenceReviewState,
  reviewStateLabel,
} from './evidenceReviewUi';

/** @typedef {'success'|'warning'|'danger'|'neutral'|'info'|'processing'} PresentationTone */

/** @param {PresentationTone} tone */
export function badgeClassForTone(tone) {
  switch (tone) {
    case 'success':
      return 'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800';
    case 'warning':
      return 'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800';
    case 'danger':
      return 'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800';
    case 'info':
      return 'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800';
    case 'processing':
      return 'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-sky-100 text-sky-800';
    default:
      return 'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700';
  }
}

/**
 * @param {string} label
 * @param {PresentationTone} [tone]
 * @param {string} [canonicalValue]
 * @param {string} [helperText]
 */
export function presentationBadge(label, tone = 'neutral', canonicalValue = '', helperText = '') {
  return {
    label: label || '—',
    badgeClass: badgeClassForTone(tone),
    tone,
    canonicalValue: canonicalValue || '',
    helperText: helperText || '',
  };
}

const MATCH_OUTCOME_MAP = {
  match_confirmed: { label: 'Match confirmed', tone: 'success', helper: 'Strong alignment with the linked requirement.' },
  match_likely: { label: 'Likely match found', tone: 'warning', helper: 'Document type aligns with the requirement; confirm before verifying.' },
  mismatch_suspected: { label: 'Possible mismatch', tone: 'danger', helper: 'Document may not satisfy the linked requirement.' },
  unknown_type: { label: 'Document type unclear', tone: 'warning', helper: 'Could not classify the document family reliably.' },
  needs_admin_review: { label: 'Possible match needs review', tone: 'warning', helper: 'Manual review recommended before verification.' },
  match_uncertain: { label: 'Possible match needs review', tone: 'warning', helper: 'Manual review recommended before verification.' },
};

/**
 * @param {string|null|undefined} outcome
 */
export function getMatchOutcomePresentation(outcome) {
  const raw = String(outcome || '').trim();
  if (!raw) {
    return presentationBadge('Match not evaluated yet', 'processing', '', 'Matching may still be in progress.');
  }
  const k = normalizePresentationKey(raw);
  const mapped = MATCH_OUTCOME_MAP[k];
  if (mapped) {
    return presentationBadge(mapped.label, mapped.tone, raw, mapped.helper);
  }
  return presentationBadge(humanizeSnakeFallback(k), 'neutral', raw);
}

const CANONICAL_DOCUMENT_TYPE_MAP = {
  epc: 'Energy Performance Certificate (EPC)',
  eicr: 'Electrical Installation Condition Report (EICR)',
  gas_safety: 'Gas safety certificate',
  fire_alarm_inspection: 'Fire alarm inspection',
  legionella_risk_assessment: 'Legionella risk assessment',
  pat_test: 'PAT test certificate',
  hmo_licence: 'HMO licence',
  landlord_registration: 'Landlord registration',
  deposit_protection: 'Deposit protection evidence',
  right_to_rent_evidence: 'Right to Rent evidence',
  tenancy_agreement: 'Tenancy agreement',
  occupation_contract: 'Occupation contract',
  smoke_co_alarm_evidence: 'Smoke / CO alarm evidence',
  fire_risk_assessment: 'Fire risk assessment',
  unknown: 'Unknown document type',
};

/**
 * @param {string|null|undefined} type
 */
export function getCanonicalDocumentTypeLabel(type) {
  const raw = String(type || '').trim();
  if (!raw) return '';
  const k = normalizePresentationKey(raw);
  if (CANONICAL_DOCUMENT_TYPE_MAP[k]) return CANONICAL_DOCUMENT_TYPE_MAP[k];
  return humanizeSnakeFallback(k);
}

/**
 * @param {string|null|undefined} type
 */
export function getCanonicalDocumentTypePresentation(type) {
  const raw = String(type || '').trim();
  if (!raw) {
    return presentationBadge('Document type pending', 'processing', '', 'Classification may still be running.');
  }
  const label = getCanonicalDocumentTypeLabel(raw);
  return presentationBadge(label, 'neutral', raw);
}

const MISMATCH_REASON_MAP = {
  none: { label: 'No mismatch flagged', tone: 'neutral' },
  strong_family_mismatch: { label: 'Document type does not match requirement', tone: 'danger' },
  declared_type_mismatch: { label: 'Declared type does not match', tone: 'danger' },
  filename_hint_mismatch: { label: 'Filename suggests a different document', tone: 'warning' },
  extraction_family_mismatch: { label: 'Extracted content suggests a different document', tone: 'warning' },
  extraction_ambiguous: { label: 'Extraction result was ambiguous', tone: 'warning' },
  no_requirement_link: { label: 'No matching requirement linked yet', tone: 'neutral' },
  no_requirement_linked: { label: 'No matching requirement linked yet', tone: 'neutral' },
  admin_override_match: { label: 'Admin match override applied', tone: 'info' },
  low_signal: { label: 'Low confidence signals', tone: 'warning' },
  legacy_unclassified: { label: 'Legacy document — classification incomplete', tone: 'neutral' },
};

/**
 * @param {string|null|undefined} code
 * @param {string|null|undefined} text
 */
export function getMismatchReasonPresentation(code, text) {
  const humanText = String(text || '').trim();
  if (humanText && !/^[A-Z0-9_]+$/.test(humanText)) {
    return presentationBadge(humanText, 'neutral', String(code || '').trim());
  }
  const raw = String(code || '').trim();
  if (!raw) {
    return presentationBadge('—', 'neutral', '');
  }
  const k = normalizePresentationKey(raw);
  const mapped = MISMATCH_REASON_MAP[k];
  if (mapped) {
    return presentationBadge(mapped.label, mapped.tone, raw);
  }
  return presentationBadge(humanizeSnakeFallback(k), 'neutral', raw);
}

/**
 * @param {number|string|null|undefined} score — 0–1 decimal or 0–100 percent
 */
export function getConfidencePresentation(score) {
  if (score == null || score === '') {
    return {
      ...presentationBadge('Confidence unavailable', 'neutral', '', 'Match confidence has not been calculated yet.'),
      percent: null,
      tier: null,
      tierLabel: '',
      percentLabel: '',
    };
  }
  let n = Number(score);
  if (Number.isNaN(n)) {
    return {
      ...presentationBadge('Confidence unavailable', 'neutral', String(score)),
      percent: null,
      tier: null,
      tierLabel: '',
      percentLabel: '',
    };
  }
  if (n > 1) n = n / 100;
  const pct = Math.round(Math.max(0, Math.min(1, n)) * 100);
  let tier;
  let tierLabel;
  let tone;
  if (pct >= 90) {
    tier = 'high';
    tierLabel = 'High confidence';
    tone = 'success';
  } else if (pct >= 70) {
    tier = 'medium';
    tierLabel = 'Medium confidence';
    tone = 'warning';
  } else {
    tier = 'low';
    tierLabel = 'Low confidence';
    tone = 'neutral';
  }
  const label = `${pct}% confidence`;
  const helperText = `${tierLabel} (${pct}%).`;
  return {
    ...presentationBadge(label, tone, String(score), helperText),
    percent: pct,
    tier,
    tierLabel,
    percentLabel: label,
  };
}

const VALIDATION_STATUS_MAP = {
  pass: { label: 'Passed checks', tone: 'success' },
  passed: { label: 'Passed checks', tone: 'success' },
  warn: { label: 'Warnings found', tone: 'warning' },
  warning: { label: 'Warnings found', tone: 'warning' },
  fail: { label: 'Validation failed', tone: 'danger' },
  failed: { label: 'Validation failed', tone: 'danger' },
  failure: { label: 'Validation failed', tone: 'danger' },
  unknown: { label: 'Validation status unknown', tone: 'neutral' },
};

/**
 * @param {Record<string, unknown>|null|undefined} snap
 */
export function getValidationSnapshotPresentation(snap = {}) {
  const status = String(snap?.validation_status || '').trim();
  const warnings = Array.isArray(snap?.warnings) ? snap.warnings : [];
  const failures = Array.isArray(snap?.failures) ? snap.failures : [];
  if (!status && warnings.length === 0 && failures.length === 0) {
    return presentationBadge('No validation run yet', 'neutral', '');
  }
  const k = normalizePresentationKey(status || 'unknown');
  const mapped = VALIDATION_STATUS_MAP[k] || { label: humanizeSnakeFallback(k), tone: 'neutral' };
  const parts = [];
  if (warnings.length) parts.push(`${warnings.length} warning${warnings.length === 1 ? '' : 's'}`);
  if (failures.length) parts.push(`${failures.length} failure${failures.length === 1 ? '' : 's'}`);
  const summary = parts.length ? `${mapped.label} · ${parts.join(', ')}` : mapped.label;
  const helperText = [
    warnings.length ? `Warnings: ${warnings.join(', ')}` : '',
    failures.length ? `Failures: ${failures.join(', ')}` : '',
  ].filter(Boolean).join(' | ');
  return presentationBadge(summary, mapped.tone, status, helperText);
}

/**
 * @param {number|string|null|undefined} score — 0–1 risk score
 */
export function getAnomalyRiskPresentation(score) {
  if (score == null || score === '') {
    return presentationBadge('—', 'neutral', '');
  }
  const risk = Number(score);
  if (Number.isNaN(risk)) {
    return presentationBadge('—', 'neutral', String(score));
  }
  let tone;
  let label;
  if (risk >= 0.65) {
    tone = 'danger';
    label = 'High-risk anomaly detected';
  } else if (risk >= 0.35) {
    tone = 'warning';
    label = 'Medium anomaly risk';
  } else {
    tone = 'neutral';
    label = 'Low anomaly risk';
  }
  return presentationBadge(label, tone, String(score), `Risk score: ${risk.toFixed(2)}`);
}

/**
 * @param {Record<string, unknown>|null|undefined} ai
 */
export function getAiAssistanceWarningsPresentation(ai = {}) {
  const warns = Array.isArray(ai?.extraction_warnings) ? ai.extraction_warnings : [];
  const flags = Array.isArray(ai?.ai_flags) ? ai.ai_flags : [];
  if (warns.length === 0 && flags.length === 0) {
    return presentationBadge('—', 'neutral', '');
  }
  const parts = [];
  if (warns.length) parts.push(`${warns.length} extraction warning${warns.length === 1 ? '' : 's'}`);
  if (flags.length) parts.push(`${flags.length} review flag${flags.length === 1 ? '' : 's'}`);
  const helperText = [
    warns.length ? warns.join(', ') : '',
    flags.length ? flags.join(', ') : '',
  ].filter(Boolean).join(' | ');
  return presentationBadge(parts.join(' · '), warns.length || flags.length ? 'warning' : 'neutral', '', helperText);
}

const LEGACY_MATCH_MAP = {
  unclassified_pre_engine: { label: 'Legacy — not auto-classified', tone: 'neutral' },
};

/**
 * @param {string|null|undefined} state
 */
export function getLegacyMatchStatePresentation(state) {
  const raw = String(state || '').trim();
  if (!raw) return null;
  const k = normalizePresentationKey(raw);
  const mapped = LEGACY_MATCH_MAP[k];
  if (mapped) return presentationBadge(mapped.label, mapped.tone, raw);
  return presentationBadge(humanizeSnakeFallback(k), 'neutral', raw);
}

/**
 * @param {boolean|null|undefined} satisfies
 */
export function getEvidenceSatisfiesPresentation(satisfies) {
  if (satisfies === true) return presentationBadge('Likely satisfies requirement', 'success', 'true');
  if (satisfies === false) return presentationBadge('May not satisfy requirement', 'warning', 'false');
  return presentationBadge('Satisfaction not determined', 'neutral', '');
}

/**
 * @param {Record<string, unknown>|null|undefined} doc
 */
export function getReviewStatePresentation(doc = {}) {
  const state = effectiveEvidenceReviewState(doc);
  const label = reviewStateLabel(state);
  let tone = 'neutral';
  if (state === 'VERIFIED' || state === 'ACCEPTED_UNVERIFIED') tone = 'success';
  else if (state === 'REJECTED' || state === 'EXPIRED') tone = 'danger';
  else if (state === 'UNDER_REVIEW' || state === 'NEEDS_INFORMATION') tone = 'warning';
  else if (state === 'UPLOADED') tone = 'info';
  return presentationBadge(label, tone, state);
}

/**
 * @param {Record<string, unknown>|null|undefined} doc
 */
export function getAssuranceTierPresentation(doc = {}) {
  const tier = effectiveAssuranceTier(doc);
  const label = assuranceTierLabel(tier);
  let tone = 'neutral';
  if (tier === 'EXTERNALLY_VERIFIED' || tier === 'HUMAN_ACCEPTED') tone = 'success';
  else if (tier === 'REJECTED' || tier === 'SYSTEM_EXPIRED') tone = 'danger';
  return presentationBadge(label, tone, tier);
}

/**
 * @param {string|null|undefined} status — extraction queue / document extraction_status
 */
export function getExtractionStatusPresentation(status) {
  const raw = String(status || '').trim();
  if (!raw) return presentationBadge('—', 'neutral', '');
  const k = normalizePresentationKey(raw);
  const map = {
    needs_review: { label: 'Extraction needs review', tone: 'warning' },
    failed: { label: 'Extraction failed', tone: 'danger' },
    pending: { label: 'Extraction in progress', tone: 'processing' },
    confirmed: { label: 'Extraction applied', tone: 'success' },
    rejected: { label: 'Extraction rejected', tone: 'neutral' },
    extracted: { label: 'Extracted — awaiting apply', tone: 'info' },
  };
  const mapped = map[k];
  if (mapped) return presentationBadge(mapped.label, mapped.tone, raw);
  return presentationBadge(operationalLabelForToken(raw, { emptyLabel: '—' }), 'neutral', raw);
}

export const ENRICHMENT_READINESS = {
  READY: 'READY',
  PROCESSING: 'PROCESSING',
  PARTIAL: 'PARTIAL',
  FAILED: 'FAILED',
};

/**
 * @param {Record<string, unknown>} doc
 */
export function getEnrichmentReadinessPresentation(doc = {}) {
  const readiness = String(doc.enrichment_readiness || '').toUpperCase();
  const apiLabel = String(doc.enrichment_readiness_label || '').trim();
  const detail = String(doc.enrichment_readiness_detail || '').trim();
  if (readiness) {
    const map = {
      READY: { label: apiLabel || 'Ready for review', tone: 'success' },
      PROCESSING: { label: apiLabel || 'Processing document…', tone: 'processing' },
      PARTIAL: { label: apiLabel || 'Review preparation incomplete', tone: 'warning' },
      FAILED: { label: apiLabel || 'Extraction failed — review manually', tone: 'danger' },
    };
    const mapped = map[readiness] || { label: apiLabel || 'Processing document…', tone: 'processing' };
    return presentationBadge(mapped.label, mapped.tone, readiness, detail || apiLabel);
  }
  if (!hasMatchEvaluationAttempted(doc)) {
    return presentationBadge('Review preparation in progress', 'processing', '', 'Waiting for extraction and matching.');
  }
  if (doc.extraction_status === 'FAILED' || doc.ai_extraction?.status === 'failed') {
    return presentationBadge('Extraction failed — review manually', 'danger', 'FAILED');
  }
  return presentationBadge('Ready for review', 'success', 'READY');
}

/**
 * @param {Record<string, unknown>} doc
 */
export function isEnrichmentReady(doc = {}) {
  return String(doc.enrichment_readiness || '').toUpperCase() === ENRICHMENT_READINESS.READY;
}

/**
 * @param {Record<string, unknown>} doc
 */
export function isEnrichmentProcessing(doc = {}) {
  return String(doc.enrichment_readiness || '').toUpperCase() === ENRICHMENT_READINESS.PROCESSING;
}

/**
 * Client-side inference: has match engine written signals to this document row?
 * @param {Record<string, unknown>} doc
 */
export function hasMatchEvaluationAttempted(doc = {}) {
  if (doc.match_outcome) return true;
  if (doc.mismatch_reason_code) return true;
  if (doc.predicted_document_type) return true;
  if (doc.evidence_match_legacy_state) return true;
  const signals = doc.detection_signals;
  if (signals && typeof signals === 'object' && Object.keys(signals).length > 0) return true;
  return false;
}

/**
 * @param {Record<string, unknown>} doc
 */
export function getRequirementLinkPresentation(doc = {}) {
  const label = String(doc.requirement_label || '').trim();
  if (label) {
    return presentationBadge(label, 'neutral', String(doc.requirement_id || ''));
  }
  if (doc.requirement_id) {
    return presentationBadge('Requirement linked', 'info', String(doc.requirement_id), 'Requirement details are still loading.');
  }
  return presentationBadge('Requirement not linked yet', 'neutral', '', 'Link or resolve match before verifying against an obligation.');
}

/**
 * Combined suggested-match column (type + outcome + mismatch hint).
 * @param {Record<string, unknown>} doc
 */
export function getSuggestedMatchPresentation(doc = {}) {
  const readiness = String(doc.enrichment_readiness || '').toUpperCase();
  if (readiness === ENRICHMENT_READINESS.FAILED) {
    return presentationBadge(
      'Match unavailable — extraction failed',
      'danger',
      '',
      'Resolve extraction or review the file manually before matching.',
    );
  }
  if (readiness === ENRICHMENT_READINESS.PROCESSING || (!hasMatchEvaluationAttempted(doc) && readiness !== ENRICHMENT_READINESS.READY)) {
    const label = readiness === ENRICHMENT_READINESS.PARTIAL
      ? (String(doc.enrichment_readiness_label || '').includes('match') ? doc.enrichment_readiness_label : 'Matching requirement…')
      : (doc.enrichment_readiness_label || 'Matching requirement…');
    return presentationBadge(String(label), 'processing', '', doc.enrichment_readiness_detail || '');
  }
  if (!hasMatchEvaluationAttempted(doc)) {
    return presentationBadge('Matching requirement…', 'processing', '', 'Automated matching is still in progress.');
  }
  const outcome = getMatchOutcomePresentation(doc.match_outcome);
  const typeLabel = getCanonicalDocumentTypeLabel(doc.predicted_document_type);
  const mismatch = getMismatchReasonPresentation(doc.mismatch_reason_code, doc.mismatch_reason_text);
  const label = typeLabel
    ? `${typeLabel} · ${outcome.label}`
    : outcome.label;
  const helperText = [outcome.helperText, mismatch.helperText].filter(Boolean).join(' ');
  return {
    ...outcome,
    label,
    helperText,
    documentTypeLabel: typeLabel,
    matchOutcome: outcome,
    mismatch,
  };
}

/**
 * Operational review status for pending verification row (review + optional processing).
 * @param {Record<string, unknown>} doc
 */
export function getPendingReviewStatusPresentation(doc = {}) {
  const readiness = String(doc.enrichment_readiness || '').toUpperCase();
  if (readiness === ENRICHMENT_READINESS.FAILED) {
    return presentationBadge(
      doc.enrichment_readiness_label || 'Extraction failed — review manually',
      'danger',
      '',
      doc.enrichment_readiness_detail || 'Automated extraction did not complete.',
    );
  }
  if (readiness === ENRICHMENT_READINESS.PROCESSING) {
    return presentationBadge(
      doc.enrichment_readiness_label || 'Review preparation in progress',
      'processing',
      '',
      doc.enrichment_readiness_detail || 'Extraction and matching are still running.',
    );
  }
  if (readiness === ENRICHMENT_READINESS.PARTIAL) {
    return presentationBadge(
      doc.enrichment_readiness_label || 'Review preparation incomplete',
      'warning',
      '',
      doc.enrichment_readiness_detail || 'Some context is still loading.',
    );
  }
  if (!hasMatchEvaluationAttempted(doc)) {
    return presentationBadge('Review preparation in progress', 'processing', '', 'Extraction and matching are still running.');
  }
  return getReviewStatePresentation(doc);
}

/**
 * @param {Record<string, unknown>} doc
 */
export function getPendingDocumentOperationalPresentation(doc = {}) {
  const fileName = String(doc.file_name || '').trim();
  const shortId = String(doc.document_id || '').slice(0, 8);
  const readiness = getEnrichmentReadinessPresentation(doc);
  const confidence = (isEnrichmentReady(doc) || hasMatchEvaluationAttempted(doc))
    ? getConfidencePresentation(doc.match_confidence)
    : getConfidencePresentation(null);
  return {
    readiness,
    documentTitle: fileName || (shortId ? `Document ${shortId}…` : 'Document'),
    documentSubtitle: fileName && doc.document_id ? String(doc.document_id) : '',
    clientName: doc.client_name || '—',
    crn: doc.crn || '—',
    requirement: getRequirementLinkPresentation(doc),
    suggestedMatch: getSuggestedMatchPresentation(doc),
    confidence,
    reviewStatus: getPendingReviewStatusPresentation(doc),
    assurance: getAssuranceTierPresentation(doc),
    validation: getValidationSnapshotPresentation(doc.latest_validation_snapshot),
    aiWarnings: getAiAssistanceWarningsPresentation(doc.ai_assistance),
    anomaly: getAnomalyRiskPresentation(doc.ai_assistance?.anomaly_risk_score),
    satisfies: getEvidenceSatisfiesPresentation(doc.evidence_satisfies_requirement),
    legacy: getLegacyMatchStatePresentation(doc.evidence_match_legacy_state),
    documentType: getCanonicalDocumentTypePresentation(doc.predicted_document_type),
    matchOutcome: getMatchOutcomePresentation(doc.match_outcome),
    mismatch: getMismatchReasonPresentation(doc.mismatch_reason_code, doc.mismatch_reason_text),
  };
}

/**
 * Flat list of technical detail rows for audit/debug drawer.
 * @param {Record<string, unknown>} doc
 */
export function buildTechnicalDetailsRows(doc = {}) {
  const rows = [
    { key: 'document_id', label: 'Document ID', value: doc.document_id },
    { key: 'client_id', label: 'Client ID', value: doc.client_id },
    { key: 'property_id', label: 'Property ID', value: doc.property_id || doc.authoritative_property_id },
    { key: 'requirement_id', label: 'Requirement ID', value: doc.requirement_id },
    { key: 'match_outcome', label: 'Match outcome (canonical)', value: doc.match_outcome },
    { key: 'predicted_document_type', label: 'Predicted type (canonical)', value: doc.predicted_document_type },
    { key: 'match_confidence', label: 'Match confidence (raw)', value: doc.match_confidence != null ? String(doc.match_confidence) : null },
    { key: 'mismatch_reason_code', label: 'Mismatch reason code', value: doc.mismatch_reason_code },
    { key: 'mismatch_reason_text', label: 'Mismatch reason text', value: doc.mismatch_reason_text },
    { key: 'evidence_satisfies_requirement', label: 'Evidence satisfies requirement', value: doc.evidence_satisfies_requirement },
    { key: 'evidence_match_legacy_state', label: 'Legacy match state', value: doc.evidence_match_legacy_state },
    { key: 'evidence_review_state', label: 'Review state (canonical)', value: effectiveEvidenceReviewState(doc) },
    { key: 'assurance_tier', label: 'Assurance tier (canonical)', value: effectiveAssuranceTier(doc) },
    { key: 'evidence_scope_type', label: 'Evidence scope', value: doc.evidence_scope_type },
    { key: 'document_type', label: 'Declared document type', value: doc.document_type },
    { key: 'manual_review_flag', label: 'Manual review flag', value: doc.manual_review_flag },
    { key: 'requirement_evidence_mismatch', label: 'Requirement evidence mismatch', value: doc.requirement_evidence_mismatch },
    { key: 'enrichment_readiness', label: 'Enrichment readiness (canonical)', value: doc.enrichment_readiness },
    { key: 'enrichment_readiness_label', label: 'Enrichment readiness label', value: doc.enrichment_readiness_label },
    { key: 'extraction_status', label: 'Extraction status (canonical)', value: doc.extraction_status },
    { key: 'match_status', label: 'Match status (canonical)', value: doc.match_status },
    { key: 'enrichment_started_at', label: 'Enrichment started at', value: doc.enrichment_started_at },
    { key: 'enrichment_completed_at', label: 'Enrichment completed at', value: doc.enrichment_completed_at },
    { key: 'enrichment_latency_ms', label: 'Enrichment latency (ms)', value: doc.enrichment_latency_ms != null ? String(doc.enrichment_latency_ms) : null },
  ];
  const snap = doc.latest_validation_snapshot;
  if (snap && typeof snap === 'object') {
    rows.push({ key: 'validation_status', label: 'Validation status (canonical)', value: snap.validation_status });
    if (Array.isArray(snap.warnings) && snap.warnings.length) {
      rows.push({ key: 'validation_warnings', label: 'Validation warnings (raw)', value: snap.warnings.join(', ') });
    }
    if (Array.isArray(snap.failures) && snap.failures.length) {
      rows.push({ key: 'validation_failures', label: 'Validation failures (raw)', value: snap.failures.join(', ') });
    }
  }
  const ai = doc.ai_assistance;
  if (ai && typeof ai === 'object') {
    if (ai.anomaly_risk_score != null) {
      rows.push({ key: 'anomaly_risk_score', label: 'Anomaly risk score (raw)', value: String(ai.anomaly_risk_score) });
    }
    if (Array.isArray(ai.extraction_warnings) && ai.extraction_warnings.length) {
      rows.push({ key: 'extraction_warnings', label: 'Extraction warnings (raw)', value: ai.extraction_warnings.join(', ') });
    }
    if (Array.isArray(ai.ai_flags) && ai.ai_flags.length) {
      rows.push({ key: 'ai_flags', label: 'AI flags (raw)', value: ai.ai_flags.join(', ') });
    }
  }
  if (doc.detection_signals && typeof doc.detection_signals === 'object') {
    rows.push({
      key: 'detection_signals',
      label: 'Detection signals (raw)',
      value: JSON.stringify(doc.detection_signals),
    });
  }
  return rows.filter((r) => r.value != null && r.value !== '');
}

const MATCH_RESOLUTION_PRESENTATION = {
  approve_override: {
    label: 'Requirement link confirmed',
    tone: 'info',
    helper: 'Matching resolved only. Use Verify to accept evidence on file — this is not verification.',
    toast: 'Requirement link confirmed. Evidence verification is still required.',
  },
  reject_evidence: {
    label: 'Evidence rejected',
    tone: 'danger',
    helper: 'Document marked rejected; extraction confirmation closed.',
    toast: 'Evidence rejected. Document is not accepted on file.',
  },
  relink_requirement: {
    label: 'Requirement relinked',
    tone: 'info',
    helper: 'Obligation link updated. Verification is still required before acceptance.',
    toast: 'Requirement relinked successfully. Evidence verification is still required.',
  },
};

/**
 * Admin evidence match resolution (distinct from Verify / accept on file).
 * @param {string} action
 */
export function getMatchResolutionActionPresentation(action) {
  const key = String(action || '').trim().toLowerCase();
  const mapped = MATCH_RESOLUTION_PRESENTATION[key];
  if (mapped) {
    return presentationBadge(mapped.label, mapped.tone, key, mapped.helper);
  }
  return presentationBadge('Match resolution', 'neutral', key, 'Admin action on document–requirement matching.');
}

/**
 * @param {string} action
 */
export function getMatchResolutionSuccessToast(action) {
  const key = String(action || '').trim().toLowerCase();
  return MATCH_RESOLUTION_PRESENTATION[key]?.toast || 'Match resolution recorded.';
}

/**
 * Evidence verify / accept on file (distinct from match resolution).
 */
export function getEvidenceVerifyActionPresentation() {
  return presentationBadge(
    'Verify evidence',
    'success',
    'verify',
    'Accepts evidence on file after review. Does not only resolve document–requirement matching.',
  );
}
