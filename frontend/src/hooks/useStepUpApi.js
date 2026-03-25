import { useCallback, useRef, useState } from 'react';
import { authAPI } from '../api/client';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import { Button } from '../components/ui/button';

function isStepUpRequired(error) {
  if (error?.response?.status !== 403) return false;
  const d = error.response?.data?.detail;
  return d && typeof d === 'object' && d.error_code === 'STEP_UP_REQUIRED';
}

/**
 * Run an API call that may require X-Step-Up-Token; opens password modal when the server returns STEP_UP_REQUIRED.
 * @param {(headers: Record<string, string>) => Promise<any>} fn
 */
export function useStepUpApi() {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [formError, setFormError] = useState('');
  const pendingRef = useRef(null);

  const request = useCallback(async (fn) => {
    try {
      return await fn({});
    } catch (e) {
      if (isStepUpRequired(e)) {
        return new Promise((resolve, reject) => {
          pendingRef.current = { fn, resolve, reject };
          setPassword('');
          setFormError('');
          setOpen(true);
        });
      }
      throw e;
    }
  }, []);

  const cancel = useCallback(() => {
    const p = pendingRef.current;
    pendingRef.current = null;
    setOpen(false);
    setPassword('');
    setFormError('');
    if (p) p.reject(new Error('step_up_cancelled'));
  }, []);

  const submit = useCallback(async () => {
    if (!password.trim()) {
      setFormError('Password is required');
      return;
    }
    const p = pendingRef.current;
    if (!p) return;
    setLoading(true);
    setFormError('');
    try {
      const { data } = await authAPI.verifyStepUp({ password });
      const token = data?.step_up_token;
      if (!token) {
        setFormError('Could not verify password. Try again.');
        return;
      }
      const result = await p.fn({ 'X-Step-Up-Token': token });
      pendingRef.current = null;
      setOpen(false);
      setPassword('');
      p.resolve(result);
    } catch (err) {
      const d = err.response?.data?.detail;
      const msg =
        typeof d === 'string'
          ? d
          : d?.message || err.message || 'Verification failed';
      setFormError(msg);
    } finally {
      setLoading(false);
    }
  }, [password]);

  const modal = (
    <Dialog open={open} onOpenChange={(v) => !v && cancel()}>
      <DialogContent className="sm:max-w-md" onPointerDown={(e) => e.stopPropagation()}>
        <DialogHeader>
          <DialogTitle>Confirm your password</DialogTitle>
          <DialogDescription>
            For your security, re-enter your password to continue this action.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2 py-2">
          <input
            type="password"
            autoComplete="current-password"
            className="w-full border rounded-md px-3 py-2 text-sm"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
          />
          {formError ? <p className="text-sm text-red-600">{formError}</p> : null}
        </div>
        <DialogFooter className="gap-2 sm:gap-0">
          <Button type="button" variant="outline" onClick={cancel} disabled={loading}>
            Cancel
          </Button>
          <Button type="button" onClick={submit} disabled={loading}>
            {loading ? 'Verifying…' : 'Continue'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  return { request, modal };
}
