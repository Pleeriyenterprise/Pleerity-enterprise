import React from 'react';
import { Button } from './ui/button';
import { AlertCircle } from 'lucide-react';

/**
 * Catches React render errors so the app never shows a fully blank screen.
 * Renders a fallback UI with option to go to login or reload.
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    const stack = errorInfo?.componentStack ?? '';
    let navContext = null;
    let lastInteraction = null;
    try {
      const raw = sessionStorage.getItem('cvp_nav_context');
      if (raw) navContext = JSON.parse(raw);
    } catch {
      /* ignore */
    }
    try {
      const rawI = sessionStorage.getItem('cvp_last_interaction');
      if (rawI) lastInteraction = JSON.parse(rawI);
    } catch {
      /* ignore */
    }
    const route =
      typeof window !== 'undefined'
        ? `${window.location.pathname}${window.location.search}${window.location.hash}`
        : '';
    const lastApiError =
      typeof window !== 'undefined' && window.__CVP_LAST_API_ERROR ? { ...window.__CVP_LAST_API_ERROR } : null;

    const payload = {
      tag: 'CVP_ErrorBoundary',
      route,
      errorMessage: error?.message,
      errorName: error?.name,
      componentStack: stack,
      navContext,
      lastInteraction,
      lastApiError,
    };
    console.error('[CVP] ErrorBoundary caught:', payload);
    if (error?.stack) {
      console.error('[CVP] ErrorBoundary stack:', error.stack);
    }
  }

  handleGoLogin = () => {
    this.setState({ hasError: false, error: null });
    window.location.href = '/login';
  };

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      const route =
        typeof window !== 'undefined'
          ? `${window.location.pathname}${window.location.search}`
          : '';
      const msg = this.state.error?.message ? String(this.state.error.message) : '';
      const showDevHint = process.env.NODE_ENV === 'development' && msg;
      return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4" data-testid="error-boundary-fallback">
          <div className="max-w-md w-full text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-100 text-red-600 mb-4">
              <AlertCircle className="w-8 h-8" />
            </div>
            <h1 className="text-xl font-semibold text-gray-900 mb-2">Something went wrong</h1>
            <p className="text-gray-600 mb-6">
              The page could not load. Please try signing in again or refresh the page.
            </p>
            {route ? (
              <p className="text-xs text-gray-500 mb-4 font-mono break-all" data-testid="error-boundary-route">
                Route: {route}
              </p>
            ) : null}
            {showDevHint ? (
              <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded p-2 mb-4 text-left break-words">
                {msg}
              </p>
            ) : null}
            <p className="text-xs text-gray-500 mb-6">
              Details were logged to the browser console (search for <span className="font-mono">CVP_ErrorBoundary</span>).
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Button onClick={this.handleGoLogin} variant="default" className="bg-electric-teal hover:bg-electric-teal/90">
                Go to sign in
              </Button>
              <Button onClick={this.handleReload} variant="outline">
                Refresh page
              </Button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
