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
