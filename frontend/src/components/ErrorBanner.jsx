import React from 'react';
import { Alert, AlertDescription } from './ui/alert';
import { AlertCircle } from 'lucide-react';
import { Button } from './ui/button';

/**
 * Consistent error banner for portal pages.
 * variant: 'destructive' (red) or 'default' (neutral)
 */
export default function ErrorBanner({ message, variant = 'destructive', onRetry, retryLabel = 'Try again', className = '' }) {
  if (!message) return null;
  return (
    <Alert variant={variant} className={`mb-6 ${className}`} data-testid="error-banner">
      <AlertCircle className="h-4 w-4" />
      <AlertDescription className="flex flex-wrap items-center gap-2">
        <span className="flex-1">{message}</span>
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            {retryLabel}
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}
