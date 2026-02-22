import React from 'react';

/**
 * Consistent empty state: icon, title, description, optional CTA.
 */
export default function EmptyState({ icon: Icon, title, description, actionLabel, onAction, className = '', testId = 'empty-state', actionTestId }) {
  return (
    <div className={`text-center py-12 px-4 ${className}`} data-testid={testId}>
      {Icon && <Icon className="w-12 h-12 text-gray-300 mx-auto mb-4" />}
      {title && <h3 className="text-lg font-medium text-gray-900 mb-2">{title}</h3>}
      {description && <p className="text-gray-500 max-w-sm mx-auto">{description}</p>}
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="mt-4 px-4 py-2 text-sm font-medium text-electric-teal border border-electric-teal rounded-lg hover:bg-teal-50 transition-colors"
          data-testid={actionTestId}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
