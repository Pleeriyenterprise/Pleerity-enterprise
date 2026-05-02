/**
 * Admin-facing lines for risk_signal_regen_worker last job_run (Automation Centre).
 * Does not use raw outcome_kind as primary copy; technical payload is for <details> only.
 */

/**
 * @param {{ lastRun?: object|null }} runInfo from byJobRuns
 * @param {object|null} invInfo framework audit inventory row
 * @returns {object|null}
 */
export function getRiskSignalRegenDisplayLastRun(runInfo, invInfo) {
  const base = runInfo?.lastRun;
  const invOm = invInfo?.last_outcome_metrics;
  const hasInvOm = invOm && typeof invOm === 'object' && Object.keys(invOm).length > 0;
  if (!hasInvOm) return base || null;
  const baseOm = base?.outcome_metrics;
  const baseOmKeys = baseOm && typeof baseOm === 'object' ? Object.keys(baseOm).length : 0;
  if (baseOmKeys > 0) return base;
  if (base) {
    return {
      ...base,
      outcome_metrics: baseOmKeys > 0 ? baseOm : invOm,
      outcome_status: base.outcome_status ?? invInfo?.last_outcome_status,
    };
  }
  if (invInfo?.last_run_id) {
    return {
      id: invInfo.last_run_id,
      job_name: 'risk_signal_regen_worker',
      status: invInfo.last_status,
      finished_at: invInfo.last_finished_at,
      created_at: invInfo.last_started_at,
      outcome_metrics: invOm,
      outcome_status: invInfo.last_outcome_status,
    };
  }
  return base || null;
}

/**
 * @param {object|null|undefined} lastRun
 * @returns {{ headlineLines: string[], showTechnicalDetail: boolean, technicalPayload: object }}
 */
export function formatRiskSignalRegenOutcomeSummary(lastRun) {
  if (!lastRun || typeof lastRun !== 'object') {
    return {
      headlineLines: ['No recent run in the loaded history; open framework audit or refresh.'],
      showTechnicalDetail: false,
      technicalPayload: {},
    };
  }
  const om = lastRun.outcome_metrics || {};
  const outcomeStatus = String(lastRun.outcome_status || '').toLowerCase();
  const status = String(lastRun.status || '').toLowerCase();
  const reg = Number(om.regenerated_count) || 0;
  const skip = Number(om.skipped_feature_flag_count) || 0;
  const fail = Number(om.failed_count) || 0;
  const queueEmpty = om.queue_empty === true;

  const lines = [];
  const payload = { ...om };

  if (status === 'failed') {
    if (fail > 0) lines.push(`${fail} refresh attempt(s) failed.`);
    else lines.push('Last run completed with failed status.');
    if (reg > 0) {
      lines.push(
        `Risk signals were refreshed for ${reg} ${reg === 1 ? 'property' : 'properties'} (partial batch).`,
      );
    }
    if (skip > 0) {
      lines.push(
        `${skip} ${skip === 1 ? 'property was' : 'properties were'} skipped because predictive maintenance is disabled.`,
      );
    }
    return { headlineLines: lines, showTechnicalDetail: true, technicalPayload: payload };
  }

  if (status === 'degraded' || outcomeStatus === 'degraded') {
    if (reg > 0) {
      lines.push(`Risk signals refreshed for ${reg} ${reg === 1 ? 'property' : 'properties'}.`);
    }
    if (fail > 0) lines.push(`${fail} refresh attempt(s) failed.`);
    if (skip > 0) {
      lines.push(
        `${skip} ${skip === 1 ? 'property was' : 'properties were'} skipped because predictive maintenance is disabled.`,
      );
    }
    if (!lines.length) lines.push('Last run completed with a degraded outcome.');
    return { headlineLines: lines, showTechnicalDetail: true, technicalPayload: payload };
  }

  if (queueEmpty && outcomeStatus === 'conditional_no_output') {
    lines.push('No risk signal refresh work was waiting.');
    return { headlineLines: lines, showTechnicalDetail: true, technicalPayload: payload };
  }

  if (skip > 0 && reg === 0 && fail === 0) {
    lines.push(
      `${skip} ${skip === 1 ? 'property was' : 'properties were'} skipped because predictive maintenance is disabled.`,
    );
    lines.push('No risk signals were refreshed on this run.');
    return { headlineLines: lines, showTechnicalDetail: true, technicalPayload: payload };
  }

  if (reg > 0) {
    lines.push(`Risk signals refreshed for ${reg} ${reg === 1 ? 'property' : 'properties'}.`);
    if (skip > 0) {
      lines.push(
        `${skip} ${skip === 1 ? 'property was' : 'properties were'} skipped because predictive maintenance is disabled.`,
      );
    }
    return { headlineLines: lines, showTechnicalDetail: true, technicalPayload: payload };
  }

  if (Object.keys(om).length > 0) {
    lines.push('See technical details for last run counters.');
    return { headlineLines: lines, showTechnicalDetail: true, technicalPayload: payload };
  }

  return {
    headlineLines: ['Last run has no outcome_metrics (older run or not yet recorded).'],
    showTechnicalDetail: false,
    technicalPayload: {},
  };
}
