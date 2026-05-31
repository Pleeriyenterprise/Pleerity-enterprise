import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PilotEligibilityOverrideDialog from './PilotEligibilityOverrideDialog';

describe('PilotEligibilityOverrideDialog', () => {
  test('stays open when step-up authentication is cancelled', async () => {
    const onOpenChange = jest.fn();
    const onSubmit = jest.fn().mockRejectedValue(new Error('step_up_cancelled'));

    render(
      <PilotEligibilityOverrideDialog
        open
        onOpenChange={onOpenChange}
        title="Grant promo eligibility"
        defaultScope="email"
        defaultScopeValue="user@example.com"
        lockScope
        onSubmit={onSubmit}
      />,
    );

    fireEvent.change(screen.getByTestId('override-reason-input'), {
      target: { value: 'Recover onboarding' },
    });
    fireEvent.click(screen.getByTestId('override-dialog-confirm'));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
    expect(screen.getByTestId('pilot-eligibility-override-dialog')).toBeInTheDocument();
  });

  test('closes on successful submit', async () => {
    const onOpenChange = jest.fn();
    const onSubmit = jest.fn().mockResolvedValue(undefined);

    render(
      <PilotEligibilityOverrideDialog
        open
        onOpenChange={onOpenChange}
        defaultScope="email"
        defaultScopeValue="user@example.com"
        lockScope
        onSubmit={onSubmit}
      />,
    );

    fireEvent.change(screen.getByTestId('override-reason-input'), {
      target: { value: 'Approved exception' },
    });
    fireEvent.click(screen.getByTestId('override-dialog-confirm'));

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });
});
