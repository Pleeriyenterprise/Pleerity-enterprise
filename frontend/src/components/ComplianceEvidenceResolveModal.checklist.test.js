/**
 * Structured checklist / declaration field UX (DATE inputs, legacy string tolerance).
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ChecklistEditor, dateInputValueFromStored } from './ComplianceEvidenceResolveModal';

describe('dateInputValueFromStored', () => {
  it('accepts ISO date strings', () => {
    expect(dateInputValueFromStored('2026-04-01')).toBe('2026-04-01');
  });
  it('returns empty for non-ISO legacy values', () => {
    expect(dateInputValueFromStored('15 March 2026')).toBe('');
    expect(dateInputValueFromStored('')).toBe('');
  });
});

describe('ChecklistEditor', () => {
  it('renders native date inputs for registration DATE fields', () => {
    const schema = [
      { id: 'issue_date', label: 'Issue date', answer_type: 'DATE', required: false },
      { id: 'expiry_date', label: 'Expiry date (if applicable)', answer_type: 'DATE', required: false },
    ];
    render(<ChecklistEditor schema={schema} values={{}} onChange={jest.fn()} />);
    expect(screen.getByTestId('checklist-field-issue_date')).toHaveAttribute('type', 'date');
    expect(screen.getByTestId('checklist-field-expiry_date')).toHaveAttribute('type', 'date');
  });

  it('uses textarea when stored answer is not ISO (legacy evidence)', () => {
    const schema = [{ id: 'issue_date', label: 'Issue date', answer_type: 'DATE', required: false }];
    render(
      <ChecklistEditor
        schema={schema}
        values={{ issue_date: { answer: '31/03/2025' } }}
        onChange={jest.fn()}
      />,
    );
    const el = screen.getByTestId('checklist-field-issue_date');
    expect(el.tagName.toLowerCase()).toBe('textarea');
    expect(el).toHaveValue('31/03/2025');
  });

  it('preserves YES_NO fields without date controls', () => {
    const schema = [{ id: 'declaration_confirmed', label: 'Confirm', answer_type: 'YES_NO', required: true }];
    render(<ChecklistEditor schema={schema} values={{}} onChange={jest.fn()} />);
    expect(screen.getByTestId('checklist-field-declaration_confirmed').tagName.toLowerCase()).toBe('select');
  });

  it('renders SELECT for Right to Rent status values', () => {
    const schema = [
      {
        id: 'right_to_rent_status',
        label: 'Outcome',
        answer_type: 'SELECT',
        required: true,
        choices: [
          { value: 'unlimited', label: 'Unlimited' },
          { value: 'time_limited', label: 'Time limited' },
          { value: 'not_verified', label: 'Not verified' },
        ],
      },
    ];
    render(<ChecklistEditor schema={schema} values={{}} onChange={jest.fn()} />);
    const sel = screen.getByTestId('checklist-field-right_to_rent_status');
    expect(sel.querySelectorAll('option').length).toBeGreaterThanOrEqual(4);
  });

  it('renders SELECT with choices (How to Rent delivery method)', () => {
    const schema = [
      {
        id: 'delivery_method',
        label: 'Delivery method',
        answer_type: 'SELECT',
        required: true,
        choices: [
          { value: 'email', label: 'Email' },
          { value: 'post', label: 'Post' },
        ],
      },
    ];
    const onChange = jest.fn();
    render(<ChecklistEditor schema={schema} values={{}} onChange={onChange} />);
    const sel = screen.getByTestId('checklist-field-delivery_method');
    expect(sel.tagName.toLowerCase()).toBe('select');
    fireEvent.change(sel, { target: { value: 'email' } });
    expect(onChange).toHaveBeenCalledWith('delivery_method', { answer: 'email' });
  });

  it('updates answer from date input', () => {
    const schema = [{ id: 'expiry_date', label: 'Expiry', answer_type: 'DATE', required: false }];
    const onChange = jest.fn();
    render(<ChecklistEditor schema={schema} values={{}} onChange={onChange} />);
    fireEvent.change(screen.getByTestId('checklist-field-expiry_date'), {
      target: { value: '2027-01-10' },
    });
    expect(onChange).toHaveBeenCalledWith('expiry_date', { answer: '2027-01-10' });
  });

  it('uses date picker for legacy TEXT issue_date when value is empty or ISO', () => {
    const schema = [{ id: 'issue_date', label: 'Issue date', answer_type: 'TEXT', required: false }];
    const { rerender } = render(<ChecklistEditor schema={schema} values={{}} onChange={jest.fn()} />);
    expect(screen.getByTestId('checklist-field-issue_date')).toHaveAttribute('type', 'date');
    rerender(
      <ChecklistEditor
        schema={schema}
        values={{ issue_date: { answer: '2026-06-01' } }}
        onChange={jest.fn()}
      />,
    );
    expect(screen.getByTestId('checklist-field-issue_date')).toHaveAttribute('type', 'date');
  });
});
