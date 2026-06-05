import * as React from 'react';
import { cn } from '@/lib/utils';

/**
 * Wraps wide tables with horizontal scroll and visible affordance on mobile.
 */
export function ResponsiveTable({ className, children, ...props }) {
  return (
    <div
      className={cn(
        'responsive-table-wrap w-full max-w-full overflow-x-auto overscroll-x-contain scroll-smooth',
        '[scrollbar-width:thin] [-webkit-overflow-scrolling:touch]',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
