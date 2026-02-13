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
    console.error('[CVP] ErrorBoundary caught:', error, errorInfo?.componentStack);
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
