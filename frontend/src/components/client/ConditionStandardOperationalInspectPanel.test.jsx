import React from 'react';
import { render, screen } from '@testing-library/react';
import ConditionStandardOperationalInspectPanel from './ConditionStandardOperationalInspectPanel';

describe('ConditionStandardOperationalInspectPanel', () => {
  it('renders operational summary for condition standards', () => {
    render(
      <ConditionStandardOperationalInspectPanel
        requirement={{
          requirement_code: 'fitness_for_human_habitation',
          workflow_class: 'GUIDANCE_ONLY',
          active_standard_status_summary: {
            state: 'active_issues_present',
            state_label: 'Open remediation affecting property standard',
            signal_counts: {
              open_issues: 2,
              open_work_orders: 1,
              open_risk_signals: 0,
              open_compliance_gaps: 1,
            },
          },
          client_evidence_disclosure:
            'A single uploaded document does not prove this standard is met.',
        }}
      />,
    );
    expect(screen.getByTestId('condition-standard-operational-inspect-panel')).toBeInTheDocument();
    expect(screen.getByTestId('condition-standard-signal-open_issues')).toHaveTextContent('2');
    expect(screen.getByText(/single uploaded document does not prove/i)).toBeInTheDocument();
  });

  it('returns null for non condition-standard rows', () => {
    const { container } = render(
      <ConditionStandardOperationalInspectPanel requirement={{ requirement_code: 'gas_safety' }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
