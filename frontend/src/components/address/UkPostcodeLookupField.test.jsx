import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { UkPostcodeLookupField } from './UkPostcodeLookupField';

describe('UkPostcodeLookupField', () => {
  it('calls onSelectSuggestion on suggestion mousedown without blur swallowing click', () => {
    const onSelectSuggestion = jest.fn();
    const suggestions = [
      {
        postcode: 'NE1 2PA',
        post_town: 'Newcastle upon Tyne',
        region: 'North East',
      },
    ];

    render(
      <UkPostcodeLookupField
        postcodeInput="NE1"
        onPostcodeChange={jest.fn()}
        postcodeSuggestions={suggestions}
        showPostcodeDropdown={true}
        onSelectSuggestion={onSelectSuggestion}
        testId="postcode-input"
      />
    );

    expect(screen.getByTestId('postcode-suggestions-dropdown')).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByTestId('postcode-suggestion-0'));
    expect(onSelectSuggestion).toHaveBeenCalledWith(suggestions[0]);
  });
});
