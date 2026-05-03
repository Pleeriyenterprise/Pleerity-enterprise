/**
 * Admin-facing lines for compliance_score_snapshots (Automation Centre).
 * Uses job_runs outcome_metrics only. Raw outcome_kind stays in Technical details JSON.
 */

const JOB_ID = 'compliance_score_snapshots';

/**
 * @param {{ lastRun?: object|null }} runInfo
 * @param {object|null} invInfo
 * @returns {object|null}
 */
export function getComplianceScoreSnapshotsDisplayLastRun(runInfo, invInfo) {
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

function _num(v, fallback = null) {
  if (v == null || v === '') return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

/**
 * @param {object|null|undefined} lastRun
 * @returns {{ headlineLines: string[], showTechnicalDetail: boolean, technicalPayload: object }}
 */
export function formatComplianceScoreSnapshotsOutcomeSummary(lastRun) {
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

  const considered = _num(om.clients_considered);
  const succeeded = _num(om.clients_succeeded, _num(om.success_count, 0));
  const failedClients = _num(om.clients_failed, 0);
  const propCreated = _num(om.property_snapshots_created, 0);
  const propFailed = _num(om.property_snapshot_failures, 0);
  const propSkipped = _num(om.property_snapshots_skipped_no_score, 0);
  const enumFails = _num(om.property_enumeration_failures, 0);
  const noClients = om.no_clients === true || om.queue_empty === true;

  const technicalPayload = { ...om };
  const hasMetrics = Object.keys(om).length > 0;

  const lines = [];

  const noWork =
    noClients ||
    (outcomeStatus === 'conditional_no_output' &&
      considered === 0 &&
      (succeeded === 0 || succeeded === null) &&
      failedClients === 0);

  if (noWork) {
    lines.push('No ACTIVE clients to snapshot.');
    return { headlineLines: lines, showTechnicalDetail: hasMetrics, technicalPayload };
  }

  if (considered != null && considered > 0) {
    const ok = succeeded != null && succeeded >= 0 ? succeeded : 0;
    lines.push(
      `${ok} of ${considered} ACTIVE client${considered === 1 ? '' : 's'} snapshotted (portfolio score history).`,
    );
  } else if ((succeeded != null && succeeded > 0) || status === 'success' || outcomeStatus === 'success') {
    const ok = succeeded != null && succeeded >= 0 ? succeeded : 0;
    if (ok > 0) {
      lines.push(
        `${ok} ACTIVE client${ok === 1 ? '' : 's'} snapshotted (portfolio score history).`,
      );
    } else if (hasMetrics) {
      lines.push('Last run finished; open technical details for client and property counters.');
    }
  }

  if (failedClients > 0) {
    lines.push(
      `${failedClients} client snapshot${failedClients === 1 ? '' : 's'} failed.`,
    );
  }

  if (propCreated > 0) {
    lines.push(
      `${propCreated} property daily snapshot row${propCreated === 1 ? '' : 's'} created.`,
    );
  }
  if (propFailed > 0) {
    lines.push(`${propFailed} property snapshot failure${propFailed === 1 ? '' : 's'}.`);
  }
  if (propSkipped > 0) {
    lines.push(
      `${propSkipped} propert${propSkipped === 1 ? 'y' : 'ies'} skipped (no stored compliance score on the property).`,
    );
  }
  if (enumFails > 0) {
    lines.push(
      `${enumFails} property-list enumeration issue${enumFails === 1 ? '' : 's'} while snapshotting.`,
    );
  }

  if (lines.length === 0) {
    if (status === 'failed' || outcomeStatus === 'failed') {
      lines.push('Last run failed; check error_message and technical details.');
    } else {
      lines.push('Last run has no outcome_metrics in the loaded row (older run).');
    }
    return {
      headlineLines: lines,
      showTechnicalDetail: hasMetrics,
      technicalPayload: hasMetrics ? technicalPayload : {},
    };
  }

  return { headlineLines: lines, showTechnicalDetail: hasMetrics, technicalPayload };
}
