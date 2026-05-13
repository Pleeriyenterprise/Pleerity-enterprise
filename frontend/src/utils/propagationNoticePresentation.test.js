import {
  propagationNoticeForUi,
  PROPAGATION_NOTICE_CODE_AUTHORITY_DEFERRED,
  PROPAGATION_NOTICE_CODE_RECALC_DEFERRED,
} from './propagationNoticePresentation';

describe('propagationNoticeForUi', () => {
  it('returns null for empty input', () => {
    expect(propagationNoticeForUi(null)).toBeNull();
    expect(propagationNoticeForUi(undefined)).toBeNull();
    expect(propagationNoticeForUi({})).toBeNull();
  });

  it('prefers server message when present', () => {
    const out = propagationNoticeForUi({
      code: PROPAGATION_NOTICE_CODE_AUTHORITY_DEFERRED,
      message: 'Custom server explanation.',
    });
    expect(out?.body).toBe('Custom server explanation.');
    expect(out?.code).toBe(PROPAGATION_NOTICE_CODE_AUTHORITY_DEFERRED);
  });

  it('falls back by code when message missing', () => {
    const out = propagationNoticeForUi({ code: PROPAGATION_NOTICE_CODE_RECALC_DEFERRED });
    expect(out?.body.length).toBeGreaterThan(10);
    expect(out?.code).toBe(PROPAGATION_NOTICE_CODE_RECALC_DEFERRED);
  });
});
