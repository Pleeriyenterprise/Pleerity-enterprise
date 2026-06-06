import { AUTH_TOKEN_KEY, CONTRACTOR_TOKEN_KEY, getAuthToken, getContractorToken, getPortalAuthToken } from './authStorage';

describe('authStorage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('returns trimmed auth_token', () => {
    localStorage.setItem(AUTH_TOKEN_KEY, '  abc  ');
    expect(getAuthToken()).toBe('abc');
  });

  it('returns null when auth_token missing', () => {
    expect(getAuthToken()).toBeNull();
  });

  it('returns contractor token on contractor paths', () => {
    localStorage.setItem(CONTRACTOR_TOKEN_KEY, 'contractor-jwt');
    expect(getPortalAuthToken('/contractor/dashboard')).toBe('contractor-jwt');
  });

  it('returns auth token on client paths', () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'client-jwt');
    localStorage.setItem(CONTRACTOR_TOKEN_KEY, 'contractor-jwt');
    expect(getPortalAuthToken('/client/dashboard')).toBe('client-jwt');
  });

  it('getContractorToken returns null when unset', () => {
    expect(getContractorToken()).toBeNull();
  });
});
