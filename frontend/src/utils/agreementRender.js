import { SUPPORT_EMAIL } from '../config/branding';

const PLACEHOLDER_RE = /\{\{[^}]+\}\}/;
const HTML_TAG_RE = /<[^>]+>/;

function textHasUnsafeArtifacts(text) {
  const t = String(text || '');
  return PLACEHOLDER_RE.test(t) || HTML_TAG_RE.test(t);
}

export function renderAgreementForDisplay(agreementCurrent) {
  if (!agreementCurrent) return null;
  const fallbackSections = (agreementCurrent?.content_blocks || []).map((b) => ({
    key: b?.key || '',
    heading: b?.label || b?.key || 'Section',
    nodes: [{ type: 'paragraph', text: b?.content || '' }],
  }));
  const documentStructure = agreementCurrent?.document_structure || {
    title: agreementCurrent?.title || '',
    subtitle: agreementCurrent?.subtitle || '',
    sections: fallbackSections,
  };
  return {
    title: documentStructure?.title || agreementCurrent?.title || '',
    subtitle: documentStructure?.subtitle || agreementCurrent?.subtitle || '',
    document_structure: documentStructure,
    version_number: agreementCurrent?.version_number,
    published_at: agreementCurrent?.published_at,
    effective_from: agreementCurrent?.effective_from,
  };
}

export function buildAgreementRenderContext({
  agreementCurrent,
  formData,
  selectedPlan,
  supportEmail,
  acceptanceTimestampIso,
}) {
  const monthlyFee = Number(selectedPlan?.monthly_price || 0);
  const setupFee = Number(selectedPlan?.setup_fee || 0);
  return {
    provider_company_name: 'Pleerity Enterprise Ltd',
    client_full_name: String(formData?.full_name || '').trim(),
    client_company_name: String(formData?.company_name || '').trim(),
    client_email: String(formData?.email || '').trim(),
    client_address: String(
      formData?.properties?.[0]?.address_line_1 ||
        formData?.properties?.[0]?.postcode ||
        ''
    ).trim(),
    plan_name: selectedPlan?.name || String(formData?.billing_plan || ''),
    billing_interval: 'month',
    monthly_fee: monthlyFee > 0 ? `£${monthlyFee.toFixed(2)}` : '',
    currency: 'GBP',
    onboarding_fee_line: setupFee > 0 ? `£${setupFee.toFixed(2)}` : 'None',
    accepted_signatory_name: String(formData?.full_name || '').trim(),
    acceptance_timestamp: acceptanceTimestampIso || new Date().toISOString(),
    agreement_version: String(agreementCurrent?.version_number || ''),
    support_email: supportEmail || SUPPORT_EMAIL,
  };
}

export function validateAgreementRender(renderedAgreement) {
  if (!renderedAgreement) return { valid: false, reason: 'missing_render' };
  const doc = renderedAgreement.document_structure || {};
  const sections = Array.isArray(doc.sections) ? doc.sections : [];
  if (!sections.length) return { valid: false, reason: 'empty_render' };
  const values = [renderedAgreement.title, renderedAgreement.subtitle];
  for (const s of sections) {
    values.push(s?.heading || '');
    for (const n of s?.nodes || []) {
      if (n?.type === 'bullet_list') {
        for (const i of n?.items || []) values.push(i);
      } else {
        values.push(n?.text || '');
      }
    }
  }
  if (values.every((v) => !String(v || '').trim())) return { valid: false, reason: 'empty_render' };
  if (values.some((v) => textHasUnsafeArtifacts(v))) return { valid: false, reason: 'unsafe_artifact' };
  return { valid: true, reason: null };
}

