/**
 * True when the compliance-score API returned v2 bucket breakdown (averaged from properties).
 * Used to avoid showing legacy component labels/weights alongside the current model.
 */
export function portfolioHasV2BucketBreakdown(bucketBreakdown) {
  if (!bucketBreakdown || typeof bucketBreakdown !== 'object') return false;
  const keys = [
    'legal_core',
    'documentation_completeness',
    'operational_responsiveness',
    'recency_maintenance_confidence',
  ];
  return keys.every((k) => {
    const b = bucketBreakdown[k];
    return b != null && typeof b === 'object' && b.percent != null && !Number.isNaN(Number(b.percent));
  });
}
