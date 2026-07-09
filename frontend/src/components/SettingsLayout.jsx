import React, { useMemo } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { User, Bell, CreditCard, Palette, Globe2 } from 'lucide-react';
import { useBrandingCapabilities, useProfileCapabilities } from '../utils/accountCapabilityAccess';
import { PortalModePageBanner } from './lifecycle/LifecycleShell';
import { ScrollableUnderlineNav, scrollableNavItemClass } from './ui/scrollable-nav';

const BASE_TABS = [
  { path: '/settings/profile', label: 'Profile', icon: User },
  { path: '/settings/jurisdiction', label: 'Jurisdiction', icon: Globe2 },
  { path: '/settings/notifications', label: 'Notifications', icon: Bell },
  { path: '/settings/billing', label: 'Billing', icon: CreditCard },
  { path: '/settings/branding', label: 'Branding', icon: Palette },
];

export default function SettingsLayout() {
  const { canViewProfile, canViewJurisdiction } = useProfileCapabilities();
  const { canViewBranding, canUseWhiteLabelBranding } = useBrandingCapabilities();
  const tabs = useMemo(
    () =>
      BASE_TABS.filter((t) => {
        if (t.path === '/settings/jurisdiction') return canViewJurisdiction;
        if (t.path === '/settings/branding') return canViewBranding || canUseWhiteLabelBranding;
        if (t.path === '/settings/profile' || t.path === '/settings/notifications') return canViewProfile;
        return true;
      }),
    [canViewProfile, canViewJurisdiction, canViewBranding, canUseWhiteLabelBranding],
  );

  return (
    <div className="min-w-0 max-w-full">
      <PortalModePageBanner />
      <h1 className="text-2xl font-bold text-midnight-blue mb-2">Settings</h1>
      <p className="text-gray-600 mb-6">Profile, compliance jurisdiction, notifications, and plan.</p>
      <ScrollableUnderlineNav ariaLabel="Settings sections" data-testid="settings-tab-nav">
        {tabs.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            data-testid={`settings-tab-${path.split('/').pop()}`}
            className={({ isActive }) => scrollableNavItemClass(isActive)}
          >
            <Icon className="w-4 h-4 shrink-0" aria-hidden />
            {label}
          </NavLink>
        ))}
      </ScrollableUnderlineNav>
      <Outlet />
    </div>
  );
}
