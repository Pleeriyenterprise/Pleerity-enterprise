/**
 * Admin-facing lines for compliance_recalc_worker last job_run (Automation Centre).
 * Uses persisted outcome_status / outcome_metrics only. Raw outcome_kind stays in Technical details JSON.
 */

const JOB_ID = 'compliance_recalc_worker';

/**
 * @param {{ lastRun?: object|null }} runInfo
 * @param {object|null} invInfo
 * @returns {object|null}
 */
export function getComplianceRecalcWorkerDisplayLastRun(runInfo, invInfo) {
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
      job_name: JOB_ID,
      status: invInfo.last_status,
      finished_at: invInfo.last_finished_at,
      created_at: invInfo.last_started_at,
      outcome_metrics: invOm,
      outcome_status: invInfo.last_outcome_status,
    };
  }
  return base || null;
}

function _num(v, fallback = 0) {
  if (v == null || v === '') return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

/**
 * @param {object|null|undefined} lastRun
 * @returns {{ headlineLines: string[], showTechnicalDetail: boolean, technicalPayload: object }}
 */
export function formatComplianceRecalcWorkerOutcomeSummary(lastRun) {
  if (!lastRun || typeof lastRun !== 'object') {
    return {
      headlineLines: ['No recent run in the loaded history; refresh or check framework audit.'],
      showTechnicalDetail: false,
      technicalPayload: {},
    };
  }

  const om = lastRun.outcome_metrics || {};
  const outcomeStatus = String(lastRun.outcome_status || '').toLowerCase();
  const status = String(lastRun.status || '').toLowerCase();
  const technicalPayload = { ...om };
  const hasMetrics = Object.keys(om).length > 0;

  const batch = _num(om.queue_items_seen_batch, _num(om.attempted_count, 0));
  const processed = _num(om.queue_items_processed, _num(om.success_count, 0));
  const claimSkipped = _num(om.queue_items_claim_skipped, 0);
  const failedRetry = _num(om.queue_items_failed, 0);
  const dead = _num(om.queue_items_dead, 0);
  const queueEmpty = om.queue_empty === true || batch === 0;

  const lines = [];

  if (status === 'failed') {
    lines.push('No successful compliance recalculations on this run.');
    if (failedRetry > 0) {
      lines.push(
        `${failedRetry} item${failedRetry === 1 ? '' : 's'} failed and will retry.`,
      );
    }
    if (dead > 0) {
      lines.push(
        `${dead} recalculation item${dead === 1 ? '' : 's'} reached terminal failure.`,
      );
    }
    if (!failedRetry && !dead) {
      lines.push('Check error details and technical payload.');
    }
    return { headlineLines: lines, showTechnicalDetail: true, technicalPayload };
  }

  if (status === 'degraded' || outcomeStatus === 'degraded') {
    if (processed > 0) {
      lines.push(
        `${processed} queued compliance recalculation${processed === 1 ? '' : 's'} completed.`,
      );
    }
    if (failedRetry > 0) {
      lines.push(
        `${failedRetry} queue item${failedRetry === 1 ? '' : 's'} failed and will retry.`,
      );
    }
    if (dead > 0) {
      lines.push(
        `${dead} recalculation item${dead === 1 ? '' : 's'} reached terminal failure.`,
      );
    }
    if (!lines.length) {
      lines.push('Last run completed with a degraded outcome.');
    }
    return { headlineLines: lines, showTechnicalDetail: true, technicalPayload };
  }

  if (queueEmpty && outcomeStatus === 'conditional_no_output') {
    lines.push('No compliance recalculation work was waiting.');
    return { headlineLines: lines, showTechnicalDetail: hasMetrics, technicalPayload };
  }

  const contentionOnly =
    batch > 0 &&
    processed === 0 &&
    failedRetry === 0 &&
    dead === 0 &&
    claimSkipped === batch &&
    outcomeStatus === 'success';

  if (contentionOnly) {
    lines.push('Another worker already claimed the queued recalculation items.');
    lines.push('No recalculation work was completed by this run.');
    return { headlineLines: lines, showTechnicalDetail: true, technicalPayload };
  }

  if (processed > 0 && failedRetry === 0 && dead === 0) {
    lines.push(
      `${processed} queued compliance recalculation${processed === 1 ? '' : 's'} completed.`,
    );
    if (claimSkipped > 0) {
      lines.push('Some due items were already being processed by another worker.');
    }
    return { headlineLines: lines, showTechnicalDetail: true, technicalPayload };
  }

  if (hasMetrics) {
    lines.push('See technical details for last run counters.');
    return { headlineLines: lines, showTechnicalDetail: true, technicalPayload };
  }

  return {
    headlineLines: ['Last run has no outcome_metrics in the loaded row (older run).'],
    showTechnicalDetail: false,
    technicalPayload: {},
  };
}
