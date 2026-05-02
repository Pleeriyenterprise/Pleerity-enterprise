/**
 * @jest-environment jsdom
 */
import { isFullUkPostcode, normalizeUkPostcode, sanitizePostcodeFieldInput } from './ukPostcode';

describe('ukPostcode', () => {
  describe('isFullUkPostcode', () => {
    it('accepts full UK postcodes including KY10 (outward could be confused with KY0 fragment)', () => {
      expect(isFullUkPostcode('KY10 2AA')).toBe(true);
      expect(isFullUkPostcode('KY102AA')).toBe(true);
      expect(isFullUkPostcode('SW1A 1AA')).toBe(true);
    });

    it('rejects outward-only and truncated fragments', () => {
      expect(isFullUkPostcode('KY0')).toBe(false);
      expect(isFullUkPostcode('KY10')).toBe(false);
      expect(isFullUkPostcode('KY1')).toBe(false);
      expect(isFullUkPostcode('')).toBe(false);
    });

    it('rejects postcode polluted by comma suffix', () => {
      expect(isFullUkPostcode('KY10 2AA, Fife')).toBe(false);
    });
  });

  describe('normalizeUkPostcode', () => {
    it('inserts space before inward when absent', () => {
      expect(normalizeUkPostcode('ky102aa')).toBe('KY10 2AA');
    });

    it('preserves already spaced canonical forms', () => {
      expect(normalizeUkPostcode('SW1A 1AA')).toBe('SW1A 1AA');
    });
  });

  describe('sanitizePostcodeFieldInput', () => {
    it('removes commas and keeps alphanumerics and spaces', () => {
      expect(sanitizePostcodeFieldInput('KY10 2AA, Fife')).toBe('KY10 2AA FIFE');
    });
  });
});
