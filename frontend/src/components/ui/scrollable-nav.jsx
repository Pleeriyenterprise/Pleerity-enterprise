import * as React from 'react';
import { cn } from '@/lib/utils';

/**
 * Horizontal nav row that scrolls on narrow viewports instead of clipping tabs.
 * Preserves keyboard focus and touch scrolling; children should use shrink-0 + min-h-11.
 */
export const ScrollableNav = React.forwardRef(
  ({ className, trackClassName, ariaLabel, as: Component = 'nav', children, ...props }, ref) => (
    <Component
      ref={ref}
      className={cn('scrollable-nav relative max-w-full', className)}
      aria-label={ariaLabel}
      {...props}
    >
      <div
        className={cn(
          'scrollable-nav-track flex flex-nowrap gap-2 overflow-x-auto overscroll-x-contain scroll-smooth pb-px',
          '[scrollbar-width:thin] [-webkit-overflow-scrolling:touch]',
          trackClassName
        )}
        role={Component === 'nav' ? undefined : 'tablist'}
      >
        {children}
      </div>
    </Component>
  )
);
ScrollableNav.displayName = 'ScrollableNav';

/** Underline tab row used by Settings and similar section nav. */
export function ScrollableUnderlineNav({ className, trackClassName, ariaLabel, children, ...props }) {
  return (
    <ScrollableNav
      ariaLabel={ariaLabel}
      className={cn('mb-6', className)}
      trackClassName={cn('border-b border-gray-200', trackClassName)}
      {...props}
    >
      {children}
    </ScrollableNav>
  );
}

/** Classes for NavLink / button triggers inside ScrollableNav. */
export const scrollableNavItemClass = (active, extra = '') =>
  cn(
    'inline-flex shrink-0 items-center gap-2 px-4 py-2 min-h-11 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap',
    active
      ? 'border-electric-teal text-electric-teal'
      : 'border-transparent text-gray-600 hover:text-midnight-blue',
    extra
  );

export const scrollableNavButtonClass = (active, extra = '') =>
  cn(
    'inline-flex shrink-0 items-center gap-2 px-4 py-2 min-h-11 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap',
    active
      ? 'border-electric-teal text-midnight-blue'
      : 'border-transparent text-gray-500 hover:text-gray-700',
    extra
  );
