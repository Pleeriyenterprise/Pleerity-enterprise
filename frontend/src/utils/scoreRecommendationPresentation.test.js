import {
  SCORE_RECOMMENDATION_GROUP_THRESHOLD,
  buildPropertyLookup,
  buildScoreRecommendationDisplayUnits,
  matchRequirementsForRecommendation,
  prepareScoreRecommendationPresentation,
  resolveOperationalReason,
  scoreRecommendationGroupingKey,
} from './scoreRecommendationPresentation';

const requirements = [
  {
    requirement_id: 'req-eicr-1',
    property_id: 'p-harbour',
    requirement_code: 'eicr',
    requirement_type: 'eicr',
    status: 'EXPIRING_SOON',
    due_date: new Date(Date.now() + 18 * 86400000).toISOString(),
    display_label: 'Electrical Installation Condition Report (EICR)',
  },
  {
    requirement_id: 'req-eicr-2',
    property_id: 'p-cathedral',
    requirement_code: 'eicr',
    requirement_type: 'eicr',
    status: 'EXPIRING_SOON',
    due_date: new Date(Date.now() + 20 * 86400000).toISOString(),
    display_label: 'Electrical Installation Condition Report (EICR)',
  },
];

const properties = [
  { property_id: 'p-harbour', nickname: 'Harbour Apartment', jurisdiction: 'England', compliance_basis: 'RESIDENTIAL' },
  { property_id: 'p-cathedral', nickname: 'Cathedral View Apartment', jurisdiction: 'Wales', compliance_basis: 'RESIDENTIAL' },
];

describe('scoreRecommendationPresentation', () => {
  it('preserves backend order in display units', () => {
    const recs = [
      { requirement_code: 'GAS', property_id: 'p1', action: 'Renew Gas', impact_points: 10 },
      { requirement_code: 'EICR', property_id: 'p2', action: 'Renew EICR', impact_points: 8 },
      { requirement_code: 'EICR', property_id: 'p3', action: 'Renew EICR', impact_points: 7 },
    ];
    const units = buildScoreRecommendationDisplayUnits(recs, { groupThreshold: 99 });
    expect(units.map((u) => u.type)).toEqual(['individual', 'individual', 'individual']);
    expect(units[0].rec.requirement_code).toBe('GAS');
  });

  it('groups only when threshold met without re-sorting members', () => {
    const recs = Array.from({ length: 4 }, (_, i) => ({
      requirement_code: 'EICR',
      property_id: `p${i}`,
      action: 'Renew EICR before expiry',
      impact_points: 10 - i,
    }));
    const units = buildScoreRecommendationDisplayUnits(recs);
    expect(units).toHaveLength(1);
    expect(units[0].type).toBe('group');
    expect(units[0].items).toHaveLength(4);
  });

  it('does not group when fewer than threshold similar items', () => {
    const recs = [
      { requirement_code: 'EICR', property_id: 'p1', action: 'A' },
      { requirement_code: 'EICR', property_id: 'p2', action: 'B' },
      { requirement_code: 'EICR', property_id: 'p3', action: 'C' },
    ];
    const units = buildScoreRecommendationDisplayUnits(recs);
    expect(units.every((u) => u.type === 'individual')).toBe(true);
  });

  it('exposes property context on each card', () => {
    const lookup = buildPropertyLookup({ properties });
    const pres = prepareScoreRecommendationPresentation(
      {
        requirement_code: 'eicr',
        property_id: 'p-harbour',
        requirement_id: 'req-eicr-1',
        action: 'Renew EICR before expiry',
        impact: '+12 points',
        priority: 'high',
      },
      { requirementsList: requirements, propertyLookup: lookup },
    );
    expect(pres.propertyName).toBe('Harbour Apartment');
    expect(pres.requirementName).toContain('EICR');
    expect(pres.jurisdiction).toBe('England');
    expect(pres.operationalReason).toMatch(/Due in \d+ day/);
    expect(pres.expectedOutcome).toContain('Improves compliance score');
    expect(pres.primaryCtaLabel).toBe('Fix now');
  });

  it('uses distinct identity keys per property-requirement pair', () => {
    const lookup = buildPropertyLookup({ properties });
    const a = prepareScoreRecommendationPresentation(
      { requirement_code: 'eicr', property_id: 'p-harbour', action: 'Renew EICR' },
      { requirementsList: requirements, propertyLookup: lookup },
    );
    const b = prepareScoreRecommendationPresentation(
      { requirement_code: 'eicr', property_id: 'p-cathedral', action: 'Renew EICR' },
      { requirementsList: requirements, propertyLookup: lookup },
    );
    expect(a.identityKey).not.toBe(b.identityKey);
    expect(a.propertyName).not.toBe(b.propertyName);
  });

  it('does not alter grouping key for mixed requirement types', () => {
    expect(scoreRecommendationGroupingKey({ requirement_code: 'EICR' })).not.toBe(
      scoreRecommendationGroupingKey({ requirement_code: 'GAS' }),
    );
  });

  it('matches requirement by property and code without re-ranking list', () => {
    const match = matchRequirementsForRecommendation(
      { requirement_code: 'eicr', property_id: 'p-harbour' },
      requirements,
    );
    expect(match.bestReq?.requirement_id).toBe('req-eicr-1');
  });

  it('resolves overdue operational reason from requirement status', () => {
    const reason = resolveOperationalReason(
      { action: 'Upload evidence' },
      { status: 'OVERDUE' },
    );
    expect(reason).toBe('Prevents overdue compliance');
  });

  it('uses default threshold constant of 4', () => {
    expect(SCORE_RECOMMENDATION_GROUP_THRESHOLD).toBe(4);
  });
});
