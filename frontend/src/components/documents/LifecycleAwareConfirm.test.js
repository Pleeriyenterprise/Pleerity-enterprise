/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import LifecycleAwareConfirm, {
  buildLifecycleConfirmPayload,
  isLifecycleConfirmContractPresent,
} from './LifecycleAwareConfirm';
import {
  contractShowsExpiryField,
  initialFormValuesFromExtraction,
  mapLifecycleViolationsToFieldErrors,
  parseLifecycleConfirm422Detail,
} from '../../utils/lifecycleAwareConfirm';

const gasContract = {
  lifecycle_semantics: 'EXPIRY_BASED',
  extraction_profile_id: 'certificate_standard_v1',
  confirm_fields: ['expiry_date'],
  optional_fields: ['issue_date', 'certificate_number'],
  forbidden_fields: [],
  field_labels: {
    expiry_date: 'Certificate expiry date',
    issue_date: 'Issue date',
    certificate_number: 'Certificate number',
  },
};

const legionellaContract = {
  lifecycle_semantics: 'REVIEW_BASED',
  extraction_profile_id: 'legionella_review_v1',
  confirm_fields: ['assessment_date'],
  optional_fields: ['next_review_date', 'risk_level'],
  forbidden_fields: ['expiry_date', 'confirmed_expiry_date', 'extracted_expiry_date'],
  field_labels: {
    assessment_date: 'Assessment date',
    next_review_date: 'Next review date',
    risk_level: 'Risk level',
  },
};

describe('lifecycleAwareConfirm utils', () => {
  it('detects contract presence', () => {
    expect(isLifecycleConfirmContractPresent(gasContract)).toBe(true);
    expect(isLifecycleConfirmContractPresent(null)).toBe(false);
  });

  it('hides expiry for non-EXPIRY contracts', () => {
    expect(contractShowsExpiryField(gasContract)).toBe(true);
    expect(contractShowsExpiryField(legionellaContract)).toBe(false);
  });

  it('builds payload without forbidden fields', () => {
    const payload = buildLifecycleConfirmPayload(legionellaContract, {
      assessment_date: '2026-01-15',
      expiry_date: '2027-01-01',
      next_review_date: '2027-01-15',
    });
    expect(payload.assessment_date).toBe('2026-01-15');
    expect(payload.next_review_date).toBe('2027-01-15');
    expect(payload.expiry_date).toBeUndefined();
  });

  it('initialises values from extraction data', () => {
    const values = initialFormValuesFromExtraction(gasContract, {
      expiry_date: '2027-03-15T00:00:00Z',
      issue_date: '2026-03-15',
    });
    expect(values.expiry_date).toBe('2027-03-15');
    expect(values.issue_date).toBe('2026-03-15');
  });
});

describe('LifecycleAwareConfirm', () => {
  it('renders expiry for EXPIRY_BASED contract', () => {
    render(
      <LifecycleAwareConfirm
        contract={gasContract}
        values={{ expiry_date: '2027-03-15' }}
        onChange={() => {}}
      />,
    );
    expect(screen.getByTestId('lifecycle-confirm-expiry_date')).toBeInTheDocument();
    expect(screen.queryByTestId('lifecycle-confirm-assessment_date')).not.toBeInTheDocument();
  });

  it('renders assessment date and not expiry for REVIEW_BASED', () => {
    render(
      <LifecycleAwareConfirm
        contract={legionellaContract}
        values={{ assessment_date: '2026-06-01' }}
        onChange={() => {}}
      />,
    );
    expect(screen.getByTestId('lifecycle-confirm-assessment_date')).toBeInTheDocument();
    expect(screen.queryByTestId('lifecycle-confirm-expiry_date')).not.toBeInTheDocument();
  });

  it('returns null without contract', () => {
    const { container } = render(
      <LifecycleAwareConfirm contract={null} values={{}} onChange={() => {}} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('calls onChange when field edited', () => {
    const onChange = jest.fn();
    render(
      <LifecycleAwareConfirm
        contract={gasContract}
        values={{ expiry_date: '' }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId('lifecycle-confirm-expiry_date'), {
      target: { value: '2028-01-01' },
    });
    expect(onChange).toHaveBeenCalledWith('expiry_date', '2028-01-01');
  });

  it('renders field-level errors from 422 violations', () => {
    render(
      <LifecycleAwareConfirm
        contract={gasContract}
        values={{ expiry_date: 'bad' }}
        onChange={() => {}}
        fieldErrors={{ expiry_date: 'invalid date format: expiry_date' }}
      />,
    );
    expect(screen.getByTestId('lifecycle-confirm-expiry_date-error')).toHaveTextContent(
      'invalid date format: expiry_date',
    );
  });
});

describe('lifecycle 422 helpers', () => {
  it('maps violations to field errors', () => {
    const mapped = mapLifecycleViolationsToFieldErrors([
      { code: 'LIFECYCLE_FIELD_FORBIDDEN', field: 'expiry_date', message: 'forbidden field present' },
    ]);
    expect(mapped.expiry_date).toBe('forbidden field present');
  });

  it('parses lifecycle 422 detail from axios-like error', () => {
    const parsed = parseLifecycleConfirm422Detail({
      response: {
        status: 422,
        data: {
          detail: {
            code: 'LIFECYCLE_CONFIRM_REJECTED',
            message: 'Rejected',
            violations: [{ field: 'expiry_date', message: 'forbidden' }],
          },
        },
      },
    });
    expect(parsed.code).toBe('LIFECYCLE_CONFIRM_REJECTED');
    expect(parsed.fieldErrors.expiry_date).toBe('forbidden');
  });

  it('returns null for non-lifecycle errors (legacy fallback)', () => {
    expect(
      parseLifecycleConfirm422Detail({
        response: { data: { detail: 'plain string error' } },
      }),
    ).toBeNull();
  });
});
