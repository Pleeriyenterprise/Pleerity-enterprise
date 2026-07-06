/**
 * Presentation-only plan comparison metadata for Billing UI.
 * Must match backend/services/plan_registry.py FEATURE_MATRIX (non-authoritative display).
 * Permission decisions use Runtime Contract capabilities — not this module.
 */

export const BILLING_PLAN_FEATURE_MATRIX = {
  PLAN_1_SOLO: {
    compliance_dashboard: true,
    compliance_score: true,
    compliance_calendar: true,
    email_notifications: true,
    multi_file_upload: true,
    score_trending: true,
    ai_extraction_basic: true,
    ai_extraction_advanced: false,
    extraction_review_ui: false,
    zip_upload: false,
    reports_pdf: false,
    reports_csv: false,
    scheduled_reports: false,
    sms_reminders: false,
    tenant_portal: false,
    webhooks: false,
    white_label_reports: false,
    audit_log_export: false,
  },
  PLAN_2_PORTFOLIO: {
    compliance_dashboard: true,
    compliance_score: true,
    compliance_calendar: true,
    email_notifications: true,
    multi_file_upload: true,
    score_trending: true,
    ai_extraction_basic: true,
    ai_extraction_advanced: false,
    extraction_review_ui: false,
    zip_upload: true,
    reports_pdf: true,
    reports_csv: true,
    scheduled_reports: true,
    sms_reminders: true,
    tenant_portal: false,
    webhooks: false,
    white_label_reports: false,
    audit_log_export: false,
  },
  PLAN_3_PRO: {
    compliance_dashboard: true,
    compliance_score: true,
    compliance_calendar: true,
    email_notifications: true,
    multi_file_upload: true,
    score_trending: true,
    ai_extraction_basic: true,
    ai_extraction_advanced: true,
    extraction_review_ui: true,
    zip_upload: true,
    reports_pdf: true,
    reports_csv: true,
    scheduled_reports: true,
    sms_reminders: true,
    tenant_portal: true,
    webhooks: true,
    white_label_reports: true,
    audit_log_export: true,
  },
};

/** Plan comparison matrix row lookup (display only). */
export function isFeatureEnabledForBillingComparison(planCode, featureKey) {
  const row = BILLING_PLAN_FEATURE_MATRIX[planCode];
  return row ? Boolean(row[featureKey]) : false;
}

/** Count of features included in a plan tier for plan banners and comparison headers. */
export function featureCountForPlanBanner(planCode) {
  const row = BILLING_PLAN_FEATURE_MATRIX[planCode];
  if (!row) return 0;
  return Object.values(row).filter(Boolean).length;
}

/** Property cap for plan banner from billing status or catalog fallback. */
export function planPropertyLimitForDisplay(planCode, billingStatus, displayPlans) {
  if (typeof billingStatus?.properties_limit === 'number' && billingStatus.properties_limit > 0) {
    return billingStatus.properties_limit;
  }
  if (typeof billingStatus?.max_properties === 'number' && billingStatus.max_properties > 0) {
    return billingStatus.max_properties;
  }
  const catalog = displayPlans?.find((p) => p.code === planCode);
  return catalog?.maxProperties ?? null;
}
