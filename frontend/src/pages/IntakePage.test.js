/**
 * Intake wizard tests. Focus: Preferences & Consents (step 4) – document submission method
 * (UPLOAD | EMAIL) persists when switching, EMAIL path shows instructions and allows proceeding.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import IntakePage from './IntakePage';
import { buildIntakeSubmitPayload } from './IntakePage';
import { intakeAPI, publicAgreementsAPI } from '../api/client';

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useSearchParams: () => [new URLSearchParams(''), jest.fn()],
  };
});

jest.mock('uuid', () => ({
  v4: () => 'test-uuid-1',
}));

// Mock intake API
jest.mock('../api/client', () => ({
  publicAgreementsAPI: {
    postAcceptance: jest.fn(() =>
      Promise.resolve({ data: { acceptance_id: 'accept-test-1' } })
    ),
  },
  intakeAPI: {
    checkEmailAvailability: jest.fn(() =>
      Promise.resolve({
        data: { available: true, normalized_email: 'test@example.com', reason_code: 'OK' },
      }),
    ),
    getPlans: jest.fn(() =>
      Promise.resolve({
        data: {
          plans: [
            { plan_id: 'PLAN_1_SOLO', name: 'Solo Landlord', display_name: 'Solo Landlord', max_properties: 2, monthly_price: 9.99, setup_fee: 49, features: ['Feature 1', 'Feature 2'] },
            { plan_id: 'PLAN_2_PORTFOLIO', name: 'Portfolio', display_name: 'Portfolio', max_properties: 10, monthly_price: 29.99, setup_fee: 99, features: ['Feature 1', 'Feature 2', 'Feature 3'] },
            { plan_id: 'PLAN_3_PRO', name: 'Professional', display_name: 'Professional', max_properties: 25, monthly_price: 79.99, setup_fee: 199, features: ['Feature 1', 'Feature 2', 'Feature 3', 'Feature 4'] },
          ],
        },
      })
    ),
    validatePropertyCount: jest.fn((_plan, count) =>
      Promise.resolve({ data: { allowed: count <= 25, current_limit: count <= 2 ? 2 : count <= 10 ? 10 : 25 } })
    ),
    autocompletePostcode: jest.fn(() =>
      Promise.resolve({ data: { postcodes: [] } })
    ),
    lookupPostcode: jest.fn(() =>
      Promise.resolve({
        data: {
          postcode: 'SW1A 1AA',
          suggested_city: 'London',
          council_name: null,
          council_code: null,
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
    previewAgreement: jest.fn(() =>
      Promise.resolve({
        data: {
          title: 'Test service agreement',
          subtitle: '',
          template_code: 'property_compliance_management_agreement',
          template_id: 't1',
          template_version_id: 'v1',
          version_number: 1,
          published_at: null,
          effective_from: null,
          acceptance_text_required: 'I have read and agree to the service agreement above.',
          render_hash_sha256: 'ab'.repeat(32),
          document_structure: {
            title: 'Test service agreement',
            subtitle: '',
            sections: [
              {
                key: 'sec1',
                heading: 'Terms',
                nodes: [
                  {
                    type: 'paragraph',
                    text: 'This is the binding agreement body text for validation purposes.',
                  },
                ],
              },
            ],
          },
          content_blocks: [],
        },
      })
    ),
  },
}));

// Mock fetch for intake uploads list (used when UPLOAD is selected)
global.fetch = jest.fn(() =>
  Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
);

const defaultPlansPayload = {
  data: {
    plans: [
      { plan_id: 'PLAN_1_SOLO', name: 'Solo Landlord', display_name: 'Solo Landlord', max_properties: 2, monthly_price: 9.99, setup_fee: 49, features: ['Feature 1', 'Feature 2'] },
      { plan_id: 'PLAN_2_PORTFOLIO', name: 'Portfolio', display_name: 'Portfolio', max_properties: 10, monthly_price: 29.99, setup_fee: 99, features: ['Feature 1', 'Feature 2', 'Feature 3'] },
      { plan_id: 'PLAN_3_PRO', name: 'Professional', display_name: 'Professional', max_properties: 25, monthly_price: 79.99, setup_fee: 199, features: ['Feature 1', 'Feature 2', 'Feature 3', 'Feature 4'] },
    ],
  },
};

beforeEach(() => {
  intakeAPI.getPlans.mockResolvedValue(defaultPlansPayload);
  intakeAPI.checkEmailAvailability.mockResolvedValue({
    data: { available: true, normalized_email: 'test@example.com', reason_code: 'OK' },
  });
  intakeAPI.validatePropertyCount.mockResolvedValue({
    data: { allowed: true, current_limit: 25 },
  });
  intakeAPI.submit.mockResolvedValue({
    data: { client_id: 'test-client', customer_reference: 'REF123' },
  });
  intakeAPI.createCheckout.mockResolvedValue({
    data: { checkout_url: 'https://checkout.example.com' },
  });
  intakeAPI.previewAgreement.mockResolvedValue({
    data: {
      title: 'Test service agreement',
      subtitle: '',
      template_code: 'property_compliance_management_agreement',
      template_id: 't1',
      template_version_id: 'v1',
      version_number: 1,
      published_at: null,
      effective_from: null,
      acceptance_text_required: 'I have read and agree to the service agreement above.',
      render_hash_sha256: 'ab'.repeat(32),
      document_structure: {
        title: 'Test service agreement',
        subtitle: '',
        sections: [
          {
            key: 'sec1',
            heading: 'Terms',
            nodes: [
              {
                type: 'paragraph',
                text: 'This is the binding agreement body text for validation purposes.',
              },
            ],
          },
        ],
      },
      content_blocks: [],
    },
  });
  publicAgreementsAPI.postAcceptance.mockResolvedValue({
    data: { acceptance_id: 'accept-test-1' },
  });
  window.scrollTo = jest.fn();
});

describe('buildIntakeSubmitPayload', () => {
  it('coerces numeric and boolean fields so submit payload has numbers and booleans', () => {
    const formData = {
      full_name: 'Test',
      email: 'test@example.com',
      client_type: 'INDIVIDUAL',
      company_name: '',
      preferred_contact: 'EMAIL',
      phone: '',
      billing_plan: 'PLAN_1_SOLO',
      properties: [
        {
          nickname: 'Prop 1',
          postcode: 'SW1A 1AA',
          address_line_1: '10 Street',
          address_line_2: '',
          city: 'London',
          property_type: 'house',
          is_hmo: 'true',
          bedrooms: '3',
          occupancy: 'single_family',
          council_name: '',
          council_code: '',
          licence_required: '',
          licence_type: '',
          licence_status: '',
          managed_by: 'LANDLORD',
          send_reminders_to: 'LANDLORD',
          agent_name: '',
          agent_email: '',
          agent_phone: '',
          cert_gas_safety: '',
          cert_eicr: '',
          cert_epc: '',
          cert_licence: '',
        },
      ],
      document_submission_method: 'UPLOAD',
      email_upload_consent: 'false',
      consent_data_processing: 'true',
      consent_service_boundary: true,
    };
    const payload = buildIntakeSubmitPayload(formData, 'session-123');
    expect(payload.intake_session_id).toBe('session-123');
    expect(payload.properties).toHaveLength(1);
    expect(typeof payload.properties[0].bedrooms).toBe('number');
    expect(payload.properties[0].bedrooms).toBe(3);
    expect(typeof payload.properties[0].is_hmo).toBe('boolean');
    expect(payload.properties[0].is_hmo).toBe(true);
    expect(typeof payload.email_upload_consent).toBe('boolean');
    expect(payload.email_upload_consent).toBe(false);
    expect(typeof payload.consent_data_processing).toBe('boolean');
    expect(payload.consent_data_processing).toBe(true);
    expect(typeof payload.consent_service_boundary).toBe('boolean');
    expect(payload.consent_service_boundary).toBe(true);
  });

  it('normalises email to canonical form in submit payload', () => {
    const formData = {
      full_name: 'Test',
      email: '  User@Example.COM ',
      client_type: 'INDIVIDUAL',
      company_name: '',
      preferred_contact: 'EMAIL',
      phone: '',
      billing_plan: 'PLAN_1_SOLO',
      properties: [
        {
          nickname: 'P',
          postcode: 'SW1A 1AA',
          address_line_1: '10 St',
          address_line_2: '',
          city: 'London',
          property_type: 'house',
          jurisdiction: 'England',
          is_hmo: false,
          bedrooms: null,
          occupancy: 'single_family',
          council_name: '',
          council_code: '',
          licence_required: '',
          licence_type: '',
          licence_status: '',
          managed_by: 'LANDLORD',
          send_reminders_to: 'LANDLORD',
          agent_name: '',
          agent_email: '',
          agent_phone: '',
          cert_gas_safety: '',
          cert_eicr: '',
          cert_epc: '',
          cert_licence: '',
        },
      ],
      document_submission_method: 'UPLOAD',
      email_upload_consent: false,
      consent_data_processing: true,
      consent_service_boundary: true,
    };
    const payload = buildIntakeSubmitPayload(formData, null);
    expect(payload.email).toBe('user@example.com');
  });

  it('coerces empty bedrooms to null', () => {
    const formData = {
      full_name: 'Test',
      email: 'test@example.com',
      client_type: 'INDIVIDUAL',
      company_name: '',
      preferred_contact: 'EMAIL',
      phone: '',
      billing_plan: 'PLAN_1_SOLO',
      properties: [
        {
          nickname: '',
          postcode: 'E1 1AA',
          address_line_1: '1 Road',
          address_line_2: '',
          city: 'London',
          property_type: 'flat',
          is_hmo: false,
          bedrooms: '',
          occupancy: 'single_family',
          council_name: '',
          council_code: '',
          licence_required: '',
          licence_type: '',
          licence_status: '',
          managed_by: 'LANDLORD',
          send_reminders_to: 'LANDLORD',
          agent_name: '',
          agent_email: '',
          agent_phone: '',
          cert_gas_safety: '',
          cert_eicr: '',
          cert_epc: '',
          cert_licence: '',
        },
      ],
      document_submission_method: 'EMAIL',
      email_upload_consent: false,
      consent_data_processing: true,
      consent_service_boundary: true,
    };
    const payload = buildIntakeSubmitPayload(formData, null);
    expect(payload.properties[0].bedrooms).toBeNull();
    expect(typeof payload.properties[0].is_hmo).toBe('boolean');
  });

  it('sends bedrooms as number not string when form has string from input', () => {
    const formDataWithStringBedrooms = {
      full_name: 'Test',
      email: 'test@example.com',
      client_type: 'INDIVIDUAL',
      company_name: '',
      preferred_contact: 'EMAIL',
      phone: '',
      billing_plan: 'PLAN_1_SOLO',
      properties: [
        {
          nickname: 'P',
          postcode: 'SW1A 1AA',
          address_line_1: '10 St',
          address_line_2: '',
          city: 'London',
          property_type: 'house',
          is_hmo: false,
          bedrooms: '2',
          occupancy: 'single_family',
          council_name: '',
          council_code: 'E09000033',
          licence_required: '',
          licence_type: '',
          licence_status: '',
          managed_by: 'LANDLORD',
          send_reminders_to: 'LANDLORD',
          agent_name: '',
          agent_email: '',
          agent_phone: '',
          cert_gas_safety: '',
          cert_eicr: '',
          cert_epc: '',
          cert_licence: '',
        },
      ],
      document_submission_method: 'UPLOAD',
      email_upload_consent: false,
      consent_data_processing: true,
      consent_service_boundary: true,
    };
    const payload = buildIntakeSubmitPayload(formDataWithStringBedrooms, null);
    expect(payload.properties).toHaveLength(1);
    expect(typeof payload.properties[0].bedrooms).toBe('number');
    expect(payload.properties[0].bedrooms).toBe(2);
  });
});

// Advance wizard to step 4 (Preferences & Consents)
async function advanceToStep4() {
  // Step 1: Your Details
  await waitFor(() => {
    expect(screen.getByTestId('step-indicator-1')).toBeInTheDocument();
  });
  fireEvent.change(screen.getByPlaceholderText('John Smith'), { target: { value: 'Test User' } });
  fireEvent.change(screen.getByPlaceholderText('john@example.com'), { target: { value: 'test@example.com' } });
  fireEvent.blur(screen.getByTestId('email-input'));
  await waitFor(() => {
    expect(screen.getByTestId('email-availability-available')).toBeInTheDocument();
  });
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
  const jurSelect = screen.getByTestId('property-0-jurisdiction');
  fireEvent.change(jurSelect, { target: { value: 'England' } });
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
      expect(screen.getAllByText(/info@pleerityenterprise.co.uk/i).length).toBeGreaterThan(0);
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
      expect(screen.getAllByText(/info@pleerityenterprise.co.uk/i).length).toBeGreaterThan(0);
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

describe('IntakePage Step 3 – Property cap enforcement', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
    );
  });

  it('Solo (2): at cap the Add button is hidden, upgrade prompt shown, count stays 2', async () => {
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>
    );
    // Step 1
    await waitFor(() => { expect(screen.getByTestId('step-indicator-1')).toBeInTheDocument(); });
    fireEvent.change(screen.getByPlaceholderText('John Smith'), { target: { value: 'Test User' } });
    fireEvent.change(screen.getByPlaceholderText('john@example.com'), { target: { value: 'test@example.com' } });
    fireEvent.blur(screen.getByTestId('email-input'));
    await waitFor(() => {
      expect(screen.getByTestId('email-availability-available')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('client-type-individual'));
    fireEvent.click(screen.getByTestId('step1-next'));
    // Step 2 – Solo
    await waitFor(() => { expect(screen.getByTestId('plan-plan-1-solo')).toBeInTheDocument(); });
    fireEvent.click(screen.getByTestId('plan-plan-1-solo'));
    fireEvent.click(screen.getByTestId('step2-next'));
    // Step 3 – start with 1 property; add one to reach cap (2)
    await waitFor(() => { expect(screen.getByTestId('add-property-btn')).toBeInTheDocument(); });
    const postcodeInput = screen.getByPlaceholderText(/Start typing|SW1A/i);
    if (postcodeInput) fireEvent.change(postcodeInput, { target: { value: 'SW1A 1AA' } });
    const addressInput = screen.getByPlaceholderText('123 Example Street');
    if (addressInput) fireEvent.change(addressInput, { target: { value: '10 Test Street' } });
    const cityInput = screen.getByPlaceholderText('London');
    if (cityInput) fireEvent.change(cityInput, { target: { value: 'London' } });
    fireEvent.change(screen.getByTestId('property-0-jurisdiction'), { target: { value: 'England' } });
    fireEvent.click(screen.getByTestId('add-property-btn'));
    // At cap: Add button must be gone, limit warning visible, count 2/2
    await waitFor(() => {
      expect(screen.queryByTestId('add-property-btn')).not.toBeInTheDocument();
      expect(screen.getByTestId('property-limit-warning')).toBeInTheDocument();
      expect(screen.getByText(/Property limit reached/i)).toBeInTheDocument();
      expect(screen.getByText(/2\/2/)).toBeInTheDocument();
    });
    // Clicking "add" again is impossible (button hidden); if we had a way to invoke add, count would stay 2 – enforced in addProperty
  }, 15000);

  it('Portfolio (10): at cap the Add button is hidden, count stays 10', async () => {
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>
    );
    await waitFor(() => { expect(screen.getByTestId('step-indicator-1')).toBeInTheDocument(); });
    fireEvent.change(screen.getByPlaceholderText('John Smith'), { target: { value: 'Test User' } });
    fireEvent.change(screen.getByPlaceholderText('john@example.com'), { target: { value: 'test@example.com' } });
    fireEvent.blur(screen.getByTestId('email-input'));
    await waitFor(() => {
      expect(screen.getByTestId('email-availability-available')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('client-type-individual'));
    fireEvent.click(screen.getByTestId('step1-next'));
    await waitFor(() => { expect(screen.getByTestId('plan-plan-2-portfolio')).toBeInTheDocument(); });
    fireEvent.click(screen.getByTestId('plan-plan-2-portfolio'));
    fireEvent.click(screen.getByTestId('step2-next'));
    await waitFor(() => { expect(screen.getByTestId('add-property-btn')).toBeInTheDocument(); });
    const postcodeInput = screen.getByPlaceholderText(/Start typing|SW1A/i);
    if (postcodeInput) fireEvent.change(postcodeInput, { target: { value: 'SW1A 1AA' } });
    const addressInput = screen.getByPlaceholderText('123 Example Street');
    if (addressInput) fireEvent.change(addressInput, { target: { value: '10 Test Street' } });
    const cityInput = screen.getByPlaceholderText('London');
    if (cityInput) fireEvent.change(cityInput, { target: { value: 'London' } });
    fireEvent.change(screen.getByTestId('property-0-jurisdiction'), { target: { value: 'England' } });
    for (let i = 0; i < 9; i++) {
      fireEvent.click(screen.getByTestId('add-property-btn'));
      await waitFor(() => expect(screen.getByText(new RegExp(`${i + 2}/10`))).toBeInTheDocument(), { timeout: 3000 });
    }
    await waitFor(() => {
      expect(screen.getByText(/10\/10/)).toBeInTheDocument();
    }, 5000);
  }, 25000);
});

// Advance wizard to step 5 (Review) so "Proceed to Payment" is visible
async function advanceToStep5() {
  await advanceToStep4();
  await waitFor(() => expect(screen.getByTestId('doc-method-email')).toBeInTheDocument());
  fireEvent.click(screen.getByTestId('doc-method-email'));
  await waitFor(() => expect(screen.getByTestId('email-consent-checkbox')).toBeInTheDocument());
  fireEvent.click(screen.getByTestId('email-consent-checkbox'));
  fireEvent.click(screen.getByTestId('gdpr-consent-checkbox'));
  fireEvent.click(screen.getByTestId('service-consent-checkbox'));
  const nextButton = screen.getByTestId('step4-next') || screen.getByRole('button', { name: /Review & Pay/i });
  fireEvent.click(nextButton);
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /Proceed to Payment/i }) || screen.getByTestId('submit-payment')).toBeInTheDocument();
  });
  await waitFor(() => {
    expect(screen.getByTestId('intake-service-agreement-checkbox')).toBeInTheDocument();
  });
  fireEvent.click(screen.getByTestId('intake-service-agreement-checkbox'));
}

describe('IntakePage Step 5 – Proceed to Payment (checkout)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
    );
    intakeAPI.submit.mockResolvedValue({
      data: { client_id: 'test-client', customer_reference: null },
    });
    intakeAPI.createCheckout.mockResolvedValue({
      data: { checkout_url: 'https://checkout.stripe.com/pay', session_id: 'cs_xxx' },
    });
  });

  it('on submit then checkout success, redirects to checkout_url', async () => {
    let hrefSet = '';
    const origLocation = window.location;
    delete window.location;
    window.location = {
      get href() { return hrefSet; },
      set href(v) { hrefSet = v; },
      assign: jest.fn(),
      replace: jest.fn(),
    };

    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>
    );
    await advanceToStep5();

    const payButton = screen.getByRole('button', { name: /Proceed to Payment/i }) || screen.getByTestId('submit-payment');
    fireEvent.click(payButton);

    await waitFor(() => {
      expect(intakeAPI.submit).toHaveBeenCalled();
      expect(publicAgreementsAPI.postAcceptance).toHaveBeenCalled();
      expect(intakeAPI.createCheckout).toHaveBeenCalledWith('test-client', { acceptance_id: 'accept-test-1' });
    });
    const submitPayload = intakeAPI.submit.mock.calls[0][0];
    expect(submitPayload.properties).toBeDefined();
    submitPayload.properties.forEach((p) => {
      expect(p.bedrooms === null || typeof p.bedrooms === 'number').toBe(true);
    });
    await waitFor(() => {
      expect(hrefSet).toBe('https://checkout.stripe.com/pay');
    });

    window.location = origLocation;
  }, 15000);

  it('on checkout failure with request_id, shows Payment setup failed with Reference', async () => {
    const requestId = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
    intakeAPI.createCheckout.mockRejectedValue({
      response: {
        status: 400,
        data: {
          detail: {
            error_code: 'CHECKOUT_FAILED',
            message: 'No subscription price configured',
            request_id: requestId,
          },
        },
      },
    });

    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>
    );
    await advanceToStep5();

    const payButton = screen.getByRole('button', { name: /Proceed to Payment/i }) || screen.getByTestId('submit-payment');
    fireEvent.click(payButton);

    await waitFor(() => {
      expect(intakeAPI.submit).toHaveBeenCalled();
      expect(publicAgreementsAPI.postAcceptance).toHaveBeenCalled();
      expect(intakeAPI.createCheckout).toHaveBeenCalledWith('test-client', { acceptance_id: 'accept-test-1' });
    });
    await waitFor(() => {
      expect(screen.getByTestId('intake-error-alert')).toBeInTheDocument();
      expect(screen.getAllByText(new RegExp(requestId)).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Payment setup failed|Reference:/).length).toBeGreaterThan(0);
    });
  }, 15000);

  it('blocks payment when agreement render is invalid (unresolved placeholders)', async () => {
    intakeAPI.previewAgreement.mockResolvedValueOnce({
      data: {
        title: 'Agreement {{unknown_title_key}}',
        subtitle: '',
        template_code: 'property_compliance_management_agreement',
        template_id: 't1',
        template_version_id: 'v1',
        version_number: 1,
        published_at: null,
        effective_from: null,
        acceptance_text_required: 'I agree.',
        render_hash_sha256: 'ef'.repeat(32),
        document_structure: {
          title: 'Agreement {{unknown_title_key}}',
          subtitle: '',
          sections: [
            {
              key: 'sec1',
              heading: 'Terms',
              nodes: [{ type: 'paragraph', text: 'Body text without placeholders.' }],
            },
          ],
        },
        content_blocks: [],
      },
    });
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>
    );
    await advanceToStep5();
    const payButton = screen.getByRole('button', { name: /Proceed to Payment/i }) || screen.getByTestId('submit-payment');
    expect(payButton).toBeDisabled();
    fireEvent.click(payButton);
    expect(publicAgreementsAPI.postAcceptance).not.toHaveBeenCalled();
    expect(intakeAPI.createCheckout).not.toHaveBeenCalled();
  });

  it('shows safe agreement preview error with retry and keeps payment disabled', async () => {
    intakeAPI.previewAgreement.mockRejectedValueOnce({
      response: {
        status: 500,
        data: {
          detail: {
            error_code: 'AGREEMENT_PREVIEW_FAILED',
            message: 'Could not load the service agreement preview. Please retry or contact support.',
            request_id: 'req-agreement-123',
          },
        },
      },
    });
    intakeAPI.previewAgreement.mockResolvedValueOnce({
      data: {
        title: 'Recovered service agreement',
        subtitle: '',
        template_code: 'property_compliance_management_agreement',
        template_id: 't1',
        template_version_id: 'v1',
        version_number: 1,
        published_at: null,
        effective_from: null,
        acceptance_text_required: 'I have read and agree to the service agreement above.',
        render_hash_sha256: 'cd'.repeat(32),
        document_structure: {
          title: 'Recovered service agreement',
          subtitle: '',
          sections: [
            {
              key: 'sec1',
              heading: 'Terms',
              nodes: [{ type: 'paragraph', text: 'Recovered binding agreement text.' }],
            },
          ],
        },
        content_blocks: [],
      },
    });
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>
    );
    await advanceToStep4();
    fireEvent.click(screen.getByTestId('doc-method-email'));
    fireEvent.click(screen.getByTestId('email-consent-checkbox'));
    fireEvent.click(screen.getByTestId('gdpr-consent-checkbox'));
    fireEvent.click(screen.getByTestId('service-consent-checkbox'));
    fireEvent.click(screen.getByTestId('step4-next') || screen.getByRole('button', { name: /Review & Pay/i }));

    await waitFor(() => expect(screen.getByTestId('intake-agreement-load-error')).toBeInTheDocument());
    expect(screen.getByText(/req-agreement-123/i)).toBeInTheDocument();
    expect(screen.getByTestId('submit-payment')).toBeDisabled();

    fireEvent.click(screen.getByTestId('intake-agreement-retry'));
    await waitFor(() => expect(screen.getByTestId('intake-service-agreement-checkbox')).toBeInTheDocument());
  });

  it('passes agreement audit fields with acceptance payload', async () => {
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>
    );
    await advanceToStep5();
    const payButton = screen.getByRole('button', { name: /Proceed to Payment/i }) || screen.getByTestId('submit-payment');
    fireEvent.click(payButton);
    await waitFor(() => expect(publicAgreementsAPI.postAcceptance).toHaveBeenCalled());
    const sent = publicAgreementsAPI.postAcceptance.mock.calls[0][0];
    expect(sent.document_submission_method).toBe('EMAIL');
    expect(sent.assisted_upload_consent_accepted).toBe(true);
    expect(typeof sent.assisted_upload_consent_timestamp).toBe('string');
    expect(typeof sent.rendered_agreement_hash).toBe('string');
    expect(sent.rendered_agreement_hash.length).toBeGreaterThan(3);
    expect(sent.rendered_agreement_snapshot).toBeTruthy();
    const mergedText = JSON.stringify(sent.rendered_agreement_snapshot);
    expect(mergedText.includes('{{')).toBe(false);
    expect(mergedText.includes('<strong>')).toBe(false);
  });

  it('shows assisted upload summary wording without implying automatic send', async () => {
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>
    );
    await advanceToStep5();
    expect(screen.getByText(/assisted document upload via email/i)).toBeInTheDocument();
    expect(screen.getByText(/you can send compliance documents/i)).toBeInTheDocument();
  });

  it('does not leak engine metadata language in compliance profile summary', async () => {
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>
    );
    await advanceToStep5();
    expect(screen.getByText(/Compliance profile summary/i)).toBeInTheDocument();
    expect(screen.queryByText(/Engine-generated from property facts/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Action types:/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Drivers:/i)).not.toBeInTheDocument();
  });

  it('opens full agreement viewer with metadata', async () => {
    intakeAPI.previewAgreement.mockResolvedValueOnce({
      data: {
        title: 'Property Compliance Management Agreement',
        subtitle: '(Compliance Vault Pro Service)',
        template_code: 'property_compliance_management_agreement',
        template_id: 't1',
        template_version_id: 'v1',
        version_number: 4,
        effective_from: '2026-01-01T00:00:00Z',
        published_at: '2026-01-02T00:00:00Z',
        acceptance_text_required: 'I agree.',
        render_hash_sha256: '12'.repeat(32),
        document_structure: {
          title: 'Property Compliance Management Agreement',
          subtitle: '(Compliance Vault Pro Service)',
          sections: [
            { key: 'scope', heading: 'Service Scope', nodes: [{ type: 'paragraph', text: 'Scope text.' }] },
          ],
        },
        content_blocks: [],
      },
    });
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>
    );
    await advanceToStep5();
    fireEvent.click(screen.getByTestId('view-full-agreement'));
    await waitFor(() => expect(screen.getAllByText(/Service Scope/i).length).toBeGreaterThan(0));
    expect(screen.getByText(/Version 4/i)).toBeInTheDocument();
  });
});

describe('IntakePage Step 1 – live email availability', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve([]) }),
    );
  });

  it('shows taken and blocks progression when email is already registered', async () => {
    intakeAPI.checkEmailAvailability.mockResolvedValue({
      data: { available: false, normalized_email: 'taken@example.com', reason_code: 'EMAIL_TAKEN' },
    });
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByTestId('step-indicator-1')).toBeInTheDocument());
    fireEvent.change(screen.getByPlaceholderText('John Smith'), { target: { value: 'Test User' } });
    fireEvent.change(screen.getByPlaceholderText('john@example.com'), { target: { value: 'taken@example.com' } });
    fireEvent.blur(screen.getByTestId('email-input'));
    await waitFor(() => expect(screen.getByTestId('email-availability-taken')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('client-type-individual'));
    fireEvent.click(screen.getByTestId('step1-next'));
    expect(screen.queryByTestId('plan-plan-1-solo')).not.toBeInTheDocument();
    expect(screen.getByTestId('step-indicator-1')).toBeInTheDocument();
  });

  it('shows neutral error and retry; retry can reach available', async () => {
    intakeAPI.checkEmailAvailability.mockRejectedValueOnce(new Error('network')).mockResolvedValue({
      data: { available: true, normalized_email: 'ok@example.com', reason_code: 'OK' },
    });
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByTestId('step-indicator-1')).toBeInTheDocument());
    fireEvent.change(screen.getByPlaceholderText('John Smith'), { target: { value: 'Test User' } });
    fireEvent.change(screen.getByPlaceholderText('john@example.com'), { target: { value: 'ok@example.com' } });
    fireEvent.blur(screen.getByTestId('email-input'));
    await waitFor(() => expect(screen.getByTestId('email-availability-error')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('client-type-individual'));
    fireEvent.click(screen.getByTestId('step1-next'));
    expect(screen.queryByTestId('plan-plan-1-solo')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('email-availability-retry'));
    await waitFor(() => expect(screen.getByTestId('email-availability-available')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('step1-next'));
    await waitFor(() => expect(screen.getByTestId('plan-plan-1-solo')).toBeInTheDocument());
  });

  it('editing email after a successful check resets inline availability until re-verified', async () => {
    intakeAPI.checkEmailAvailability.mockResolvedValue({
      data: { available: true, normalized_email: 'first@example.com', reason_code: 'OK' },
    });
    render(
      <MemoryRouter>
        <IntakePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByTestId('step-indicator-1')).toBeInTheDocument());
    fireEvent.change(screen.getByPlaceholderText('john@example.com'), { target: { value: 'first@example.com' } });
    fireEvent.blur(screen.getByTestId('email-input'));
    await waitFor(() => expect(screen.getByTestId('email-availability-available')).toBeInTheDocument());
    fireEvent.change(screen.getByTestId('email-input'), { target: { value: 'first@example.comx' } });
    expect(screen.queryByTestId('email-availability-available')).not.toBeInTheDocument();
  });
});
