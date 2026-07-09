/**
 * Client-held session runtime version hints for API requests (ILP-5).
 * Not permission authority — staleness detection only.
 */
let runtimeVersion = null;
let entitlementsVersion = null;
let contractVersion = null;
let sessionId = null;

export function setSessionRuntimeVersions({
  runtime_version,
  entitlements_version,
  contract_version,
  session_id,
} = {}) {
  if (runtime_version != null) runtimeVersion = runtime_version;
  if (entitlements_version != null) entitlementsVersion = entitlements_version;
  if (contract_version != null) contractVersion = contract_version;
  if (session_id != null) sessionId = session_id;
}

export function clearSessionRuntimeVersions() {
  runtimeVersion = null;
  entitlementsVersion = null;
  contractVersion = null;
  sessionId = null;
}

export function getSessionRuntimeVersionHeaders() {
  const headers = {};
  if (runtimeVersion != null) headers['X-Client-Runtime-Version'] = String(runtimeVersion);
  if (entitlementsVersion != null) headers['X-Client-Entitlements-Version'] = String(entitlementsVersion);
  if (contractVersion != null) headers['X-Client-Contract-Version'] = String(contractVersion);
  if (sessionId != null) headers['X-Client-Session-Id'] = String(sessionId);
  return headers;
}

export function getStoredSessionRuntimeVersions() {
  return {
    runtimeVersion,
    entitlementsVersion,
    contractVersion,
    sessionId,
  };
}

export function applySessionRuntimeFromUser(user) {
  if (!user) {
    clearSessionRuntimeVersions();
    return;
  }
  setSessionRuntimeVersions({
    runtime_version: user.runtime_version,
    entitlements_version: user.entitlements_version,
    session_id: user.session_id,
  });
}

export function applySessionRuntimeFromContract(runtime, sessionRuntime) {
  if (sessionRuntime) {
    setSessionRuntimeVersions({
      runtime_version: sessionRuntime.runtime_version,
      entitlements_version: sessionRuntime.entitlements_version,
      contract_version: sessionRuntime.contract_version,
      session_id: sessionRuntime.session_id,
    });
    return;
  }
  if (runtime) {
    setSessionRuntimeVersions({
      runtime_version: runtime.runtime_version,
      contract_version: runtime.contract_version,
      entitlements_version: runtime.session_policy?.entitlements_version,
    });
  }
}

/** Registered by LifecycleRuntimeProvider for response-header driven refresh. */
let refreshHandler = null;
let refreshInFlight = false;

export function registerSessionRuntimeRefreshHandler(handler) {
  refreshHandler = handler;
}

export async function requestSessionRuntimeRefresh(reason = 'api_header') {
  if (!refreshHandler || refreshInFlight) return false;
  refreshInFlight = true;
  try {
    return await refreshHandler(reason);
  } finally {
    refreshInFlight = false;
  }
}

export function responseIndicatesSessionRefresh(response) {
  const headers = response?.headers || {};
  const flag =
    headers['x-session-refresh-required'] ||
    headers['X-Session-Refresh-Required'] ||
    headers['x-session-refresh-required'.toLowerCase()];
  return flag === 'true' || flag === 'force_reauth';
}

export function responseForceReauth(response) {
  const headers = response?.headers || {};
  const flag = headers['x-session-refresh-required'] || headers['X-Session-Refresh-Required'];
  return flag === 'force_reauth';
}
