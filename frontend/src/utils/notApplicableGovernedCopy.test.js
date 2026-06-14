/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  NotApplicableGovernedDisclosure,
  NotApplicableGovernedNotice,
  notApplicableGovernedCompactCopy,
  resolveNaGovernanceDisclosureDefaultOpen,
} from './notApplicableGovernedCopy';
import { MOBILE_VIEWPORT_MEDIA_QUERY } from '../hooks/useMobileViewport';

function mockMatchMedia(matchesMobile) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: jest.fn().mockImplementation((query) => ({
      matches: query === MOBILE_VIEWPORT_MEDIA_QUERY ? matchesMobile : false,
      media: query,
      onchange: null,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      addListener: jest.fn(),
      removeListener: jest.fn(),
      dispatchEvent: jest.fn(),
    })),
  });
}

describe('resolveNaGovernanceDisclosureDefaultOpen', () => {
  it('returns collapsed default on mobile', () => {
    expect(resolveNaGovernanceDisclosureDefaultOpen(true)).toBe(false);
  });

  it('returns expanded default on desktop', () => {
    expect(resolveNaGovernanceDisclosureDefaultOpen(false)).toBe(true);
  });
});

describe('NotApplicableGovernedNotice', () => {
  it('renders full governed copy', () => {
    render(<NotApplicableGovernedNotice />);
    expect(screen.getByTestId('governed-not-applicable-copy')).toBeInTheDocument();
    expect(screen.getByText(/Before you confirm/i)).toBeInTheDocument();
  });

  it('renders compact governed copy', () => {
    render(<NotApplicableGovernedNotice variant="compact" />);
    expect(screen.getByTestId('governed-not-applicable-compact-copy')).toHaveTextContent(
      notApplicableGovernedCompactCopy(),
    );
  });
});

describe('NotApplicableGovernedDisclosure', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('starts collapsed on mobile viewport', () => {
    mockMatchMedia(true);
    render(<NotApplicableGovernedDisclosure />);
    const trigger = screen.getByTestId('na-governed-disclosure-trigger');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByTestId('na-governed-disclosure-toggle-label')).toHaveTextContent('Show details');
    expect(screen.queryByTestId('governed-not-applicable-compact-copy')).not.toBeInTheDocument();
  });

  it('starts expanded on desktop viewport', () => {
    mockMatchMedia(false);
    render(<NotApplicableGovernedDisclosure />);
    const trigger = screen.getByTestId('na-governed-disclosure-trigger');
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('na-governed-disclosure-toggle-label')).toHaveTextContent('Hide details');
    expect(screen.getByTestId('governed-not-applicable-compact-copy')).toBeVisible();
  });

  it('toggles disclosure open and closed via keyboard-accessible trigger', () => {
    mockMatchMedia(true);
    render(<NotApplicableGovernedDisclosure />);
    const trigger = screen.getByTestId('na-governed-disclosure-trigger');
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('governed-not-applicable-compact-copy')).toBeVisible();
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });
});
