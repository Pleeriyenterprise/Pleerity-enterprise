import {
  normalizePresentationKey,
  operationalLabelForToken,
  humanizeSnakeFallback,
} from './presentationLanguage';

describe('presentationLanguage', () => {
  it('normalizes kebab and spaces to snake keys', () => {
    expect(normalizePresentationKey(' pending-SYNC ')).toBe('pending_sync');
  });

  it('maps known async-honest compliance phrases', () => {
    expect(operationalLabelForToken('accepted_unverified')).toBe('Accepted (awaiting verification)');
    expect(operationalLabelForToken('RECALC_PENDING')).toBe('Compliance score update pending');
    expect(operationalLabelForToken('propagation_pending')).toBe('Updates still applying');
  });

  it('preserves human API sentences without snake segments', () => {
    expect(operationalLabelForToken('Evidence submitted and awaiting review')).toBe(
      'Evidence submitted and awaiting review'
    );
  });

  it('title-cases unknown snake tokens', () => {
    expect(operationalLabelForToken('custom_unknown_token')).toBe('Custom Unknown Token');
    expect(humanizeSnakeFallback('')).toBe('—');
  });

  it('respects emptyLabel option', () => {
    expect(operationalLabelForToken('', { emptyLabel: 'All' })).toBe('All');
  });

  it('maps SLA and scheduled report presentation tokens', () => {
    expect(operationalLabelForToken('sla_breached')).toBe('SLA deadline missed');
    expect(operationalLabelForToken('breached')).toBe('SLA deadline missed');
    expect(operationalLabelForToken('near_breach')).toBe('Near SLA deadline');
    expect(operationalLabelForToken('compliance_summary')).toBe('Compliance status summary');
    expect(operationalLabelForToken('requirements')).toBe('Requirements report');
  });
});
