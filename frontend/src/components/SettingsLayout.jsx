import React, { useMemo } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { User, Bell, CreditCard, Palette, Globe2 } from 'lucide-react';
import { useEntitlements } from '../contexts/EntitlementsContext';

const BASE_TABS = [
  { path: '/settings/profile', label: 'Profile', icon: User },
  { path: '/settings/jurisdiction', label: 'Jurisdiction', icon: Globe2 },
  { path: '/settings/notifications', label: 'Notifications', icon: Bell },
  { path: '/settings/billing', label: 'Billing', icon: CreditCard },
  { path: '/settings/branding', label: 'Branding', icon: Palette, feature: 'white_label_reports' },
];

export default function SettingsLayout() {
  const { hasFeature, entitlementsLoadFailed } = useEntitlements();
  const tabs = useMemo(
    () =>
      BASE_TABS.filter((t) => {
        if (!t.feature) return true;
        return entitlementsLoadFailed || hasFeature(t.feature);
      }),
    [hasFeature, entitlementsLoadFailed]
  );

  return (
    <div>
      <h1 className="text-2xl font-bold text-midnight-blue mb-2">Settings</h1>
      <p className="text-gray-600 mb-6">Profile, compliance jurisdiction, notifications, and plan.</p>
      <nav className="flex gap-2 border-b border-gray-200 mb-6">
        {tabs.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              `flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                isActive
                  ? 'border-electric-teal text-electric-teal'
                  : 'border-transparent text-gray-600 hover:text-midnight-blue'
              }`
            }
          >
            <Icon className="w-4 h-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
