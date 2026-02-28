/**
 * Risk label for UI: Low / Medium / High / Critical risk (no legal verdict).
 * Backend may return "Moderate Risk"; we display "Medium risk" per spec.
 */
export function formatRiskLabel(riskLevel) {
  if (!riskLevel || typeof riskLevel !== 'string') return riskLevel || '—';
  const s = riskLevel.trim();
  if (s === 'Moderate Risk') return 'Medium risk';
  if (s === 'Low Risk') return 'Low risk';
  if (s === 'High Risk') return 'High risk';
  if (s === 'Critical Risk') return 'Critical risk';
  return s;
}

/** Map backend risk_level to grade + color + message so dashboard card matches "Risk level" line and tables. */
export function riskLevelToGradeColorMessage(riskLevel) {
  if (!riskLevel || typeof riskLevel !== 'string') return { grade: '—', color: 'gray', message: '' };
  const s = riskLevel.trim();
  if (s === 'Low Risk') return { grade: 'B', color: 'green', message: 'Low risk - good standing' };
  if (s === 'Moderate Risk') return { grade: 'C', color: 'amber', message: 'Moderate risk - action required' };
  if (s === 'High Risk') return { grade: 'D', color: 'amber', message: 'High risk - action required' };
  if (s === 'Critical Risk') return { grade: 'F', color: 'red', message: 'High urgency: overdue items detected' };
  return { grade: '—', color: 'gray', message: formatRiskLabel(riskLevel) };
}

/** Inline risk band explanation for display under grade (matches backend risk_bands). */
export function getRiskBandExplanation(riskLevel) {
  if (!riskLevel || typeof riskLevel !== 'string') return '';
  const s = riskLevel.trim();
  if (s === 'Low Risk') return 'Low risk (80–100): Good standing.';
  if (s === 'Moderate Risk') return 'Medium risk (60–79): Action required to maintain compliance.';
  if (s === 'High Risk') return 'High risk (40–59): Action required to reduce exposure.';
  if (s === 'Critical Risk') return 'Critical risk (0–39): Immediate action required.';
  return '';
}

/** Risk band explanation when only score is available (e.g. from compliance score API). */
export function getRiskBandExplanationFromScore(score) {
  if (score == null || typeof score !== 'number') return '';
  if (score >= 80) return 'Low risk (80–100): Good standing.';
  if (score >= 60) return 'Medium risk (60–79): Action required to maintain compliance.';
  if (score >= 40) return 'High risk (40–59): Action required to reduce exposure.';
  return 'Critical risk (0–39): Immediate action required.';
}
