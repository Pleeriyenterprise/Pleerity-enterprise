import {
  buildTodayPresentationModel,
  classifyTaskOperationalBucket,
  formatNeedsActionBannerLine,
  buildListCapDisclosure,
} from './todayPresentationAuthority';

const identityFilter = (list) => list || [];

function makePayload(overrides = {}) {
  return {
    summary: {
      urgent_count: 0,
      habit: {
        urgent_open_total: 0,
        items_due_or_expiring_in_7_days: 0,
        tasks_acknowledged_last_7_days: 0,
      },
      ...overrides.summary,
    },
    bucket_continuation: overrides.bucket_continuation ?? null,
    ...overrides,
  };
}

function makeSections(overrides = {}) {
  return {
    urgent: [],
    upcoming: [],
    in_progress: [],
    recently_completed: [],
    snoozed: [],
    hidden: [],
    ...overrides,
  };
}

function assertPresentationConsistency(model) {
  expect(model.isSemanticallyConsistent).toBe(true);
  const needsActionVisible =
    model.lanes.needsActionNow.length + (model.lanes.primaryExecutionTask ? 1 : 0);
  expect(model.counters.needsAction).toBe(needsActionVisible);
  if (model.counters.needsAction > 0) {
    expect(model.banner.needsAction?.count).toBe(model.counters.needsAction);
  } else {
    expect(model.banner.needsAction).toBeNull();
  }
  expect(model.counters.waiting).toBe(model.lanes.waitingOnOthers.length);
  expect(model.counters.inProgress).toBe(model.lanes.inProgress.length);
  expect(model.counters.snoozed).toBe(model.lanes.snoozed.length);
}

describe('todayPresentationAuthority', () => {
  describe('classifyTaskOperationalBucket — work orders (global rule)', () => {
    it('routes urgent-lane work orders to needs_action_now', () => {
      expect(
        classifyTaskOperationalBucket(
          {
            id: 'wo:1',
            source_type: 'work_order',
            section: 'urgent',
            metadata: { work_order_status: 'OPEN' },
          },
          new Map(),
        ),
      ).toBe('needs_action_now');
    });

    it('routes contractor-wait work orders to waiting_on_others', () => {
      expect(
        classifyTaskOperationalBucket(
          {
            id: 'wo:2',
            source_type: 'work_order',
            section: 'urgent',
            metadata: { work_order_status: 'ASSIGNED' },
          },
          new Map(),
        ),
      ).toBe('waiting_on_others');
    });

    it('keeps server in_progress lane work orders in in_progress', () => {
      expect(
        classifyTaskOperationalBucket(
          {
            id: 'wo:3',
            source_type: 'work_order',
            section: 'in_progress',
            metadata: { work_order_status: 'IN_PROGRESS' },
          },
          new Map(),
        ),
      ).toBe('in_progress');
    });
  });

  describe('buildTodayPresentationModel — regression scenarios', () => {
    it('1. zero urgent items — banner needs-action line absent, counters zero', () => {
      const model = buildTodayPresentationModel({
        payload: makePayload(),
        sections: makeSections(),
        applyFilter: identityFilter,
        requirementsById: new Map(),
        propertyById: new Map(),
      });
      assertPresentationConsistency(model);
      expect(model.banner.needsAction).toBeNull();
      expect(model.counters.needsAction).toBe(0);
      expect(model.counters.inProgress).toBe(0);
      expect(model.falseEmptyDisclosure.genuinelyEmpty).toBe(true);
    });

    it('2. one urgent requirement in Needs Action — banner matches KPI and list', () => {
      const reqMap = new Map([
        ['r1', { requirement_id: 'r1', client_lifecycle_state: 'ACTION_REQUIRED' }],
      ]);
      const task = {
        id: 'req:r1',
        source_type: 'requirement',
        section: 'urgent',
        metadata: { requirement_id: 'r1' },
        take_action: { primary: { label: 'Upload evidence' } },
        filter_tags: ['compliance'],
      };
      const model = buildTodayPresentationModel({
        payload: makePayload({ summary: { urgent_count: 1, habit: { urgent_open_total: 1 } } }),
        sections: makeSections({ urgent: [task] }),
        applyFilter: identityFilter,
        requirementsById: reqMap,
        propertyById: new Map(),
      });
      assertPresentationConsistency(model);
      expect(model.counters.needsAction).toBe(1);
      expect(formatNeedsActionBannerLine(1)?.text).toMatch(/needing action now/);
      expect(model.lanes.primaryExecutionTask?.id).toBe('req:r1');
    });

    it('3. one urgent work order in server in_progress lane — not in Needs Action banner', () => {
      const wo = {
        id: 'wo:99',
        source_type: 'work_order',
        section: 'in_progress',
        metadata: { work_order_status: 'IN_PROGRESS' },
        filter_tags: ['operations'],
      };
      const model = buildTodayPresentationModel({
        payload: makePayload({ summary: { urgent_count: 1, habit: { urgent_open_total: 1 } } }),
        sections: makeSections({ in_progress: [wo], urgent: [] }),
        applyFilter: identityFilter,
        requirementsById: new Map(),
        propertyById: new Map(),
      });
      assertPresentationConsistency(model);
      expect(model.counters.needsAction).toBe(0);
      expect(model.banner.needsAction).toBeNull();
      expect(model.counters.inProgress).toBe(1);
      expect(model.lanes.inProgress[0].id).toBe('wo:99');
    });

    it('4. multiple urgent items split across Needs Action and In Progress', () => {
      const reqMap = new Map([
        ['r1', { requirement_id: 'r1', client_lifecycle_state: 'ACTION_REQUIRED' }],
      ]);
      const reqTask = {
        id: 'req:r1',
        source_type: 'requirement',
        section: 'urgent',
        metadata: { requirement_id: 'r1' },
        take_action: { primary: { label: 'Act' } },
      };
      const woInProgress = {
        id: 'wo:ip',
        source_type: 'work_order',
        section: 'in_progress',
        metadata: { work_order_status: 'IN_PROGRESS' },
      };
      const woNeedsAction = {
        id: 'wo:na',
        source_type: 'work_order',
        section: 'urgent',
        metadata: { work_order_status: 'OPEN' },
        take_action: { primary: { label: 'Review job' } },
      };
      const model = buildTodayPresentationModel({
        payload: makePayload({ summary: { urgent_count: 3, habit: { urgent_open_total: 3 } } }),
        sections: makeSections({
          urgent: [reqTask, woNeedsAction],
          in_progress: [woInProgress],
        }),
        applyFilter: identityFilter,
        requirementsById: reqMap,
        propertyById: new Map(),
      });
      assertPresentationConsistency(model);
      expect(model.counters.needsAction).toBe(2);
      expect(model.counters.inProgress).toBe(1);
      expect(model.banner.needsAction?.count).toBe(2);
    });

    it('5. large urgent list with bucket_continuation — disclosure shown', () => {
      const tasks = Array.from({ length: 3 }, (_, i) => ({
        id: `req:${i}`,
        source_type: 'requirement',
        section: 'urgent',
        metadata: { requirement_id: `r${i}` },
        take_action: { primary: { label: 'Upload' } },
      }));
      const reqMap = new Map(tasks.map((t, i) => [`r${i}`, { requirement_id: `r${i}`, client_lifecycle_state: 'ACTION_REQUIRED' }]));
      const model = buildTodayPresentationModel({
        payload: makePayload({
          summary: { urgent_count: 12, habit: { urgent_open_total: 12 } },
          bucket_continuation: { urgent: 9 },
        }),
        sections: makeSections({ urgent: tasks }),
        applyFilter: identityFilter,
        requirementsById: reqMap,
        propertyById: new Map(),
      });
      assertPresentationConsistency(model);
      expect(model.listCap.show).toBe(true);
      expect(model.listCap.totalHidden).toBe(9);
      expect(model.listCap.lines[0]).toMatch(/beyond this list/);
    });

    it('6. property filter applied — counts match filtered lists', () => {
      const tA = {
        id: 'a',
        source_type: 'requirement',
        section: 'urgent',
        property_id: 'p1',
        metadata: { requirement_id: 'r1' },
        take_action: { primary: { label: 'A' } },
      };
      const tB = {
        id: 'b',
        source_type: 'requirement',
        section: 'urgent',
        property_id: 'p2',
        metadata: { requirement_id: 'r2' },
        take_action: { primary: { label: 'B' } },
      };
      const reqMap = new Map([
        ['r1', { requirement_id: 'r1', client_lifecycle_state: 'ACTION_REQUIRED' }],
        ['r2', { requirement_id: 'r2', client_lifecycle_state: 'ACTION_REQUIRED' }],
      ]);
      const propertyFilter = 'p1';
      const applyFilter = (list) =>
        (list || []).filter((t) => !propertyFilter || String(t.property_id) === propertyFilter);
      const model = buildTodayPresentationModel({
        payload: makePayload({ summary: { urgent_count: 2 } }),
        sections: makeSections({ urgent: [tA, tB] }),
        applyFilter,
        requirementsById: reqMap,
        propertyById: new Map(),
        propertyFilter,
      });
      assertPresentationConsistency(model);
      expect(model.counters.needsAction).toBe(1);
      expect(model.filters.propertyFilter).toBe('p1');
    });

    it('7. category filter applied — counts match filtered lists', () => {
      const compliance = {
        id: 'c1',
        source_type: 'requirement',
        section: 'urgent',
        filter_tags: ['compliance'],
        metadata: { requirement_id: 'r1' },
        take_action: { primary: { label: 'Upload' } },
      };
      const billing = {
        id: 'b1',
        source_type: 'billing',
        section: 'urgent',
        filter_tags: ['billing'],
        take_action: { primary: { label: 'Pay' } },
      };
      const reqMap = new Map([['r1', { requirement_id: 'r1', client_lifecycle_state: 'ACTION_REQUIRED' }]]);
      const applyFilter = (list) => (list || []).filter((t) => (t.filter_tags || []).includes('compliance'));
      const model = buildTodayPresentationModel({
        payload: makePayload({ summary: { urgent_count: 2 } }),
        sections: makeSections({ urgent: [compliance, billing] }),
        applyFilter,
        requirementsById: reqMap,
        propertyById: new Map(),
        categoryFilter: 'compliance',
      });
      assertPresentationConsistency(model);
      expect(model.counters.needsAction).toBe(1);
      expect(model.filters.countsMatchFilteredLists).toBe(true);
    });

    it('8. requirements-only urgent items', () => {
      const reqMap = new Map([
        ['r1', { requirement_id: 'r1', client_lifecycle_state: 'ACTION_REQUIRED' }],
        ['r2', { requirement_id: 'r2', client_lifecycle_state: 'ACTION_REQUIRED' }],
      ]);
      const tasks = [
        { id: 'req:r1', source_type: 'requirement', section: 'urgent', metadata: { requirement_id: 'r1' }, take_action: { primary: { label: 'A' } } },
        { id: 'req:r2', source_type: 'requirement', section: 'upcoming', metadata: { requirement_id: 'r2' }, take_action: { primary: { label: 'B' } } },
      ];
      const model = buildTodayPresentationModel({
        payload: makePayload({ summary: { urgent_count: 2 } }),
        sections: makeSections({ urgent: [tasks[0]], upcoming: [tasks[1]] }),
        applyFilter: identityFilter,
        requirementsById: reqMap,
        propertyById: new Map(),
      });
      assertPresentationConsistency(model);
      expect(model.counters.needsAction).toBe(2);
      expect(model.lanes.inProgress).toHaveLength(0);
    });

    it('9. work-orders-only urgent items land in Needs Action', () => {
      const tasks = [
        {
          id: 'wo:1',
          source_type: 'work_order',
          section: 'urgent',
          metadata: { work_order_status: 'OPEN' },
          take_action: { primary: { label: 'Approve quote' } },
        },
        {
          id: 'wo:2',
          source_type: 'work_order',
          section: 'urgent',
          metadata: { work_order_status: 'OPEN' },
          take_action: { primary: { label: 'Schedule visit' } },
        },
      ];
      const model = buildTodayPresentationModel({
        payload: makePayload({ summary: { urgent_count: 2, habit: { urgent_open_total: 2 } } }),
        sections: makeSections({ urgent: tasks }),
        applyFilter: identityFilter,
        requirementsById: new Map(),
        propertyById: new Map(),
      });
      assertPresentationConsistency(model);
      expect(model.counters.needsAction).toBe(2);
      expect(model.banner.needsAction?.count).toBe(2);
    });

    it('10. mixed requirements and work orders — consistent counts', () => {
      const reqMap = new Map([['r1', { requirement_id: 'r1', client_lifecycle_state: 'ACTION_REQUIRED' }]]);
      const model = buildTodayPresentationModel({
        payload: makePayload({ summary: { urgent_count: 2 } }),
        sections: makeSections({
          urgent: [
            { id: 'req:r1', source_type: 'requirement', section: 'urgent', metadata: { requirement_id: 'r1' }, take_action: { primary: { label: 'Upload' } } },
            { id: 'wo:1', source_type: 'work_order', section: 'urgent', metadata: { work_order_status: 'OPEN' }, take_action: { primary: { label: 'Review' } } },
          ],
        }),
        applyFilter: identityFilter,
        requirementsById: reqMap,
        propertyById: new Map(),
      });
      assertPresentationConsistency(model);
      expect(model.counters.needsAction).toBe(2);
    });

    it('11. fully satisfied landlord — waiting lane, no false urgent banner', () => {
      const reqMap = new Map([
        ['r1', { requirement_id: 'r1', client_lifecycle_state: 'SATISFIED_UNVERIFIED' }],
      ]);
      const model = buildTodayPresentationModel({
        payload: makePayload({ summary: { urgent_count: 0, habit: { urgent_open_total: 0 } } }),
        sections: makeSections({
          upcoming: [
            {
              id: 'req:r1',
              source_type: 'requirement',
              section: 'upcoming',
              metadata: { requirement_id: 'r1', client_lifecycle_state: 'SATISFIED_UNVERIFIED', requirement_satisfied: true },
              title: 'Awaiting verification',
            },
          ],
        }),
        applyFilter: identityFilter,
        requirementsById: reqMap,
        propertyById: new Map(),
      });
      assertPresentationConsistency(model);
      expect(model.counters.needsAction).toBe(0);
      expect(model.counters.waiting).toBe(1);
      expect(model.banner.needsAction).toBeNull();
    });

    it('Dashboard Needs action matches Today operational count, not priority-urgent', () => {
      const upcoming = {
        id: 'wo1',
        source_type: 'work_order',
        section: 'upcoming',
        take_action: { primary: { label: 'Assign' } },
      };
      const model = buildTodayPresentationModel({
        payload: makePayload({ summary: { urgent_count: 0, habit: { urgent_open_total: 0 } } }),
        sections: makeSections({ upcoming: [upcoming] }),
        applyFilter: identityFilter,
        requirementsById: new Map(),
        propertyById: new Map(),
      });
      assertPresentationConsistency(model);
      expect(model.counters.needsAction).toBe(1);
      expect(model.priorityEngine.urgentLaneCount).toBe(0);
    });

    it('12. fresh onboarding landlord — genuinely empty with guidance', () => {
      const model = buildTodayPresentationModel({
        payload: makePayload(),
        sections: makeSections(),
        applyFilter: identityFilter,
        requirementsById: new Map(),
        propertyById: new Map(),
      });
      assertPresentationConsistency(model);
      expect(model.falseEmptyDisclosure.genuinelyEmpty).toBe(true);
      expect(model.falseEmptyDisclosure.message).toMatch(/No open operational items/);
    });
  });

  describe('buildListCapDisclosure', () => {
    it('formats per-bucket continuation lines', () => {
      const d = buildListCapDisclosure({ urgent: 2, in_progress: 1 });
      expect(d.totalHidden).toBe(3);
      expect(d.lines).toHaveLength(2);
    });
  });
});
