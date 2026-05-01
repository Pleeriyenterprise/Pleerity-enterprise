/**
 * Stream D — score driver remediation helpers.
 * Drivers from `/client/compliance-score` expose heuristic `actions` (UPLOAD/VIEW/CONFIRM); those must not
 * drive client-constructed remediation routes. Actionable CTAs use `requirementTakeActionResolver` only when
 * `requirementUsesServerTakeActionPrimary` is true (canonical `take_action.primary` authority).
 */

/**
 * @param {Array<Record<string, unknown>>} requirements
 * @param {Record<string, unknown>} driver
 * @returns {Record<string, unknown>|null}
 */
export function findRequirementRowForScoreDriver(requirements, driver) {
  if (!driver || typeof driver !== 'object') return null;
  const pid = driver.property_id != null ? String(driver.property_id).trim() : '';
  const rid = driver.requirement_id != null ? String(driver.requirement_id).trim() : '';
  if (!pid || !rid || !Array.isArray(requirements)) return null;
  const row = requirements.find(
    (r) =>
      r &&
      typeof r === 'object' &&
      String(r.property_id ?? '').trim() === pid &&
      String(r.requirement_id ?? '').trim() === rid,
  );
  return row && typeof row === 'object' ? row : null;
}

/**
 * Stable React key: never requirement_id alone (multiple driver rows could share an id in future payloads).
 * @param {Record<string, unknown>} driver
 * @param {number} index
 */
export function scoreDriverRowReactKey(driver, index) {
  const pid = driver?.property_id != null ? String(driver.property_id) : '';
  const rid = driver?.requirement_id != null ? String(driver.requirement_id) : '';
  const st = driver?.status != null ? String(driver.status) : '';
  const ev = driver?.evidence_uploaded ? '1' : '0';
  const gk = driver?.gap_key != null ? String(driver.gap_key) : '';
  const gid = driver?.gap_id != null ? String(driver.gap_id) : '';
  const suffix = gk || gid || String(index);
  return `score-driver-${pid}-${rid}-${st}-${ev}-${suffix}`;
}
