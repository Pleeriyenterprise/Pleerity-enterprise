import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { User, Bell, CreditCard } from 'lucide-react';

const TABS = [
  { path: '/settings/profile', label: 'Profile', icon: User },
  { path: '/settings/notifications', label: 'Notifications', icon: Bell },
  { path: '/settings/billing', label: 'Billing', icon: CreditCard },
];

export default function SettingsLayout() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-midnight-blue mb-2">Settings</h1>
      <p className="text-gray-600 mb-6">Profile, notifications, and plan.</p>
      <nav className="flex gap-2 border-b border-gray-200 mb-6">
        {TABS.map(({ path, label, icon: Icon }) => (
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
