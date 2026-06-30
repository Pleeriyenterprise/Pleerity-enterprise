/**
 * Presentation helpers for score authority fields returned by the backend API.
 * Do not infer grade, colour, message, or band thresholds locally.
 */

/** Governed display label for backend risk_level strings (Moderate risk — not Medium risk). */
export function formatRiskLabel(riskLevel) {
  if (!riskLevel || typeof riskLevel !== 'string') return riskLevel || '—';
  const s = riskLevel.trim();
  if (s === 'Low Risk') return 'Low risk';
  if (s === 'Moderate Risk') return 'Moderate risk';
  if (s === 'High Risk') return 'High risk';
  if (s === 'Critical Risk') return 'Critical risk';
  const lower = s.toLowerCase().replace(/\s+/g, ' ');
  if (lower === 'low risk' || lower === 'low') return 'Low risk';
  if (lower === 'moderate risk' || lower === 'moderate' || lower === 'medium risk' || lower === 'medium') {
    return 'Moderate risk';
  }
  if (lower === 'high risk' || lower === 'high' || lower === 'elevated risk') return 'High risk';
  if (lower === 'critical risk' || lower === 'critical') return 'Critical risk';
  return s;
}

/** Merge score presentation fields from API payloads (primary wins over fallback). */
export function resolveScorePresentationFields(primary = {}, fallback = {}) {
  return {
    grade: primary.grade ?? fallback.grade ?? null,
    color: primary.color ?? fallback.color ?? 'gray',
    message: primary.message ?? fallback.message ?? '',
    band_explanation: primary.band_explanation ?? fallback.band_explanation ?? '',
    risk_level: primary.risk_level ?? fallback.risk_level ?? null,
  };
}

/** Band explanation from API authority only. */
export function getRiskBandExplanation(apiSource) {
  if (!apiSource || typeof apiSource !== 'object') return '';
  const text = apiSource.band_explanation;
  return typeof text === 'string' ? text : '';
}

/** @deprecated Prefer resolveScorePresentationFields — never derive thresholds locally. */
export function riskLevelToGradeColorMessage(riskLevel, apiFields = {}) {
  const merged = resolveScorePresentationFields(apiFields);
  if (merged.grade != null || merged.message) {
    return { grade: merged.grade ?? '—', color: merged.color, message: merged.message };
  }
  return { grade: '—', color: 'gray', message: formatRiskLabel(riskLevel) };
}

/** @deprecated Use getRiskBandExplanation with API payload — score-based inference removed. */
export function getRiskBandExplanationFromScore(_score, apiSource = {}) {
  return getRiskBandExplanation(apiSource);
}
