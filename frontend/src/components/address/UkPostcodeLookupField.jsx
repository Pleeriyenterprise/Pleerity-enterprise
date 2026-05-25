import React from 'react';
import { CheckCircle, Loader2 } from 'lucide-react';
import { Input } from '../ui/input';

/**
 * Postcode field with autocomplete dropdown (shared intake + dashboard parity).
 */
export function UkPostcodeLookupField({
  label = 'Postcode *',
  postcodeInput,
  onPostcodeChange,
  onPostcodeFocus,
  onPostcodeBlur,
  postcodeRef,
  postcodeSuggestions = [],
  showPostcodeDropdown = false,
  loadingPostcodes = false,
  lookingUpPostcode = false,
  postcodeLookupDone = false,
  postcodeError = '',
  onSelectSuggestion,
  placeholder = 'Start typing... e.g., SW1A',
  testId = 'postcode-input',
  className = '',
  lookupDoneMessage = 'City auto-filled from postcode — enter your street address below',
  hintMessage = 'Select from suggestions or type full postcode (manual entry still works)',
}) {
  return (
    <div className={`space-y-2 ${className}`} ref={postcodeRef}>
      <label className="text-sm font-medium text-gray-700">{label}</label>
      <div className="relative">
        <Input
          value={postcodeInput}
          onChange={(e) => onPostcodeChange(e.target.value)}
          onFocus={onPostcodeFocus}
          onBlur={onPostcodeBlur}
          placeholder={placeholder}
          className={postcodeError ? 'border-red-300' : ''}
          data-testid={testId}
          required
        />
        {(lookingUpPostcode || loadingPostcodes) && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <Loader2 className="w-4 h-4 animate-spin text-electric-teal" />
          </div>
        )}
        {postcodeLookupDone && !lookingUpPostcode && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <CheckCircle className="w-4 h-4 text-green-500" />
          </div>
        )}

        {showPostcodeDropdown && postcodeSuggestions.length > 0 && (
          <div
            className="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto"
            data-testid="postcode-suggestions-dropdown"
          >
            {postcodeSuggestions.map((suggestion, idx) => (
              <button
                key={`${suggestion.postcode || suggestion.outcode}-${idx}`}
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  onSelectSuggestion(suggestion);
                }}
                className="w-full px-4 py-3 text-left hover:bg-gray-50 flex items-center justify-between border-b border-gray-100 last:border-0"
                data-testid={`postcode-suggestion-${idx}`}
              >
                <div>
                  <span className="font-medium text-midnight-blue">{suggestion.postcode}</span>
                  <span className="text-sm text-gray-500 ml-2">
                    {suggestion.post_town || suggestion.admin_district}
                  </span>
                </div>
                <span className="text-xs text-gray-400">{suggestion.region}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      {postcodeError && <p className="text-xs text-red-500">{postcodeError}</p>}
      {postcodeLookupDone && lookupDoneMessage && (
        <p className="text-xs text-green-600">{lookupDoneMessage}</p>
      )}
      {!postcodeLookupDone && !postcodeError && postcodeInput.length >= 2 && hintMessage && (
        <p className="text-xs text-gray-500">{hintMessage}</p>
      )}
    </div>
  );
}
