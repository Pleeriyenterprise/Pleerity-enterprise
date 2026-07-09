/**
 * ILP-5 session runtime store and sync utilities.
 */
import {
  applySessionRuntimeFromUser,
  clearSessionRuntimeVersions,
  getSessionRuntimeVersionHeaders,
  setSessionRuntimeVersions,
} from './sessionRuntimeStore';
import { broadcastRuntimeInvalidation } from './sessionRuntimeSync';

describe('sessionRuntimeStore', () => {
  beforeEach(() => {
    clearSessionRuntimeVersions();
  });

  it('exposes version headers for API staleness detection', () => {
    setSessionRuntimeVersions({
      runtime_version: 99,
      entitlements_version: 4,
      contract_version: '1.0.0',
      session_id: 'sess-1',
    });
    expect(getSessionRuntimeVersionHeaders()).toEqual({
      'X-Client-Runtime-Version': '99',
      'X-Client-Entitlements-Version': '4',
      'X-Client-Contract-Version': '1.0.0',
      'X-Client-Session-Id': 'sess-1',
    });
  });

  it('applies session metadata from user object', () => {
    applySessionRuntimeFromUser({
      session_id: 'abc',
      runtime_version: 12,
      entitlements_version: 2,
    });
    expect(getSessionRuntimeVersionHeaders()['X-Client-Session-Id']).toBe('abc');
  });
});

describe('sessionRuntimeSync', () => {
  it('broadcastRuntimeInvalidation dispatches custom event', () => {
    const handler = jest.fn();
    window.addEventListener('pleerity:session-runtime-sync', handler);
    broadcastRuntimeInvalidation({ reason: 'test' });
    expect(handler).toHaveBeenCalled();
    window.removeEventListener('pleerity:session-runtime-sync', handler);
  });
});
