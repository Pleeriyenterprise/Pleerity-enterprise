/**
 * Lightweight client-side circuit breaker for repeated 403/429 API failures.
 * Prevents retry storms against the same endpoint path and pauses all portal
 * reads briefly after any 429 (rate limit / IP block).
 */

const CIRCUIT_FAILURE_THRESHOLD = 2;
const CIRCUIT_COOLDOWN_MS = 90_000;
const GLOBAL_429_PAUSE_MS = 90_000;
const SECURITY_BLOCK_PAUSE_MS = 5 * 60_000;
const state = new Map();
let globalPauseUntil = 0;

function normalizePath(url) {
  return String(url || '')
    .replace(/\?.*$/, '')
    .replace(/^\/api\//, '');
}

export function isGlobalApiPaused() {
  if (Date.now() >= globalPauseUntil) {
    globalPauseUntil = 0;
    return false;
  }
  return true;
}

export function isApiCircuitOpen(url) {
  if (isGlobalApiPaused()) {
    return true;
  }
  const key = normalizePath(url);
  const entry = state.get(key);
  if (!entry?.openUntil) {
    return false;
  }
  if (Date.now() >= entry.openUntil) {
    state.delete(key);
    return false;
  }
  return true;
}

export function recordApiCircuitFailure(url, status, detailMessage = '') {
  if (status === 429) {
    const isSecurityBlock =
      typeof detailMessage === 'string' &&
      detailMessage.toLowerCase().includes('suspicious activity');
    globalPauseUntil = Date.now() + (isSecurityBlock ? SECURITY_BLOCK_PAUSE_MS : GLOBAL_429_PAUSE_MS);
  }
  if (status !== 403 && status !== 429) {
    return;
  }
  const key = normalizePath(url);
  const entry = state.get(key) || { failures: 0, openUntil: 0 };
  entry.failures += 1;
  if (entry.failures >= CIRCUIT_FAILURE_THRESHOLD || status === 429) {
    entry.openUntil = Date.now() + CIRCUIT_COOLDOWN_MS;
    entry.failures = 0;
  }
  state.set(key, entry);
}

export function resetApiCircuit(url) {
  state.delete(normalizePath(url));
}

export function resetAllApiCircuits() {
  state.clear();
  globalPauseUntil = 0;
}
