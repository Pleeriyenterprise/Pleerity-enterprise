/**
 * Intake wizard tests. Focus: Preferences & Consents (step 4) – document submission method
 * (UPLOAD | EMAIL) persists when switching, EMAIL path shows instructions and allows proceeding.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import IntakePage from './IntakePage';

// Mock intake API
jest.mock('../api/client', () => ({
  intakeAPI: {
    getPlans: jest.fn(() =>
      Promise.resolve({
        data: {
          plans: [
            {
              plan_id: 'PLAN_1_SOLO',
              name: 'Solo Landlord',
              display_name: 'Solo Landlord',
              max_properties: 2,
              monthly_price: 9.99,
              setup_fee: 49,
              features: ['Feature 1', 'Feature 2'],
            },
          ],
        },
      })
    ),
    submit: jest.fn(() =>
      Promise.resolve({
        data: { client_id: 'test-client', customer_reference: 'REF123' },
      })
    ),
    createCheckout: jest.fn(() =>
      Promise.resolve({ data: { checkout_url: 'https://checkout.example.com' } })
    ),
  },
}));

// Mock fetch for intake uploads list (used when UPLOAD is selected)
global.fetch = jest.fn(() =>
  Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
);

// Advance wizard to step 4 (Preferences & Consents)
async function advanceToStep4() {
  // Step 1: Your Details
  await waitFor(() => {
    expect(screen.getByTestId('step-indicator-1')).toBeInTheDocument();
  });
  fireEvent.change(screen.getByPlaceholderText('John Smith'), { target: { value: 'Test User' } });
  fireEvent.change(screen.getByPlaceholderText('john@example.com'), { target: { value: 'test@example.com' } });
  fireEvent.click(screen.getByTestId('client-type-individual'));
  fireEvent.click(screen.getByTestId('step1-next'));

  // Step 2: Select Plan
  await waitFor(() => {
    expect(screen.getByTestId('plan-plan-1-solo')).toBeInTheDocument();
  });
  fireEvent.click(screen.getByTestId('plan-plan-1-solo'));
  fireEvent.click(screen.getByTestId('step2-next'));

  // Step 3: Properties – minimal required fields (postcode, address, city)
  await waitFor(() => {
    expect(screen.getByTestId('step3-next')).toBeInTheDocument();
  });
  const postcodeInput = screen.getByPlaceholderText(/Start typing|SW1A/i);
  if (postcodeInput) fireEvent.change(postcodeInput, { target: { value: 'SW1A 1AA' } });
  const addressInput = screen.getByPlaceholderText('123 Example Street');
  if (addressInput) fireEvent.change(addressInput, { target: { value: '10 Test Street' } });
  const cityInput = screen.getByPlaceholderText('London');
  if (cityInput) fireEvent.change(cityInput, { target: { value: 'London' } });
  fireEvent.click(screen.getByTestId('step3-next'));
}

describe('IntakePage Step 4 – Preferences & Consents', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
    );
  });

  it('switching between UPLOAD and EMAIL preserves selection and does not lose state', async () => {
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>
    );

    await advanceToStep4();

    await waitFor(() => {
      expect(screen.getByTestId('doc-method-upload')).toBeInTheDocument();
      expect(screen.getByTestId('doc-method-email')).toBeInTheDocument();
    });

    // Select EMAIL – email instructions panel should appear, dropzone hidden
    fireEvent.click(screen.getByTestId('doc-method-email'));
    await waitFor(() => {
      expect(screen.getByText(/info@pleerityenterprise.co.uk/i)).toBeInTheDocument();
      expect(screen.getByText(/Send your documents to/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Drop files here or click to browse/i)).not.toBeInTheDocument();

    // Switch to UPLOAD – dropzone should appear
    fireEvent.click(screen.getByTestId('doc-method-upload'));
    await waitFor(() => {
      expect(screen.getByText(/Drop files here or click to browse/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Send your documents to/i)).not.toBeInTheDocument();

    // Switch back to EMAIL – selection must persist (email panel visible again)
    fireEvent.click(screen.getByTestId('doc-method-email'));
    await waitFor(() => {
      expect(screen.getByText(/info@pleerityenterprise.co.uk/i)).toBeInTheDocument();
      expect(screen.getByText(/Send your documents to/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Drop files here or click to browse/i)).not.toBeInTheDocument();
  });

  it('when EMAIL is selected, user can proceed to Review & Pay after checking consents', async () => {
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>
    );

    await advanceToStep4();

    await waitFor(() => {
      expect(screen.getByTestId('doc-method-email')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('doc-method-email'));
    await waitFor(() => {
      expect(screen.getByTestId('email-consent-checkbox')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('email-consent-checkbox'));
    fireEvent.click(screen.getByTestId('gdpr-consent-checkbox'));
    fireEvent.click(screen.getByTestId('service-consent-checkbox'));

    const nextButton = screen.getByTestId('step4-next') || screen.getByRole('button', { name: /Review & Pay/i });
    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(screen.getByText(/Review Your Details/i) || screen.getByTestId('submit-payment')).toBeInTheDocument();
    });
  }, 15000);
});
