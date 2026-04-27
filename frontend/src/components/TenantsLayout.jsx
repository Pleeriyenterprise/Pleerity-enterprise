import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { cn } from '../lib/utils';
import { portalPageRoot } from './client/ClientPortalPatterns';

const subNavClass = ({ isActive }) =>
  cn(
    'inline-flex items-center rounded-md px-3 py-2 text-sm font-medium border transition-colors min-h-[44px]',
    isActive
      ? 'border-electric-teal bg-teal-50 text-midnight-blue'
      : 'border-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900'
  );

/**
 * Client portal: Tenants area sub-navigation (list, messages, certificate requests, delivery).
 */
export default function TenantsLayout() {
  return (
    <div className={cn(portalPageRoot, 'bg-gray-50')} data-testid="tenants-layout">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <h1 className="text-2xl font-bold text-midnight-blue">Tenants</h1>
        <p className="text-sm text-slate-600 mt-1 max-w-3xl">
          Invite tenants, respond to messages and requests, send compliance packs by email, and review delivery proof.
        </p>

        <nav
          className="mt-6 flex flex-wrap gap-2 border-b border-slate-200 pb-3"
          aria-label="Tenants sections"
          data-testid="tenants-subnav"
        >
          <NavLink to="/tenants" end className={subNavClass}>
            Tenant list
          </NavLink>
          <NavLink to="/tenants/messages" className={subNavClass}>
            Tenant requests
          </NavLink>
          <NavLink to="/tenants/certificate-requests" className={subNavClass}>
            Certificate requests
          </NavLink>
          <NavLink to="/tenants/delivery" className={subNavClass}>
            Send compliance pack & delivery history
          </NavLink>
        </nav>

        <div className="mt-6">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
