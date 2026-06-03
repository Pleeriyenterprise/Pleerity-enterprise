/**
 * REQUIREMENT-MODAL-CTA-FOCUS-CONVERGENCE-01 — scroll/focus targets for guided evidence modals.
 * Display-only UX; does not mutate lifecycle or scoring authority.
 */
import { heroPrimaryFromCognition, getOperationalCognition, getRequirementGuidance } from './operationalCognition';

export const CTA_FOCUS_TARGET_IDS = {
  complete_remaining_compliance_steps: 'modal-focus-component-guidance',
  complete_compliance_declaration: 'modal-focus-declaration-form',
  add_contractor_confirmation: 'modal-focus-contractor-confirmation',
  attach_supporting_files: 'modal-focus-supporting-upload',
  submit_evidence_for_review: 'modal-focus-submit-evidence',
  choose_evidence_method: 'modal-focus-evidence-method',
  inspection_checklist: 'modal-focus-inspection-checklist',
};

const EVIDENCE_MODE_TO_CTA = {
  STRUCTURED_DECLARATION: 'complete_compliance_declaration',
  CONTRACTOR_CONFIRMATION: 'add_contractor_confirmation',
  INSPECTION_CHECKLIST: 'inspection_checklist',
};

export const MODAL_CTA_FOCUS_FALLBACK_COPY =
  'The next step is not available on this screen yet. Please refresh or use another evidence method.';

const LABEL_RULES = [
  { cta: 'complete_remaining_compliance_steps', match: (l) => /remaining|still required|checklist field|component/i.test(l) },
  { cta: 'complete_compliance_declaration', match: (l) => /declaration|structured form|record.*check|assessment record/i.test(l) },
  { cta: 'add_contractor_confirmation', match: (l) => /contractor confirmation|contractor/i.test(l) },
  { cta: 'attach_supporting_files', match: (l) => /supporting file|upload supporting|attach supporting/i.test(l) },
  { cta: 'submit_evidence_for_review', match: (l) => /submit evidence|resubmit|submit for review/i.test(l) },
  { cta: 'choose_evidence_method', match: (l) => /choose evidence|evidence method|select.*method/i.test(l) },
];

/**
 * @param {string} raw
 */
function slugKey(raw) {
  return String(raw || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '');
}

/**
 * Resolve deterministic CTA focus key from cognition primary action and guidance.
 * @param {{ primary?: { key?: string, label?: string }, guidance?: Record<string, unknown>, selectedMode?: string }} ctx
 */
export function resolveModalCtaFocusKey(ctx = {}) {
  const primary = ctx.primary || {};
  const guidance = ctx.guidance || {};
  const rawKey = slugKey(primary.key);
  if (rawKey && CTA_FOCUS_TARGET_IDS[rawKey]) return rawKey;

  const modeKey = slugKey(primary.key).toUpperCase().replace(/-/g, '_');
  if (EVIDENCE_MODE_TO_CTA[modeKey]) return EVIDENCE_MODE_TO_CTA[modeKey];

  const recommendedMode = String(guidance.recommended_evidence_mode || ctx.selectedMode || '').toUpperCase();
  if (EVIDENCE_MODE_TO_CTA[recommendedMode]) return EVIDENCE_MODE_TO_CTA[recommendedMode];

  const label = String(primary.label || guidance.recommended_next_step || '').trim().toLowerCase();
  for (const rule of LABEL_RULES) {
    if (rule.match(label)) return rule.cta;
  }

  if (guidance.missing_actions?.length) return 'complete_remaining_compliance_steps';
  if (recommendedMode === 'STRUCTURED_DECLARATION') return 'complete_compliance_declaration';
  if (recommendedMode === 'CONTRACTOR_CONFIRMATION') return 'add_contractor_confirmation';
  if (recommendedMode === 'INSPECTION_CHECKLIST') return 'inspection_checklist';
  if (guidance.uploaded_not_submitted) return 'submit_evidence_for_review';

  return 'choose_evidence_method';
}

/**
 * @param {Record<string, unknown>|null|undefined} entity
 */
export function resolveModalCtaFocusKeyFromEntity(entity, selectedMode = '') {
  const cognition = getOperationalCognition(entity);
  const primary = heroPrimaryFromCognition(cognition);
  const guidance = getRequirementGuidance(entity);
  return resolveModalCtaFocusKey({ primary, guidance, selectedMode });
}

/**
 * @param {string} ctaKey
 */
export function ctaFocusTargetTestId(ctaKey) {
  return CTA_FOCUS_TARGET_IDS[ctaKey] || null;
}

const HIGHLIGHT_CLASS = 'modal-cta-focus-highlight';

/**
 * Scroll modal body to target section, briefly highlight, focus first actionable control.
 * @param {{ scrollRoot?: HTMLElement|null, ctaKey?: string, onMissing?: () => void, announce?: (msg: string) => void }} opts
 */
export function focusModalCtaTarget({ scrollRoot, ctaKey, onMissing, announce }) {
  const targetId = ctaFocusTargetTestId(ctaKey);
  if (!targetId || !scrollRoot) {
    onMissing?.();
    return false;
  }
  const target = scrollRoot.querySelector(`[data-modal-focus-target="${targetId}"]`);
  if (!target) {
    onMissing?.();
    return false;
  }

  if (typeof target.scrollIntoView === 'function') {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  target.classList.add(HIGHLIGHT_CLASS);
  window.setTimeout(() => target.classList.remove(HIGHLIGHT_CLASS), 1800);

  const focusable = target.querySelector(
    'input:not([disabled]):not([type="hidden"]), textarea:not([disabled]), select:not([disabled]), button:not([disabled])',
  );
  if (focusable && typeof focusable.focus === 'function') {
    focusable.focus({ preventScroll: true });
  } else if (typeof target.focus === 'function') {
    if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
    target.focus({ preventScroll: true });
  }

  const label = target.getAttribute('data-modal-focus-label') || 'Next step';
  announce?.(`Moved to ${label}.`);
  return true;
}
