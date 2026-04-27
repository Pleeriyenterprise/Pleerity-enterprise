/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import TenantsLayout from './TenantsLayout';

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    NavLink: ({ to, children }) => <a href={to}>{children}</a>,
    Outlet: () => <div data-testid="tenants-outlet" />,
  };
});

describe('TenantsLayout sub-navigation', () => {
  it('includes tenant delivery under /tenants/delivery', () => {
    render(
      <MemoryRouter>
        <TenantsLayout />
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: /send compliance pack/i })).toHaveAttribute('href', '/tenants/delivery');
  });
});
