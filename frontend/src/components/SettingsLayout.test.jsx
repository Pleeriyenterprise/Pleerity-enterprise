/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import SettingsLayout from './SettingsLayout';

jest.mock('../contexts/EntitlementsContext', () => ({
  useEntitlements: () => ({
    hasFeature: () => true,
    entitlementsLoadFailed: false,
  }),
}));

describe('SettingsLayout mobile tabs', () => {
  it('renders Billing tab inside scrollable nav', () => {
    render(<SettingsLayout />);
    const nav = screen.getByTestId('settings-tab-nav');
    expect(nav).toBeInTheDocument();
    expect(nav.querySelector('.scrollable-nav-track')).toBeTruthy();
    expect(screen.getByTestId('settings-tab-billing')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /billing/i })).toHaveAttribute('href', '/settings/billing');
  });

  it('exposes all critical settings tabs at mobile widths', () => {
    render(<SettingsLayout />);
    ['profile', 'jurisdiction', 'notifications', 'billing', 'branding'].forEach((slug) => {
      expect(screen.getByTestId(`settings-tab-${slug}`)).toBeInTheDocument();
    });
  });
});
