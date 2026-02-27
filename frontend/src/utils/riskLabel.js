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
