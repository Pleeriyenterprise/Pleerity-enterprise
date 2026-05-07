import {
  commandCenterWhyThisMattersLine,
  commandCenterRequirementIntelContext,
} from './clientCommandCenter';

describe('commandCenter governance consumption', () => {
  it('uses requirement_display.short_name on compact requirement cards', () => {
    const line = commandCenterWhyThisMattersLine({
      source_type: 'requirement',
      metadata: {
        action_type: 'missing_document',
        requirement_display: {
          short_name: 'Gas safety',
          canonical_name: 'Gas safety certificate',
        },
        workflow_class: 'GUIDED_DECLARATION',
      },
    });
    expect(line).toMatch(/^Gas safety — /);
  });

  it('uses workflow-aware requirement wording for missing_document', () => {
    const forbidden = ['missing document', 'blocking compliance'].join(' — ');
    const line = commandCenterWhyThisMattersLine({
      source_type: 'requirement',
      metadata: {
        action_type: 'missing_document',
        requirement_display: { short_name: 'Right to rent' },
        workflow_class: 'GUIDED_DECLARATION',
      },
    });
    expect(line).toContain('Declaration not recorded — action required');
    expect(line.toLowerCase()).not.toContain(forbidden);
  });

  it('uses canonical_name in requirement intel/detail seed display label', () => {
    const ctx = commandCenterRequirementIntelContext(
      {
        source_type: 'requirement',
        requirement_id: 'req-11',
        property_id: 'p-11',
        metadata: {
          requirement_display: {
            short_name: 'Gas safety',
            canonical_name: 'Gas safety certificate',
          },
        },
      },
      new Map(),
    );
    expect(ctx.canOpen).toBe(true);
    expect(ctx.seed.display_label).toBe('Gas safety certificate');
  });
});
