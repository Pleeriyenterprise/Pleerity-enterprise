/**
 * Prefer human-facing invoice_number for UI; fall back to reference / UUID.
 * @param {Record<string, unknown>|null|undefined} inv
 */
export function invoiceDisplayLabel(inv) {
  if (!inv || typeof inv !== 'object') return '—';
  const n = inv.invoice_number;
  if (n != null && String(n).trim()) return String(n).trim();
  const r = inv.reference || inv.contractor_reference;
  if (r != null && String(r).trim()) return String(r).trim();
  const id = inv.invoice_id;
  if (id != null && String(id).trim()) return String(id).trim();
  return '—';
}
