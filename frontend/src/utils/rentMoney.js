/** Format integer minor units (pence) for display. Operational only — not tax advice. */
export function formatMinorUnits(minor, currency = 'GBP') {
  const amount = (Number(minor) || 0) / 100;
  try {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency }).format(amount);
  } catch {
    return `£${amount.toFixed(2)}`;
  }
}

export function parseMajorToMinor(major) {
  const n = parseFloat(String(major).replace(/[^0-9.]/g, ''));
  if (Number.isNaN(n)) return 0;
  return Math.round(n * 100);
}
