/**
 * Risk Check page: 4-step funnel. Step 2 = partial only; Step 3 = email gate; Step 4 = full report.
 * Activate redirects to /intake/start?plan=...&lead_id=...&from=risk-check.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import RiskCheckPage from './RiskCheckPage';

function renderWithProviders(ui) {
  return render(
    <HelmetProvider>
      <MemoryRouter>{ui}</MemoryRouter>
    </HelmetProvider>
  );
}

const mockPost = jest.fn();
const mockNavigate = jest.fn();
jest.mock('../../api/client', () => ({
  __esModule: true,
  default: {
    post: (...args) => mockPost(...args),
  },
}));
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));
jest.mock('sonner', () => ({ toast: { error: jest.fn(), success: jest.fn() } }));

describe('RiskCheckPage', () => {
  beforeEach(() => {
    mockPost.mockReset();
    mockNavigate.mockClear();
    Element.prototype.scrollIntoView = jest.fn();
  });

  it('shows Step 1 questions and progress Step 1 of 4', () => {
    renderWithProviders(<RiskCheckPage />);
    expect(screen.getByText(/Check Your Compliance Risk in 60 Seconds/)).toBeInTheDocument();
    expect(screen.getByText(/Step 1 of 4/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Continue/ })).toBeInTheDocument();
    expect(screen.queryByText(/Your Risk Snapshot/)).not.toBeInTheDocument();
  });

  it('submits questions → partial; email gate → full report; activate redirects with lead_id', async () => {
    mockPost
      .mockResolvedValueOnce({
        data: {
          risk_band: 'MODERATE',
          teaser_text: 'Your responses suggest moderate monitoring risk.',
          blurred_score_hint: 'Moderate range',
          flags_count: 2,
          recommended_plan_code: 'PLAN_2_PORTFOLIO',
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
          recommended_plan_code: 'PLAN_2_PORTFOLIO',
        },
      })
      .mockResolvedValueOnce({ data: { ok: true } });

    renderWithProviders(<RiskCheckPage />);

    const openAndSelect = async (testId, optionText) => {
      const trigger = screen.getByTestId(testId);
      fireEvent.click(trigger);
      const option = await waitFor(() => screen.getByRole('option', { name: optionText }));
      fireEvent.click(option);
    };
    await openAndSelect('risk-gas', 'Valid');
    await openAndSelect('risk-eicr', 'Valid');
    await openAndSelect('risk-tracking', 'Manual');

    fireEvent.click(screen.getByRole('button', { name: /Continue/ }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/risk-check/preview', expect.any(Object));
    });

    // Step 2: partial only; "Get Full Risk Report" (no email form here)
    await waitFor(() => {
      expect(screen.getByText(/Preliminary Result/)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Get Full Risk Report/ })).toBeInTheDocument();
    });
    expect(screen.queryByText(/64/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Get Full Risk Report/ }));

    // Step 3: email gate
    await waitFor(() => {
      expect(screen.getByText(/Send My Full Risk Report/)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Generate My Report/ })).toBeInTheDocument();
    });
    const emailInput = screen.getByPlaceholderText('you@example.com');
    fireEvent.change(emailInput, { target: { value: 'jane@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /Generate My Report/ }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/risk-check/report', expect.objectContaining({
        email: 'jane@example.com',
      }));
    });

    // Step 4: full report
    await waitFor(() => {
      expect(screen.getByText(/Compliance Risk Score \(estimate\): 64 \/ 97/)).toBeInTheDocument();
      expect(screen.getByText(/Activate Monitoring/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/Activate Monitoring/));
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringMatching(/\/intake\/start\?.*lead_id=RISK-ABC123.*from=risk-check/));
    });
  });
});
