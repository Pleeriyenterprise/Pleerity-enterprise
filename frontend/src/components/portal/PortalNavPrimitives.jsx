import React, { useEffect, useId, useRef } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { ChevronDown, MoreHorizontal } from 'lucide-react';
import { isSettingsPath } from '../../config/portalNavigationConfig';

export const portalNavLinkClass = (isActive) =>
  `flex items-center min-h-[48px] px-3 py-3.5 lg:py-4 text-sm font-medium border-b-2 transition-colors whitespace-nowrap shrink-0 ${
    isActive
      ? 'border-electric-teal text-electric-teal bg-white/[0.06] lg:bg-transparent'
      : 'border-transparent text-slate-300 hover:text-white hover:border-white/25'
  }`;

export const portalNavDropdownItemClass = (isActive) =>
  `flex items-center px-3 py-2.5 text-sm transition-colors ${
    isActive
      ? 'border-electric-teal text-electric-teal bg-white/10'
      : 'border-transparent text-gray-300 hover:text-white hover:bg-white/5'
  }`;

export function PortalNavLink({ to, label, icon: Icon, end, isTenant, invoicingEnabled, onNavigate, className = '', lifecycleNavHint }) {
  const hintClass =
    lifecycleNavHint === 'locked'
      ? 'opacity-60'
      : lifecycleNavHint === 'read_only'
        ? 'opacity-80'
        : lifecycleNavHint === 'de_emphasized'
          ? 'opacity-50'
          : '';
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      className={({ isActive }) =>
        `${portalNavLinkClass(
          isActive || ((to === '/settings' || to === '/tenant/settings') && isSettingsPath(to, { isTenant, invoicingEnabled }))
        )} ${hintClass} ${className}`
      }
      data-lifecycle-nav-hint={lifecycleNavHint || 'normal'}
    >
      {Icon ? <Icon className="w-4 h-4 mr-2 shrink-0" aria-hidden /> : null}
      {label}
    </NavLink>
  );
}

/**
 * Desktop dropdown for Operations or More menus.
 * Hover + click; keyboard Escape closes; focus-friendly trigger.
 */
export function PortalNavDropdown({
  menuId,
  label,
  icon: Icon = MoreHorizontal,
  isActive,
  isOpen,
  onOpenChange,
  items = [],
  onNavigate,
  isTenant,
  invoicingEnabled,
}) {
  const panelRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onOpenChange(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [isOpen, onOpenChange]);

  return (
    <div
      className="relative shrink-0"
      onMouseEnter={() => onOpenChange(true)}
      onMouseLeave={() => onOpenChange(false)}
    >
      <button
        type="button"
        id={`${menuId}-trigger`}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-controls={`${menuId}-menu`}
        onClick={() => onOpenChange(!isOpen)}
        className={`${portalNavLinkClass(isActive)} w-full lg:w-auto`}
      >
        <Icon className="w-4 h-4 mr-2 shrink-0" aria-hidden />
        {label}
        <ChevronDown className={`w-4 h-4 ml-1 transition-transform ${isOpen ? 'rotate-180' : ''}`} aria-hidden />
      </button>
      <div
        ref={panelRef}
        id={`${menuId}-menu`}
        role="menu"
        aria-labelledby={`${menuId}-trigger`}
        className={`lg:absolute lg:left-0 lg:top-full lg:bg-midnight-blue lg:border lg:border-white/10 lg:rounded-b-lg lg:shadow-lg lg:min-w-[200px] z-40 ${
          isOpen ? 'block' : 'hidden'
        }`}
      >
        {items.map((item) => {
          const ItemIcon = item.icon;
          if (item.type === 'group' && item.children?.length) {
            return item.children.map((child) => {
              const ChildIcon = child.icon;
              return (
                <NavLink
                  key={child.path}
                  to={child.path}
                  role="menuitem"
                  onClick={() => {
                    onNavigate?.();
                    onOpenChange(false);
                  }}
                  className={({ isActive: childActive }) => portalNavDropdownItemClass(childActive)}
                >
                  <ChildIcon className="w-4 h-4 mr-2 shrink-0" aria-hidden />
                  {child.label}
                </NavLink>
              );
            });
          }
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.end}
              role="menuitem"
              onClick={() => {
                onNavigate?.();
                onOpenChange(false);
              }}
              className={({ isActive }) =>
                portalNavDropdownItemClass(
                  isActive ||
                    ((item.path === '/settings' || item.path === '/tenant/settings') &&
                      isSettingsPath(item.path, { isTenant, invoicingEnabled }))
                )
              }
            >
              {ItemIcon ? <ItemIcon className="w-4 h-4 mr-2 shrink-0" aria-hidden /> : null}
              {item.label}
            </NavLink>
          );
        })}
      </div>
    </div>
  );
}

/** Mobile section header for grouped navigation. */
export function PortalMobileNavSection({ title, children, defaultOpen = false, isActiveSection = false }) {
  const sectionId = useId();
  const [open, setOpen] = React.useState(defaultOpen || isActiveSection);

  useEffect(() => {
    if (isActiveSection) setOpen(true);
  }, [isActiveSection]);

  return (
    <div className="border-t border-white/10 first:border-t-0">
      <button
        type="button"
        className="flex w-full items-center justify-between px-3 py-3 text-xs font-semibold uppercase tracking-wide text-slate-400 hover:text-white"
        aria-expanded={open}
        aria-controls={sectionId}
        onClick={() => setOpen((o) => !o)}
      >
        {title}
        <ChevronDown className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden />
      </button>
      {open ? (
        <div id={sectionId} className="pb-1">
          {children}
        </div>
      ) : null}
    </div>
  );
}

export function PortalMobileNavLink({ to, label, icon: Icon, end, isTenant, invoicingEnabled, onNavigate }) {
  const location = useLocation();
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      className={({ isActive }) =>
        `flex items-center min-h-[44px] px-4 py-2.5 text-sm border-l-2 transition-colors ${
          isActive ||
          ((to === '/settings' || to === '/tenant/settings') &&
            isSettingsPath(location.pathname, { isTenant, invoicingEnabled }))
            ? 'border-electric-teal text-electric-teal bg-white/10'
            : 'border-transparent text-gray-300 hover:text-white hover:bg-white/5'
        }`
      }
    >
      {Icon ? <Icon className="w-4 h-4 mr-2 shrink-0" aria-hidden /> : null}
      {label}
    </NavLink>
  );
}
