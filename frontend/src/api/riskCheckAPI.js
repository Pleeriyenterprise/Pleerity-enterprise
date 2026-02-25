/**
 * Risk Check API – Compliance Risk Check (marketing diagnostic funnel).
 * Preview (no PII) and report (persist lead + optional email).
 */
import client from './client';

const PREFIX = '/risk-check';

/**
 * Get risk preview (step 1 answers only). No PII. Returns risk_band, teaser_text, blurred_score_hint, flags_count, recommended_plan_code.
 * @param {Object} body - { property_count, any_hmo, gas_status, eicr_status, tracking_method }
 * @returns {Promise<Object>} Preview result
 */
export async function getPreview(body) {
  const res = await client.post(`${PREFIX}/preview`, body);
  return res.data;
}

/**
 * Submit report with name + email. Persists to risk_leads, sends Email 1, returns full report + lead_id, score (cap 97), recommended_plan_code.
 * @param {Object} body - { ...step1, first_name, email, utm_source?, utm_medium?, utm_campaign? }
 * @returns {Promise<Object>} Report with lead_id, score, risk_band, recommended_plan_code, etc.
 */
export async function postReport(body) {
  const res = await client.post(`${PREFIX}/report`, body);
  return res.data;
}

/**
 * Record CTA click (Activate Monitoring). Sets risk lead status to activated_cta. Idempotent.
 * @param {string} leadId - risk_leads.lead_id
 * @param {string} [selectedPlanCode] - e.g. PLAN_1_SOLO
 * @returns {Promise<Object>} { ok: true }
 */
export async function activate(leadId, selectedPlanCode) {
  const res = await client.post(`${PREFIX}/activate`, { lead_id: leadId, selected_plan_code: selectedPlanCode || null });
  return res.data;
}
