import { toast } from './portalNotifications';

jest.mock('sonner', () => ({
  toast: {
    error: jest.fn(),
    success: jest.fn(),
    warning: jest.fn(),
    info: jest.fn(),
    message: jest.fn(),
  },
}));

const { toast: sonnerToast } = require('sonner');

describe('portalNotifications', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('coerces capability_denied detail objects for error toasts (React #31 guard)', () => {
    toast.error({
      error: 'capability_denied',
      message: 'CAP_TODAY_VIEW is not permitted for your account status.',
      support_reference: 'lifecycle-1',
      safe_to_retry: false,
      action: 'read',
      effective_semantic: 'DENY',
    });
    expect(sonnerToast.error).toHaveBeenCalledWith(
      'CAP_TODAY_VIEW is not permitted for your account status.',
      expect.objectContaining({ position: 'top-center' }),
    );
  });
});
