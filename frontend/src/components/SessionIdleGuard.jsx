import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { authAPI } from '../api/client';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';

function parseMinutes(envVal, fallback) {
  const n = parseInt(envVal, 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

/** Decode JWT exp (seconds since epoch) without verifying signature; local UX only. */
function jwtExpSeconds(token) {
  if (!token || typeof token !== 'string') return null;
  const parts = token.split('.');
  if (parts.length < 2) return null;
  try {
    let b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const pad = b64.length % 4;
    if (pad) b64 += '='.repeat(4 - pad);
    const json = JSON.parse(atob(b64));
    const exp = json && json.exp;
    return typeof exp === 'number' && Number.isFinite(exp) ? exp : null;
  } catch {
    return null;
  }
}

/**
 * Inactivity warning + extend session + idle logout for client and staff portals.
 */
export default function SessionIdleGuard({ children }) {
  const { user, logout, loginWithToken, isStaff } = useAuth();
  const [warningOpen, setWarningOpen] = useState(false);
  const [extendLoading, setExtendLoading] = useState(false);
  const lastActivityRef = useRef(Date.now());
  const warnedRef = useRef(false);
  const hardLogoutRef = useRef(false);

  const idleMinutes = isStaff()
    ? parseMinutes(process.env.REACT_APP_SESSION_IDLE_MINUTES_STAFF, 20)
    : parseMinutes(process.env.REACT_APP_SESSION_IDLE_MINUTES_CLIENT, 45);
  const idleMs = idleMinutes * 60 * 1000;
  const warningSec = parseInt(process.env.REACT_APP_SESSION_IDLE_WARNING_SECONDS, 10);
  const warnBeforeMs = Math.min(
    (Number.isFinite(warningSec) && warningSec > 0 ? warningSec : 120) * 1000,
    Math.max(idleMs - 5000, 30000),
  );

  const bumpActivity = useCallback(() => {
    lastActivityRef.current = Date.now();
    warnedRef.current = false;
    setWarningOpen(false);
  }, []);

  useEffect(() => {
    if (!user || !localStorage.getItem('auth_token')) return undefined;

    const onActivity = () => {
      bumpActivity();
    };
    const opts = { capture: true, passive: true };
    window.addEventListener('pointerdown', onActivity, opts);
    window.addEventListener('keydown', onActivity, opts);
    window.addEventListener('scroll', onActivity, opts);

    return () => {
      window.removeEventListener('pointerdown', onActivity, opts);
      window.removeEventListener('keydown', onActivity, opts);
      window.removeEventListener('scroll', onActivity, opts);
    };
  }, [user, bumpActivity]);

  useEffect(() => {
    if (!user || !localStorage.getItem('auth_token')) return undefined;

    const tick = () => {
      const now = Date.now();
      const elapsed = now - lastActivityRef.current;
      if (elapsed >= idleMs) {
        if (!hardLogoutRef.current) {
          hardLogoutRef.current = true;
          authAPI.idleSessionNotify().catch(() => {});
          const isAdminPath = window.location.pathname.startsWith('/admin');
          localStorage.removeItem('auth_token');
          localStorage.removeItem('user');
          window.location.href = isAdminPath ? '/login/admin?session_expired=1' : '/login?session_expired=1';
        }
        return;
      }
      if (elapsed >= idleMs - warnBeforeMs) {
        if (!warnedRef.current) {
          warnedRef.current = true;
          setWarningOpen(true);
        }
      } else {
        warnedRef.current = false;
        setWarningOpen(false);
      }
    };

    const id = window.setInterval(tick, 5000);
    tick();
    return () => window.clearInterval(id);
  }, [user, idleMs, warnBeforeMs]);

  // Proactive extend when access JWT is short-lived (e.g. JWT_EXPIRATION_MINUTES) so active users are not cut off mid-work.
  useEffect(() => {
    if (!user || !localStorage.getItem('auth_token')) return undefined;
    const renewIfNeeded = async () => {
      const token = localStorage.getItem('auth_token');
      if (!token) return;
      const exp = jwtExpSeconds(token);
      if (exp == null) return;
      const msLeft = exp * 1000 - Date.now();
      const renewThresholdMs = 5 * 60 * 1000;
      if (msLeft > 0 && msLeft < renewThresholdMs) {
        try {
          const { data } = await authAPI.extendSession();
          if (data?.access_token) {
            localStorage.setItem('auth_token', data.access_token);
          }
          if (data?.user && loginWithToken) {
            let prev = {};
            try {
              prev = JSON.parse(localStorage.getItem('user') || '{}');
            } catch {
              prev = {};
            }
            loginWithToken(data.access_token, { ...prev, ...data.user });
          }
        } catch {
          /* Let the next 401 handler or idle flow deal with hard failure */
        }
      }
    };
    const id = window.setInterval(renewIfNeeded, 60 * 1000);
    renewIfNeeded();
    return () => window.clearInterval(id);
  }, [user, loginWithToken]);

  const handleExtend = async () => {
    setExtendLoading(true);
    try {
      const { data } = await authAPI.extendSession();
      if (data?.access_token) {
        localStorage.setItem('auth_token', data.access_token);
      }
      if (data?.user && loginWithToken) {
        let prev = {};
        try {
          prev = JSON.parse(localStorage.getItem('user') || '{}');
        } catch {
          prev = {};
        }
        loginWithToken(data.access_token, { ...prev, ...data.user });
      }
      bumpActivity();
      hardLogoutRef.current = false;
    } catch {
      const isAdminPath = window.location.pathname.startsWith('/admin');
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user');
      window.location.href = isAdminPath ? '/login/admin?session_expired=1' : '/login?session_expired=1';
    } finally {
      setExtendLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
  };

  if (!user) {
    return children;
  }

  return (
    <>
      {children}
      <Dialog open={warningOpen} onOpenChange={setWarningOpen}>
        <DialogContent className="sm:max-w-md" onPointerDown={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>Session timeout</DialogTitle>
            <DialogDescription>
              You will be signed out soon due to inactivity. Stay signed in to continue working, or log out now.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={handleLogout}>
              Log out
            </Button>
            <Button type="button" onClick={handleExtend} disabled={extendLoading}>
              {extendLoading ? 'Extending…' : 'Stay signed in'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
