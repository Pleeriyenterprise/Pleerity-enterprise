import { toastComplianceActionOutcome } from './complianceActionOutcome';
import { toast } from '@/utils/portalNotifications';

jest.mock('@/utils/portalNotifications', () => ({
  toast: {
    success: jest.fn(),
    warning: jest.fn(),
    error: jest.fn(),
  },
}));

describe('toastComplianceActionOutcome', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows success when workflow_complete', () => {
    const ok = toastComplianceActionOutcome({ ok: true, workflow_complete: true, message: 'Recorded.' });
    expect(ok).toBe(true);
    expect(toast.success).toHaveBeenCalledWith('Recorded.');
  });

  it('shows warning on partial success', () => {
    const ok = toastComplianceActionOutcome({ ok: true, workflow_complete: false, authority_synced: false });
    expect(ok).toBe(false);
    expect(toast.warning).toHaveBeenCalled();
  });

  it('does not treat ok without authority_synced as full success', () => {
    const ok = toastComplianceActionOutcome({ ok: true });
    expect(ok).toBe(false);
    expect(toast.warning).toHaveBeenCalled();
  });

  it('shows error when not ok', () => {
    const ok = toastComplianceActionOutcome({ ok: false });
    expect(ok).toBe(false);
    expect(toast.error).toHaveBeenCalled();
  });
});
