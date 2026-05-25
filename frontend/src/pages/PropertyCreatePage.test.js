import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import api, { intakeAPI } from '../api/client';
import PropertyCreatePage from './PropertyCreatePage';

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'landlord@example.com' },
    logout: jest.fn(),
  }),
}));

describe('PropertyCreatePage address lookup', () => {
  beforeEach(() => {
    jest.spyOn(api, 'get').mockResolvedValue({ data: { default_jurisdiction: 'England' } });
    jest.spyOn(api, 'post').mockResolvedValue({ data: { property_id: 'prop-1' } });
    jest.spyOn(intakeAPI, 'autocompletePostcode').mockResolvedValue({
      data: {
        postcodes: [
          {
            postcode: 'SW1A 1AA',
            post_town: 'London',
            admin_district: 'Westminster',
            region: 'London',
          },
        ],
      },
    });
    jest.spyOn(intakeAPI, 'lookupPostcode').mockResolvedValue({
      data: {
        postcode: 'SW1A 1AA',
        suggested_city: 'London',
        country: 'England',
        council_name: null,
        council_code: null,
      },
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  const renderPage = () =>
    render(
      <MemoryRouter>
        <PropertyCreatePage />
      </MemoryRouter>
    );

  it('shows postcode suggestions and fills city after selection', async () => {
    renderPage();

    const postcodeInput = screen.getByTestId('postcode-input');
    fireEvent.change(postcodeInput, { target: { value: 'SW1A' } });

    await waitFor(() => {
      expect(intakeAPI.autocompletePostcode).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getByTestId('postcode-suggestions-dropdown')).toBeInTheDocument();
    });

    fireEvent.mouseDown(screen.getByTestId('postcode-suggestion-0'));

    await waitFor(() => {
      expect(intakeAPI.lookupPostcode).toHaveBeenCalled();
      expect(screen.getByTestId('city-input')).toHaveValue('London');
    });
  });

  it('allows manual address entry without postcode lookup', async () => {
    renderPage();

    fireEvent.change(screen.getByTestId('address-1-input'), { target: { value: '10 Manual Street' } });
    fireEvent.change(screen.getByTestId('city-input'), { target: { value: 'Manchester' } });
    fireEvent.change(screen.getByTestId('postcode-input'), { target: { value: 'M1 1AA' } });

    fireEvent.click(screen.getByTestId('create-property-btn'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/properties/create',
        expect.objectContaining({
          address_line_1: '10 Manual Street',
          city: 'Manchester',
          postcode: 'M1 1AA',
        })
      );
    });
  });
});
