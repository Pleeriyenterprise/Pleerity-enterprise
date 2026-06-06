import {
  ADMIN_FETCH_STATE,
  classifyAxiosError,
  classifyHttpStatus,
  resolveListFetchState,
} from './adminFetchState';

describe('adminFetchState', () => {
  it('classifies 401 as auth failure', () => {
    const row = classifyHttpStatus(401);
    expect(row.kind).toBe(ADMIN_FETCH_STATE.AUTH_FAILURE);
  });

  it('classifies 403 as auth failure', () => {
    const row = classifyHttpStatus(403);
    expect(row.kind).toBe(ADMIN_FETCH_STATE.AUTH_FAILURE);
  });

  it('classifies network axios errors', () => {
    const row = classifyAxiosError({ message: 'Network Error' });
    expect(row.kind).toBe(ADMIN_FETCH_STATE.NETWORK_FAILURE);
  });

  it('distinguishes empty from error', () => {
    expect(resolveListFetchState({ loading: false, error: null, items: [] })).toBe(ADMIN_FETCH_STATE.EMPTY);
    expect(
      resolveListFetchState({
        loading: false,
        error: { kind: ADMIN_FETCH_STATE.AUTH_FAILURE },
        items: [],
      }),
    ).toBe(ADMIN_FETCH_STATE.AUTH_FAILURE);
  });
});
