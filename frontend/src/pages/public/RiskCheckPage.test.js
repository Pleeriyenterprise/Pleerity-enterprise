/**
 * Risk Check page: Step 2 does not show full report until email is submitted and report API returns.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import RiskCheckPage from './RiskCheckPage';

const mockPost = jest.fn();
jest.mock('../../api/client', () => ({
  __esModule: true,
  default: {
    post: (...args) => mockPost(...args),
  },
}));

jest.mock('sonner', () => ({ toast: { error: jest.fn(), success: jest.fn() } }));

describe('RiskCheckPage', () => {
  beforeEach(() => {
    mockPost.mockReset();
  });

  it('shows Step 1 questions initially', () => {
    render(
      <MemoryRouter>
        <RiskCheckPage />
      </MemoryRouter>
    );
    expect(screen.getByText(/Compliance Monitoring Snapshot/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Calculate Risk/ })).toBeInTheDocument();
    expect(screen.queryByText(/Your Compliance Monitoring Snapshot/)).not.toBeInTheDocument();
  });

  it('shows Step 2 partial reveal after Calculate Risk; full report only after Generate My Risk Report', async () => {
    mockPost
      .mockResolvedValueOnce({
        data: {
          risk_band: 'MODERATE',
          teaser_text: 'Your responses suggest moderate monitoring risk.',
          blurred_score_hint: 'Moderate range',
          flags_count: 2,
        },
      })
      .mockResolvedValueOnce({
        data: {
          lead_id: 'RISK-ABC123',
          score: 64,
          risk_band: 'MODERATE',
          exposure_range_label: 'Some gaps may require attention.',
          flags: [],
          disclaimer_text: 'This assessment is informational.',
          property_breakdown: [{ label: 'Property 1', score: 64, gas: 'Valid', electrical: 'Valid', tracking: 'Manual' }],
        },
      });

    render(
      <MemoryRouter>
        <RiskCheckPage />
      </MemoryRouter>
    );

    // Open each Select and choose an option (gas, eicr, tracking)
    const openAndSelect = async (testId, optionText) => {
      const trigger = screen.getByTestId(testId);
      fireEvent.click(trigger);
      await waitFor(() => screen.getByText(optionText));
      fireEvent.click(screen.getByText(optionText));
    };
    await openAndSelect('risk-gas', 'Valid');
    await openAndSelect('risk-eicr', 'Valid');
    await openAndSelect('risk-tracking', 'Manual reminders');

    fireEvent.click(screen.getByRole('button', { name: /Calculate Risk/ }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/risk-check/preview', expect.any(Object));
    });

    // Step 2: partial reveal and email gate visible; full report not yet
    await waitFor(() => {
      expect(screen.getByText(/Preliminary Risk Assessment/)).toBeInTheDocument();
      expect(screen.getByText(/Get Your Full Compliance Risk Report/)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Generate My Risk Report/ })).toBeInTheDocument();
    });
    expect(screen.queryByText(/Compliance Score: 64%/)).not.toBeInTheDocument();

    // Fill email gate and submit
    const nameInput = screen.getByPlaceholderText('First name');
    const emailInput = screen.getByPlaceholderText('you@example.com');
    fireEvent.change(nameInput, { target: { value: 'Jane' } });
    fireEvent.change(emailInput, { target: { value: 'jane@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /Generate My Risk Report/ }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/risk-check/report', expect.objectContaining({
        first_name: 'Jane',
        email: 'jane@example.com',
      }));
    });

    // Step 3: full report visible
    await waitFor(() => {
      expect(screen.getByText(/Compliance Score: 64%/)).toBeInTheDocument();
      expect(screen.getByText(/Activate Monitoring/)).toBeInTheDocument();
    });
  });
});
