/**
 * Admin Control Centre / Platform Status — display-only helpers.
 * Maps API/internal identifiers to admin-friendly copy without changing API payloads.
 */

/** Scheduled / worker job_id → short admin title (primary label). */
export const CONTROL_CENTRE_JOB_DISPLAY_NAMES = {
  subscription_lifecycle: 'Subscription lifecycle',
  stripe_subscription_reconcile: 'Stripe subscription reconcile',
  daily_reminders: 'Daily reminders',
  pending_verification_digest: 'Pending verification digest',
  monthly_digest: 'Monthly digest',
  compliance_check_morning: 'Compliance check (morning)',
  compliance_check_evening: 'Compliance check (evening)',
  scheduled_reports: 'Scheduled reports',
  compliance_score_snapshots: 'Compliance score snapshots',
  expiry_rollover_recalc: 'Expiry rollover recalculation',
  contractor_performance_recalc: 'Contractor performance recalculation',
  compliance_recalc_worker: 'Compliance score recalculation worker',
  compliance_recalc_enqueue_property: 'Compliance recalculation enqueue (property)',
  risk_signal_regen_worker: 'Risk signal refresh worker',
  compliance_recalc_sla_monitor: 'Compliance recalculation SLA monitor',
  notification_retry_worker: 'Notification retry worker',
  notification_failure_spike_monitor: 'Notification failure spike monitor',
  sla_watchdog: 'SLA watchdog',
  risk_signal_regen_alert_monitor: 'Risk signal queue alert monitor',
  scheduler_heartbeat: 'Scheduler heartbeat',
  delivery_reconciliation: 'Delivery reconciliation',
  order_delivery_processing: 'Order delivery processing',
  sla_monitoring: 'SLA monitoring',
  stuck_order_detection: 'Stuck order detection',
  queued_order_processing: 'Queued order processing',
  generation_auto_retry_processing: 'Generation auto-retry',
  abandoned_intake_detection: 'Abandoned intake detection',
  lead_followup_processing: 'Lead follow-up processing',
  lead_compliance_gap_detection: 'Lead compliance gap detection',
  lead_inactive_reactivation_detection: 'Lead inactive reactivation',
  pending_payment_lifecycle: 'Pending payment lifecycle',
  client_lifecycle_stale_archive: 'Client lifecycle stale archive',
  client_purge_eligibility_scan: 'Client purge eligibility scan',
  client_test_like_flag_job: 'Client test-like flag job',
  lead_sla_check: 'Lead SLA check',
  checklist_nurture_processing: 'Checklist nurture processing',
  risk_lead_nurture_processing: 'Risk lead nurture processing',
  onboarding_sequence_processing: 'Onboarding sequence processing',
  activation_reminder_processing: 'Activation reminder processing',
  predictive_insights_job: 'Predictive insights job',
  risk_signals_job: 'Risk signals batch job',
  work_order_sla_breach_job: 'Work order SLA breach job',
  work_order_contractor_confirmation_timeout_job: 'Work order contractor confirmation timeout',
};

/** security_incidents.type aggregate keys → admin-readable labels. */
export const THREAT_DETECTION_LABELS = {
  brute_force_login: 'Brute-force login pattern',
  rapid_failed_auth: 'Rapid failed authentication',
  token_reuse_multi_ip: 'Token reuse across multiple IPs',
  suspicious_data_access_pattern: 'Suspicious data access pattern',
  cross_user_data_access_probe: 'Cross-user data access probe',
  endpoint_probing: 'Endpoint probing',
  admin_route_request_spike: 'Admin route request spike',
  webhook_signature_attack: 'Webhook signature attack pattern',
  malformed_request_spike: 'Malformed request spike',
};

export function displayJobName(jobId) {
  if (jobId == null || String(jobId).trim() === '') return '—';
  const id = String(jobId).trim();
  return CONTROL_CENTRE_JOB_DISPLAY_NAMES[id] || snakeToTitleCase(id);
}

function snakeToTitleCase(id) {
  return id
    .split(/_+/g)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');
}

export function overallAutomationHealthLabel(raw) {
  const r = String(raw || '').toLowerCase().replace(/\s+/g, '_');
  switch (r) {
    case 'healthy':
      return 'Healthy';
    case 'degraded':
      return 'Degraded';
    case 'failed':
      return 'Failed (critical automation)';
    case 'attention_required':
    case 'attentionrequired':
      return 'Attention required';
    default:
      return raw ? snakeToTitleCase(String(raw)) : '—';
  }
}

/**
 * Rows for MetricGrid: [label, count] with human-readable threat names only.
 */
export function threatDetectionsToDisplayRows(threatObj) {
  const o = threatObj && typeof threatObj === 'object' ? threatObj : {};
  const entries = Object.entries(o).filter(([, v]) => Number(v) > 0);
  if (entries.length === 0) {
    return [['No threat-type incidents in this window', '0']];
  }
  return entries.map(([key, count]) => [
    THREAT_DETECTION_LABELS[key] || snakeToTitleCase(key),
    String(count),
  ]);
}

/** Raw JSON for diagnostics (stable stringify). */
export function threatDetectionsRawJson(threatObj) {
  try {
    return JSON.stringify(threatObj && typeof threatObj === 'object' ? threatObj : {}, null, 0);
  } catch {
    return '{}';
  }
}

export function complianceStatusBucketLabel(key) {
  const k = String(key || '').toUpperCase();
  if (k === 'UNKNOWN') return 'Unclassified';
  if (k === 'GREEN' || k === 'AMBER' || k === 'RED') return k.charAt(0) + k.slice(1).toLowerCase();
  return snakeToTitleCase(String(key));
}

export function complianceScoreBandLabel(key) {
  const k = String(key || '');
  if (k === 'unknown') return 'No score stored';
  if (k === '0_39') return '0–39';
  if (k === '40_59') return '40–59';
  if (k === '60_79') return '60–79';
  if (k === '80_100') return '80–100';
  return snakeToTitleCase(k);
}

/**
 * Light touch on backend scoring_notes strings — display layer only.
 */
export function humanizeScoringNoteText(text) {
  if (text == null || typeof text !== 'string') return '';
  let s = text;
  s = s.replace(/\bdelivery_unknown\b/g, 'delivery confirmation still pending');
  s = s.replace(/\bpast_due\b/g, 'past-due');
  s = s.replace(/\bstripe_events\b/g, 'Stripe events');
  return s;
}

export function humanizeScoringNoteKey(key) {
  const k = String(key || '');
  const map = {
    automation_health: 'Automation health',
    security_risk: 'Security risk',
    revenue_health: 'Revenue health',
    job_confidence: 'Job confidence',
  };
  return map[k] || snakeToTitleCase(k);
}
