import { workflowAwareMissingEvidenceLabel } from './evidenceStatus';
import {
  buildSemanticRowFromTaskMetadata,
  combineEvidenceSummaryWithResolvedSubline,
  missingEvidenceLabelFromPriorityTaskMeta,
  projectResolvedRequirementFromPriorityTask,
  projectResolvedRequirementSemantics,
} from './resolvedRequirementViewModel';

function minimalRequirementRow(overrides = {}) {
  return {
    requirement_id: 'r1',
    property_id: 'p1',
    take_action: {
      primary: {
        label: 'Resolve',
        route: '/properties/p1?open=resolve&requirement_id=r1',
      },
    },
    ...overrides,
  };
}

describe('resolvedRequirementViewModel', () => {
  describe('buildSemanticRowFromTaskMetadata', () => {
    it('falls back canonical_requirement_code from requirement_code / requirement_type like Command Centre', () => {
      const row = buildSemanticRowFromTaskMetadata({
        workflow_class: 'GUIDANCE_ONLY',
        requirement_type: 'repairing_standard',
      });
      expect(row.canonical_requirement_code).toBe('repairing_standard');
      expect(row.requirement_code).toBe('repairing_standard');
    });

    it('preserves explicit canonical_requirement_code when set', () => {
      const row = buildSemanticRowFromTaskMetadata({
        canonical_requirement_code: 'gas_safety',
        requirement_code: 'legacy',
      });
      expect(row.canonical_requirement_code).toBe('gas_safety');
      expect(row.requirement_code).toBe('legacy');
    });
  });

  describe('missingEvidenceLabelFromPriorityTaskMeta', () => {
    it('matches workflowAwareMissingEvidenceLabel for the same logical row (parity)', () => {
      const meta = {
        workflow_class: 'GUIDED_DECLARATION',
        canonical_requirement_code: 'right_to_rent',
        requirement_code: 'right_to_rent',
      };
      const fromVm = missingEvidenceLabelFromPriorityTaskMeta(meta);
      const direct = workflowAwareMissingEvidenceLabel(buildSemanticRowFromTaskMetadata(meta));
      expect(fromVm).toBe(direct);
      expect(fromVm).toBe('Declaration not recorded — action required');
    });

    it('uses multi-evidence wording for MULTI_EVIDENCE', () => {
      expect(
        missingEvidenceLabelFromPriorityTaskMeta({
          workflow_class: 'MULTI_EVIDENCE',
          requirement_code: 'fire_alarm',
        }),
      ).toBe('Required evidence incomplete');
    });

    it('uses external assessment wording for EXTERNAL_ASSESSMENT_EVIDENCE', () => {
      expect(
        missingEvidenceLabelFromPriorityTaskMeta({
          workflow_class: 'EXTERNAL_ASSESSMENT_EVIDENCE',
        }),
      ).toBe('Assessment not recorded — action required');
    });
  });

  describe('projectResolvedRequirementSemantics', () => {
    it('normalizes workflow_class and sets multi-evidence / condition-standard hints deterministically', () => {
      const multi = projectResolvedRequirementSemantics(
        minimalRequirementRow({ workflow_class: 'MULTI_EVIDENCE' }),
      );
      expect(multi.workflow_class_normalized).toBe('MULTI_EVIDENCE');
      expect(multi.workflow_class_present).toBe(true);
      expect(multi.is_multi_evidence_style).toBe(true);
      expect(multi.is_condition_standard).toBe(false);

      const cond = projectResolvedRequirementSemantics(
        minimalRequirementRow({
          workflow_class: 'GUIDANCE_ONLY',
          requirement_code: 'fitness_for_human_habitation',
        }),
      );
      expect(cond.is_condition_standard).toBe(true);
      expect(cond.missing_evidence_label).toBe('Condition status needs review');
    });

    it('surfaces MULTI_EVIDENCE chip semantics via evidenceStatusForStatus(MISSING)', () => {
      const p = projectResolvedRequirementSemantics(
        minimalRequirementRow({ workflow_class: 'MULTI_EVIDENCE' }),
      );
      const chip = p.evidenceStatusForStatus('MISSING');
      expect(chip.text).toBe('Evidence incomplete');
      expect(chip.subline).toBe('Required evidence incomplete');
    });

    it('surfaces EXTERNAL_ASSESSMENT_EVIDENCE chip semantics via evidenceStatusForStatus(MISSING)', () => {
      const p = projectResolvedRequirementSemantics(
        minimalRequirementRow({ workflow_class: 'EXTERNAL_ASSESSMENT_EVIDENCE' }),
      );
      const chip = p.evidenceStatusForStatus('MISSING');
      expect(chip.text).toBe('Assessment incomplete');
      expect(chip.subline).toBe('Assessment not recorded — action required');
    });

    it('returns stable projection keys for workflow-only stub rows', () => {
      const p = projectResolvedRequirementSemantics({
        take_action: { primary: { route: '/properties/p/stub', label: 'Stub' } },
      });
      expect(p.workflow_class_normalized).toBe('');
      expect(p.workflow_class_present).toBe(false);
      expect(p.is_multi_evidence_style).toBe(false);
      expect(typeof p.evidenceStatusForStatus).toBe('function');
    });
  });

  describe('combineEvidenceSummaryWithResolvedSubline', () => {
    it('appends workflow subline when distinct from summary', () => {
      const sem = projectResolvedRequirementSemantics(
        minimalRequirementRow({ workflow_class: 'MULTI_EVIDENCE', status: 'MISSING' }),
      );
      const out = combineEvidenceSummaryWithResolvedSubline('3 of 5 evidence items', sem, 'MISSING');
      expect(out).toContain('3 of 5 evidence items');
      expect(out).toContain('Required evidence incomplete');
    });

    it('returns summary only when resolved projection is null', () => {
      expect(combineEvidenceSummaryWithResolvedSubline('Partial', null, 'PENDING')).toBe('Partial');
    });
  });

  describe('projectResolvedRequirementFromPriorityTask', () => {
    it('returns null when task is not requirement-backed with take_action', () => {
      expect(projectResolvedRequirementFromPriorityTask({ source_type: 'issue' }, null)).toBe(null);
    });

    it('projects merged requirement row when priority task is shaped', () => {
      const task = {
        source_type: 'requirement',
        source_id: 'req-9',
        property_id: 'prop-9',
        metadata: {
          workflow_class: 'MULTI_EVIDENCE',
          take_action: {
            primary: {
              label: 'Continue',
              route: '/properties/prop-9?open=resolve&requirement_id=req-9',
            },
          },
        },
      };
      const map = new Map([
        [
          'req-9',
          {
            requirement_id: 'req-9',
            workflow_class: 'DOCUMENT_UPLOAD',
            display_label: 'Gas',
          },
        ],
      ]);
      const p = projectResolvedRequirementFromPriorityTask(task, map);
      expect(p).not.toBeNull();
      expect(p.workflow_class_normalized).toBe('MULTI_EVIDENCE');
      expect(p.is_multi_evidence_style).toBe(true);
    });
  });
});
