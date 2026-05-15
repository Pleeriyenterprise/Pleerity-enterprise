import {
  computeReplyPacingDelay,
  SUPPORT_REPLY_MIN_MS,
  SUPPORT_REPLY_MAX_MS,
} from './supportChatPacing';

describe('computeReplyPacingDelay', () => {
  it('adds delay when backend responded faster than minimum', () => {
    expect(computeReplyPacingDelay(50)).toBe(SUPPORT_REPLY_MIN_MS - 50);
  });

  it('returns zero when backend already exceeded minimum', () => {
    expect(computeReplyPacingDelay(SUPPORT_REPLY_MIN_MS)).toBe(0);
    expect(computeReplyPacingDelay(2000)).toBe(0);
  });

  it('caps minimum wait at SUPPORT_REPLY_MAX_MS', () => {
    expect(computeReplyPacingDelay(0, SUPPORT_REPLY_MAX_MS + 100)).toBe(SUPPORT_REPLY_MAX_MS);
    expect(computeReplyPacingDelay(0, SUPPORT_REPLY_MAX_MS)).toBe(SUPPORT_REPLY_MAX_MS);
  });
});
