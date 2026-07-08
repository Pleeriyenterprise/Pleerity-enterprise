import { useCallback, useState } from 'react';
import api from '../api/client';
import { toast } from '@/utils/portalNotifications';
import { useStepUpApi } from './useStepUpApi';
import {
  getCapabilityDeniedMessage,
  isCapabilityDeniedApiError,
} from '../utils/billingCapabilityAccess';

/**
 * Governed undo for cancel-at-period-end (POST /api/billing/resume with step-up).
 * @param {{ onSuccess?: () => Promise<void> | void, canManageSubscription?: boolean }} options
 */
export function useResumeSubscription({ onSuccess, canManageSubscription = true } = {}) {
  const stepUp = useStepUpApi();
  const [resuming, setResuming] = useState(false);

  const resumeSubscription = useCallback(async () => {
    if (!canManageSubscription) return false;
    setResuming(true);
    try {
      const res = await stepUp.request((headers) => api.post('/billing/resume', {}, { headers }));
      if (res.data?.already_active) {
        toast.success('Subscription active', {
          description: 'Your subscription is already set to continue.',
        });
      } else {
        toast.success('Subscription kept', {
          description: 'Your scheduled cancellation has been removed.',
        });
      }
      if (onSuccess) {
        await onSuccess();
      }
      return true;
    } catch (error) {
      if (error?.message === 'step_up_cancelled') {
        return false;
      }
      if (isCapabilityDeniedApiError(error)) {
        toast.error(getCapabilityDeniedMessage(error, 'Could not keep subscription'));
      } else {
        const detail = error.response?.data?.detail;
        toast.error(typeof detail === 'string' ? detail : 'Could not keep subscription');
      }
      return false;
    } finally {
      setResuming(false);
    }
  }, [canManageSubscription, onSuccess, stepUp]);

  return { resumeSubscription, resuming, stepUpModal: stepUp.modal };
}
