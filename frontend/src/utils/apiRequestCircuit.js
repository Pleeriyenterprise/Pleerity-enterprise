/**
 * Lightweight client-side circuit breaker for repeated 403/429 API failures.
 * Prevents retry storms against the same endpoint path.
 */

const CIRCUIT_FAILURE_THRESHOLD = 4;
const CIRCUIT_COOLDOWN_MS = 90_000;
const state = new Map();

function normalizePath(url) {
  return String(url || '')
    .replace(/\?.*$/, '')
    .replace(/^\/api\//, '');
}

export function isApiCircuitOpen(url) {
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

export function recordApiCircuitFailure(url, status) {
  if (status !== 403 && status !== 429) {
    return;
  }
  const key = normalizePath(url);
  const entry = state.get(key) || { failures: 0, openUntil: 0 };
  entry.failures += 1;
  if (entry.failures >= CIRCUIT_FAILURE_THRESHOLD) {
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
}
