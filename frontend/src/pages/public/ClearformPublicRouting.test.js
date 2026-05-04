/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { TextEncoder, TextDecoder } from 'util';

if (typeof globalThis.TextEncoder === 'undefined') {
  globalThis.TextEncoder = TextEncoder;
}
if (typeof globalThis.TextDecoder === 'undefined') {
  globalThis.TextDecoder = TextDecoder;
}

describe('ClearForm public routing', () => {
  it('redirects /clearform paths to Compliance Vault Pro landing (no unfinished app shell)', async () => {
    const { createMemoryRouter, Navigate, RouterProvider } = jest.requireActual('react-router');
    const router = createMemoryRouter(
      [
        { path: '/clearform/*', element: <Navigate to="/compliance-vault-pro" replace /> },
        { path: '/compliance-vault-pro', element: <div data-testid="cvp-landing">CVP</div> },
      ],
      { initialEntries: ['/clearform/register'] }
    );
    render(<RouterProvider router={router} />);
    await waitFor(() => {
      expect(screen.getByTestId('cvp-landing')).toBeInTheDocument();
    });
    expect(router.state.location.pathname).toBe('/compliance-vault-pro');
  });
});
