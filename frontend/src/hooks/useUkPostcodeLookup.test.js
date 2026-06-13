import { renderHook, act, waitFor } from '@testing-library/react';
import { intakeAPI } from '../api/client';
import { useUkPostcodeLookup } from './useUkPostcodeLookup';

jest.mock('../utils/portalNotifications', () => ({
  toast: { success: jest.fn() },
}));

describe('useUkPostcodeLookup', () => {
  beforeEach(() => {
    jest.spyOn(intakeAPI, 'autocompletePostcode').mockResolvedValue({
      data: {
        postcodes: [{ postcode: 'SW1A 1AA', post_town: 'London', region: 'London' }],
      },
    });
    jest.spyOn(intakeAPI, 'lookupPostcode').mockResolvedValue({
      data: {
        postcode: 'SW1A 1AA',
        suggested_city: 'London',
        country: 'England',
      },
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('debounces autocomplete and calls intake API', async () => {
    const onPostcodeChange = jest.fn();
    const { result } = renderHook(() =>
      useUkPostcodeLookup({
        postcode: '',
        onPostcodeChange,
        showSuccessToast: false,
      })
    );

    act(() => {
      result.current.handlePostcodeChange('SW1');
    });

    await waitFor(() => {
      expect(intakeAPI.autocompletePostcode).toHaveBeenCalledWith('SW1');
    });
  });

  it('lookup applies canonical postcode via onLookupComplete', async () => {
    const onLookupComplete = jest.fn();
    const { result } = renderHook(() =>
      useUkPostcodeLookup({
        postcode: '',
        onPostcodeChange: jest.fn(),
        onLookupComplete,
        showSuccessToast: false,
      })
    );

    await act(async () => {
      await result.current.lookupPostcode('SW1A 1AA', { city: '', jurisdiction: '' });
    });

    expect(intakeAPI.lookupPostcode).toHaveBeenCalled();
    expect(onLookupComplete).toHaveBeenCalledWith(
      expect.objectContaining({ suggested_city: 'London', country: 'England' }),
      expect.objectContaining({ postcode: 'SW1A 1AA', city: 'London', jurisdiction: 'England' })
    );
  });

  it('selectPostcode chooses suggestion and runs lookup', async () => {
    const onPostcodeChange = jest.fn();
    const onLookupComplete = jest.fn();
    const { result } = renderHook(() =>
      useUkPostcodeLookup({
        postcode: '',
        onPostcodeChange,
        onLookupComplete,
        showSuccessToast: false,
      })
    );

    await act(async () => {
      await result.current.selectPostcode(
        { postcode: 'NE1 2PA', post_town: 'Newcastle upon Tyne' },
        { city: '', jurisdiction: '' }
      );
    });

    expect(onPostcodeChange).toHaveBeenCalledWith('NE1 2PA');
    expect(intakeAPI.lookupPostcode).toHaveBeenCalled();
    expect(result.current.showPostcodeDropdown).toBe(false);
    expect(onLookupComplete).toHaveBeenCalled();
  });
});
