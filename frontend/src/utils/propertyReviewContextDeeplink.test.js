import { parsePropertyReviewContextDeeplink } from './propertyReviewContextDeeplink';

describe('parsePropertyReviewContextDeeplink', () => {
  it('maps resolve_requirement to review context with submission focus', () => {
    const parsed = parsePropertyReviewContextDeeplink(
      '?resolve_requirement=req-abc&foo=bar',
    );
    expect(parsed).toEqual({
      kind: 'review_context',
      requirementId: 'req-abc',
      focusSubmission: true,
    });
  });

  it('returns null when param absent', () => {
    expect(parsePropertyReviewContextDeeplink('?tab=evidence')).toBeNull();
    expect(parsePropertyReviewContextDeeplink('')).toBeNull();
  });
});
