/**
 * @jest-environment jsdom
 */
import {
  CTA_FOCUS_TARGET_IDS,
  MODAL_CTA_FOCUS_FALLBACK_COPY,
  ctaFocusTargetTestId,
  focusModalCtaTarget,
  resolveModalCtaFocusKey,
  resolveModalCtaFocusKeyFromEntity,
} from './requirementModalCtaFocus';

describe('requirementModalCtaFocus', () => {
  it('maps canonical CTA keys to section targets', () => {
    expect(ctaFocusTargetTestId('complete_compliance_declaration')).toBe(
      CTA_FOCUS_TARGET_IDS.complete_compliance_declaration,
    );
    expect(ctaFocusTargetTestId('attach_supporting_files')).toBe(CTA_FOCUS_TARGET_IDS.attach_supporting_files);
  });

  it('resolves keys from primary labels', () => {
    expect(
      resolveModalCtaFocusKey({
        primary: { label: 'Complete compliance declaration' },
        guidance: {},
      }),
    ).toBe('complete_compliance_declaration');
    expect(
      resolveModalCtaFocusKey({
        primary: { label: 'Add contractor confirmation' },
        guidance: {},
      }),
    ).toBe('add_contractor_confirmation');
    expect(
      resolveModalCtaFocusKey({
        primary: { label: 'Attach supporting files' },
        guidance: {},
      }),
    ).toBe('attach_supporting_files');
  });

  it('resolves evidence mode keys', () => {
    expect(
      resolveModalCtaFocusKey({
        primary: { key: 'STRUCTURED_DECLARATION', label: 'Record declaration' },
        guidance: { recommended_evidence_mode: 'STRUCTURED_DECLARATION' },
      }),
    ).toBe('complete_compliance_declaration');
  });

  it('scrolls, highlights, and focuses target', () => {
    const root = document.createElement('div');
    root.style.height = '200px';
    root.style.overflow = 'auto';
    const section = document.createElement('section');
    section.setAttribute('data-modal-focus-target', CTA_FOCUS_TARGET_IDS.complete_compliance_declaration);
    section.setAttribute('data-modal-focus-label', 'Declaration form');
    const input = document.createElement('textarea');
    section.appendChild(input);
    root.appendChild(section);
    document.body.appendChild(root);

    const onMissing = jest.fn();
    const ok = focusModalCtaTarget({
      scrollRoot: root,
      ctaKey: 'complete_compliance_declaration',
      onMissing,
    });

    expect(ok).toBe(true);
    expect(onMissing).not.toHaveBeenCalled();
    expect(section.classList.contains('modal-cta-focus-highlight')).toBe(true);
    expect(document.activeElement).toBe(input);
    document.body.removeChild(root);
  });

  it('invokes missing fallback when target absent', () => {
    const root = document.createElement('div');
    const onMissing = jest.fn();
    const ok = focusModalCtaTarget({
      scrollRoot: root,
      ctaKey: 'complete_compliance_declaration',
      onMissing,
    });
    expect(ok).toBe(false);
    expect(onMissing).toHaveBeenCalled();
  });

  it('resolves from operational_cognition entity', () => {
    const key = resolveModalCtaFocusKeyFromEntity({
      operational_cognition: {
        primary_action: { key: 'CONTRACTOR_CONFIRMATION', label: 'Add contractor confirmation' },
        requirement_guidance_v1: { recommended_evidence_mode: 'CONTRACTOR_CONFIRMATION' },
      },
    });
    expect(key).toBe('add_contractor_confirmation');
  });

  it('exposes stable fallback copy', () => {
    expect(MODAL_CTA_FOCUS_FALLBACK_COPY).toMatch(/not available on this screen/i);
  });
});
