import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from '../utils/portalNotifications';
import { intakeAPI } from '../api/client';
import { applyPostcodeLookupResult, postcodeFromSuggestion } from '../utils/postcodeLookupApply';
import { normalizeUkPostcode, sanitizePostcodeFieldInput } from '../utils/ukPostcode';

const UK_POSTCODE_COMPACT_RE = /^[A-Z]{1,2}\d[A-Z\d]?\d[A-Z]{2}$/i;

/**
 * Shared UK postcode autocomplete + lookup (intake `/intake/postcode-*` APIs).
 */
export function useUkPostcodeLookup({
  postcode: externalPostcode = '',
  onPostcodeChange,
  onLookupComplete,
  showSuccessToast = true,
  successToastMessage = 'Address details found! Please enter your street address.',
}) {
  const [postcodeInput, setPostcodeInput] = useState(() => String(externalPostcode || '').trim().toUpperCase());
  const [postcodeSuggestions, setPostcodeSuggestions] = useState([]);
  const [showPostcodeDropdown, setShowPostcodeDropdown] = useState(false);
  const [loadingPostcodes, setLoadingPostcodes] = useState(false);
  const [lookingUpPostcode, setLookingUpPostcode] = useState(false);
  const [postcodeError, setPostcodeError] = useState('');
  const [postcodeLookupDone, setPostcodeLookupDone] = useState(false);
  const postcodeRef = useRef(null);

  useEffect(() => {
    setPostcodeInput(String(externalPostcode || '').trim().toUpperCase());
  }, [externalPostcode]);

  const fetchPostcodeSuggestions = useCallback(async (query) => {
    if (!query || query.length < 2) {
      setPostcodeSuggestions([]);
      return;
    }
    setLoadingPostcodes(true);
    try {
      const response = await intakeAPI.autocompletePostcode(query);
      setPostcodeSuggestions(response?.data?.postcodes || []);
    } catch (err) {
      console.error('Postcode autocomplete error:', err);
      setPostcodeSuggestions([]);
    } finally {
      setLoadingPostcodes(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (postcodeInput && postcodeInput.length >= 2 && !postcodeLookupDone) {
        fetchPostcodeSuggestions(postcodeInput);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [postcodeInput, postcodeLookupDone, fetchPostcodeSuggestions]);

  const lookupPostcode = useCallback(
    async (postcode, currentFields = {}) => {
      if (!postcode || postcode.length < 5) return null;
      const cleanPostcode = postcode.trim().toUpperCase().replace(/\s+/g, '');
      if (!UK_POSTCODE_COMPACT_RE.test(cleanPostcode)) {
        return null;
      }

      setLookingUpPostcode(true);
      setPostcodeError('');
      try {
        const response = await intakeAPI.lookupPostcode(postcode);
        const data = response.data || {};
        const applied = applyPostcodeLookupResult(data, {
          postcode,
          city: currentFields.city,
          jurisdiction: currentFields.jurisdiction,
        });
        const canonical = applied.postcode || normalizeUkPostcode(data.postcode || postcode);
        if (canonical) {
          setPostcodeInput(canonical);
          onPostcodeChange?.(canonical);
        }
        onLookupComplete?.(data, applied);
        setPostcodeLookupDone(true);
        if (showSuccessToast) {
          toast.success(successToastMessage);
        }
        return { data, applied };
      } catch (err) {
        if (err.response?.status === 404) {
          setPostcodeError('Postcode not found');
        } else {
          setPostcodeError('Could not lookup postcode');
        }
        return null;
      } finally {
        setLookingUpPostcode(false);
      }
    },
    [onLookupComplete, onPostcodeChange, showSuccessToast, successToastMessage]
  );

  const selectPostcode = useCallback(
    async (suggestion, currentFields = {}) => {
      const postcode = postcodeFromSuggestion(suggestion);
      if (!postcode) return;
      setPostcodeInput(postcode);
      onPostcodeChange?.(postcode);
      setShowPostcodeDropdown(false);
      setPostcodeSuggestions([]);
      await lookupPostcode(postcode, currentFields);
    },
    [lookupPostcode, onPostcodeChange]
  );

  const handlePostcodeChange = useCallback(
    (value) => {
      const upperValue = sanitizePostcodeFieldInput(value);
      setPostcodeInput(upperValue);
      onPostcodeChange?.(upperValue);
      setPostcodeLookupDone(false);
      setPostcodeError('');
      setShowPostcodeDropdown(true);
    },
    [onPostcodeChange]
  );

  const handlePostcodeBlur = useCallback(
    (currentFields = {}) => {
      setTimeout(() => {
        setShowPostcodeDropdown(false);
        if (postcodeInput && postcodeInput.length >= 5 && !postcodeLookupDone) {
          lookupPostcode(postcodeInput, currentFields);
        }
      }, 200);
    },
    [lookupPostcode, postcodeInput, postcodeLookupDone]
  );

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (postcodeRef.current && !postcodeRef.current.contains(e.target)) {
        setShowPostcodeDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return {
    postcodeRef,
    postcodeInput,
    postcodeSuggestions,
    showPostcodeDropdown,
    setShowPostcodeDropdown,
    loadingPostcodes,
    lookingUpPostcode,
    postcodeError,
    postcodeLookupDone,
    selectPostcode,
    lookupPostcode,
    handlePostcodeChange,
    handlePostcodeBlur,
  };
}
