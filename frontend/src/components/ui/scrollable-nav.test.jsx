/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { ScrollableNav, ScrollableUnderlineNav, scrollableNavItemClass } from './scrollable-nav';

describe('ScrollableNav', () => {
  it('renders horizontal scroll track with touch-friendly items', () => {
    render(
      <ScrollableNav ariaLabel="Test tabs" data-testid="tabs">
        <button type="button" className={scrollableNavItemClass(true)} data-testid="tab-a">
          Alpha
        </button>
        <button type="button" className={scrollableNavItemClass(false)} data-testid="tab-b">
          Beta
        </button>
      </ScrollableNav>
    );
    const nav = screen.getByTestId('tabs');
    const track = nav.querySelector('.scrollable-nav-track');
    expect(track).toHaveClass('overflow-x-auto');
    expect(screen.getByTestId('tab-a')).toHaveClass('min-h-11');
    expect(screen.getByTestId('tab-b')).toHaveClass('shrink-0');
  });

  it('ScrollableUnderlineNav includes bottom border on track', () => {
    render(
      <ScrollableUnderlineNav ariaLabel="Underline">
        <span>One</span>
      </ScrollableUnderlineNav>
    );
    expect(document.querySelector('.scrollable-nav-track')).toHaveClass('border-b');
  });
});
