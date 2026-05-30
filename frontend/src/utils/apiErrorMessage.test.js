import { apiErrorMessage, formatApiDetail, formatDisplayValue } from './apiErrorMessage';

describe('apiErrorMessage utils', () => {
  it('formatApiDetail returns string detail unchanged', () => {
    expect(formatApiDetail('Insufficient permissions')).toBe('Insufficient permissions');
  });

  it('formatApiDetail extracts message from structured detail', () => {
    expect(
      formatApiDetail({
        error_code: 'STEP_UP_REQUIRED',
        message: 'Confirm your password to continue.',
      }),
    ).toBe('Confirm your password to continue.');
  });

  it('apiErrorMessage reads axios-style errors', () => {
    expect(
      apiErrorMessage({
        response: {
          data: {
            detail: { error_code: 'FORBIDDEN', message: 'Not allowed' },
          },
        },
      }),
    ).toBe('Not allowed');
  });

  it('formatDisplayValue never returns objects', () => {
    const out = formatDisplayValue({ error_code: 'X', message: 'Blocked' });
    expect(typeof out).toBe('string');
    expect(out).toBe('Blocked');
  });
});
