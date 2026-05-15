/**
 * Public support chat reply pacing — minimum wait before showing assistant text,
 * without adding delay when the backend is already slow.
 */

/** Target minimum time from request start to showing reply text (ms). */
export const SUPPORT_REPLY_MIN_MS = 400;

/** Upper bound for minimum wait when using jitter (ms). */
export const SUPPORT_REPLY_MAX_MS = 800;

/** Delay after reply text before revealing action chips (ms). */
export const SUPPORT_ACTIONS_REVEAL_MS = 180;

/**
 * Extra wait (ms) so total elapsed reaches a natural minimum.
 * Returns 0 when the network/backend already exceeded the minimum.
 *
 * @param {number} elapsedMs - Time since the user message was sent
 * @param {number} [minMs] - Minimum total wait (default SUPPORT_REPLY_MIN_MS)
 */
export function computeReplyPacingDelay(elapsedMs, minMs = SUPPORT_REPLY_MIN_MS) {
  const elapsed = Math.max(0, Number(elapsedMs) || 0);
  const target = Math.min(
    Math.max(minMs, SUPPORT_REPLY_MIN_MS),
    SUPPORT_REPLY_MAX_MS,
  );
  if (elapsed >= target) return 0;
  return target - elapsed;
}

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, Math.max(0, ms)));
}
