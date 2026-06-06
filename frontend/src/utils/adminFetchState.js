/**
 * Classify fetch/axios outcomes for admin list surfaces — avoid misleading empty states.
 */

import { formatApiDetail } from './apiErrorMessage';

export const ADMIN_FETCH_STATE = {
  LOADING: 'loading',
  SUCCESS: 'success',
  EMPTY: 'empty',
  AUTH_FAILURE: 'auth_failure',
  SERVER_FAILURE: 'server_failure',
  NETWORK_FAILURE: 'network_failure',
};

export function classifyHttpStatus(status) {
  if (status === 401 || status === 403) {
    return {
      kind: ADMIN_FETCH_STATE.AUTH_FAILURE,
      message:
        status === 401
          ? 'Session expired or not signed in. Please sign in again.'
          : 'You do not have permission to view this data.',
      status,
    };
  }
  if (status >= 500) {
    return {
      kind: ADMIN_FETCH_STATE.SERVER_FAILURE,
      message: 'The service is temporarily unavailable. Please retry shortly.',
      status,
    };
  }
  return {
    kind: ADMIN_FETCH_STATE.SERVER_FAILURE,
    message: `Request failed (${status}).`,
    status,
  };
}

export function classifyAxiosError(err) {
  if (!err?.response) {
    return {
      kind: ADMIN_FETCH_STATE.NETWORK_FAILURE,
      message: err?.message === 'Network Error' ? 'Network error — check your connection and try again.' : 'Request failed.',
      status: null,
    };
  }
  return classifyHttpStatus(err.response.status);
}

export async function classifyFetchResponse(response) {
  if (response.ok) {
    return { kind: ADMIN_FETCH_STATE.SUCCESS, message: '', status: response.status };
  }
  let detail = '';
  try {
    const body = await response.clone().json();
    detail = formatApiDetail(body?.detail, '');
  } catch {
    /* ignore parse errors */
  }
  const base = classifyHttpStatus(response.status);
  if (detail && base.kind === ADMIN_FETCH_STATE.SERVER_FAILURE) {
    return { ...base, message: detail };
  }
  return base;
}

export function resolveListFetchState({ loading, error, items }) {
  if (loading) return ADMIN_FETCH_STATE.LOADING;
  if (error) return error.kind || ADMIN_FETCH_STATE.SERVER_FAILURE;
  if (!items || items.length === 0) return ADMIN_FETCH_STATE.EMPTY;
  return ADMIN_FETCH_STATE.SUCCESS;
}
