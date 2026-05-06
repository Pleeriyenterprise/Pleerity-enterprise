import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PropertyOperatingHub from './PropertyOperatingHub';
import * as ctaParity from '../../utils/requirementCtaParity';
import * as clientNav from '../../utils/clientPortalNavigation';

const mockNavigate = jest.fn();
const mockOpenGuidedEvidence = jest.fn();

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

jest.mock('../../context/GuidedEvidenceModalContext', () => ({
  useGuidedEvidenceModal: () => ({ openGuidedEvidence: mockOpenGuidedEvidence }),
}));

function hubProps(overrides = {}) {
  return {
    propertyId: 'prop-1',
    hasFeature: () => false,
    tabs: {
      compliance: 'c',
      maintenance: 'm',
      evidence: 'e',
      timeline: 't',
      riskSignals: 'r',
      contractors: 'x',
    },
    onSelectTab: jest.fn(),
    priorityActions: { actions: [], total: 0 },
    riskSignalsData: { signals: [] },
    loadRiskSignals: jest.fn(),
    loadWorkOrders: jest.fn(),
    hubPrioritizedRequirements: [],
    getComplianceSummary: () => ({ overdue: 0, expiringSoon: 0, missingDocuments: 0, valid: 0 }),
    hubActiveWorkOrders: [],
    workOrdersLoading: false,
    evidenceData: null,
    evidenceLoading: false,
    operatingFeedItems: [],
    operatingFeedLoading: false,
    setComplianceStatusFilter: jest.fn(),
    openBookInspectionFromRisk: jest.fn(),
    onOpenNotApplicable: jest.fn(),
    onCreateWoFromRiskDescription: jest.fn(),
    onPlanRestrictedJobError: jest.fn(),
    onRefreshAfterEvidence: jest.fn(),
    priorityTaskRequirementsById: new Map(),
    ...overrides,
  };
}

function renderHub(props) {
  return render(
    <MemoryRouter>
      <PropertyOperatingHub {...props} />
    </MemoryRouter>,
  );
}

describe('PropertyOperatingHub Do this next — requirement CTA parity', () => {
  let execSpy;
  let recordSpy;

  beforeEach(() => {
    mockNavigate.mockReset();
    mockOpenGuidedEvidence.mockReset();
    execSpy = jest.spyOn(ctaParity, 'executeRequirementPrimaryCta');
    recordSpy = jest.spyOn(clientNav, 'recordClientPortalInteraction').mockImplementation(() => {});
  });

  afterEach(() => {
    execSpy.mockRestore();
    recordSpy.mockRestore();
  });

  const requirementPriorityTask = {
    id: 'pri-1',
    source_type: 'requirement',
    source_id: 'req-1',
    property_id: 'prop-1',
    requirement_id: 'req-1',
    title: 'Gas safety',
    primary_action_label: 'Upload',
    metadata: {
      take_action: {
        primary: {
          label: 'Record external assessment',
          kind: 'guided_evidence_resolution',
          handler: 'guided_evidence',
          property_id: 'prop-1',
          requirement_id: 'req-1',
        },
      },
    },
  };

  it('uses executeRequirementPrimaryCta for requirement-backed priority tasks', () => {
    renderHub(
      hubProps({
        priorityActions: { actions: [requirementPriorityTask], total: 1 },
        priorityTaskRequirementsById: new Map([
          [
            'req-1',
            {
              requirement_id: 'req-1',
              property_id: 'prop-1',
              requirement_code: 'gas_safety',
              status: 'MISSING',
              take_action: requirementPriorityTask.metadata.take_action,
            },
          ],
        ]),
      }),
    );

    const btn = screen.getByTestId('property-priority-action-requirement-primary');
    expect(btn).toHaveAttribute('data-requirement-cta-parity', '1');
    fireEvent.click(btn);
    expect(execSpy).toHaveBeenCalledTimes(1);
    expect(execSpy.mock.calls[0][0]).toMatchObject({
      pagePropertyId: 'prop-1',
      requirement: expect.objectContaining({
        requirement_id: 'req-1',
        property_id: 'prop-1',
        take_action: requirementPriorityTask.metadata.take_action,
      }),
    });
    expect(recordSpy).toHaveBeenCalledWith(
      'operating_hub_do_this_next_requirement_primary',
      expect.objectContaining({ property_id: 'prop-1', requirement_id: 'req-1', task_id: 'pri-1' }),
    );
    expect(mockOpenGuidedEvidence).toHaveBeenCalledWith(
      expect.objectContaining({
        propertyId: 'prop-1',
        requirement: expect.objectContaining({ requirement_id: 'req-1' }),
      }),
    );
  });

  it('keeps resolveTaskCta path for work_order tasks', () => {
    const { container } = renderHub(
      hubProps({
        priorityActions: {
          actions: [
            {
              id: 'wo-task',
              source_type: 'work_order',
              source_id: 'wo-9',
              property_id: 'prop-1',
              primary_action_type: 'work_order',
              primary_action_url: '/operations/work-orders?work_order_id=wo-9',
              title: 'Job',
              metadata: {},
            },
          ],
          total: 1,
        },
      }),
    );

    expect(screen.queryByTestId('property-priority-action-requirement-primary')).not.toBeInTheDocument();
    const li = container.querySelector('[data-testid="property-priority-actions-panel"] li');
    expect(li).toBeTruthy();
    expect(
      li.querySelector('button') || li.querySelector('a[href]') || li.textContent.includes('No route'),
    ).toBeTruthy();
    expect(execSpy).not.toHaveBeenCalled();
  });

  it('falls back to legacy CTA when requirement_id is missing on a requirement-shaped task', () => {
    const { container } = renderHub(
      hubProps({
        priorityActions: {
          actions: [
            {
              id: 'bad',
              source_type: 'requirement',
              property_id: 'prop-1',
              metadata: {
                take_action: {
                  primary: { label: 'X', kind: 'guided_evidence_resolution', handler: 'guided_evidence' },
                },
              },
              primary_action_url: '/today',
            },
          ],
          total: 1,
        },
      }),
    );

    expect(screen.queryByTestId('property-priority-action-requirement-primary')).not.toBeInTheDocument();
    const li = container.querySelector('[data-testid="property-priority-actions-panel"] li');
    expect(li).toBeTruthy();
    expect(
      li.querySelector('button') || li.querySelector('a[href]') || li.textContent.includes('No route'),
    ).toBeTruthy();
  });
});
