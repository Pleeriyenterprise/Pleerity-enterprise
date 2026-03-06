import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../api/client';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { LayoutDashboard, FileText, Settings, Users, BarChart3, History, RefreshCw, Zap } from 'lucide-react';
import { toast } from 'sonner';

const MODULE_LINKS = [
  { id: 'compliance', label: 'Compliance', icon: FileText, href: '/admin/ops/compliance' },
  { id: 'maintenance', label: 'Maintenance', icon: Settings, href: '/admin/ops/maintenance' },
  { id: 'contractors', label: 'Contractors', icon: Users, href: '/admin/ops/contractors' },
  { id: 'risk', label: 'Risk & Insights', icon: BarChart3, href: '/admin/ops/risk' },
  { id: 'audit', label: 'Audit & Logs', icon: History, href: '/admin/ops/audit' },
];

export default function AdminOpsOverviewPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = () => {
    setLoading(true);
    setError(null);
    adminAPI
      .getOpsOverview()
      .then((res) => setData(res.data))
      .catch((err) => {
        setError(err?.response?.data?.detail || 'Failed to load overview');
        toast.error('Failed to load Operations overview');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-5xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <LayoutDashboard className="w-7 h-7" />
            Operations & Compliance — Overview
          </h1>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw className={loading ? 'animate-spin w-4 h-4' : 'w-4 h-4'} />
            Refresh
          </button>
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 mb-4">{error}</div>
        )}

        {loading && !data && (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-10 w-10 border-2 border-electric-teal border-t-transparent" />
          </div>
        )}

        {data && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                <p className="text-sm text-gray-500">Total clients</p>
                <p className="text-2xl font-semibold text-gray-900">{data.clients_total ?? 0}</p>
              </div>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Modules enabled (client count)</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {data.modules_enabled_counts && Object.entries(data.modules_enabled_counts).map(([key, count]) => (
                  <div key={key} className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                    <p className="text-sm text-gray-500 font-mono">{key}</p>
                    <p className="text-xl font-semibold text-gray-900">{count}</p>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Sections</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {MODULE_LINKS.map(({ id, label, icon: Icon, href }) => (
                  <Link
                    key={id}
                    to={href}
                    className="flex items-center gap-3 p-4 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 shadow-sm transition-colors"
                  >
                    <Icon className="w-8 h-8 text-electric-teal" />
                    <span className="font-medium text-gray-900">{label}</span>
                  </Link>
                ))}
                <Link
                  to="/admin/ops/feature-controls"
                  className="flex items-center gap-3 p-4 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 shadow-sm transition-colors"
                >
                  <Zap className="w-8 h-8 text-electric-teal" />
                  <span className="font-medium text-gray-900">Feature Controls</span>
                </Link>
              </div>
            </div>
            <p className="text-sm text-gray-500">
              <Link to="/admin/incidents" className="text-electric-teal hover:underline">Incidents</Link>
              {' · '}
              <Link to="/admin/system-health" className="text-electric-teal hover:underline">System Health</Link>
              {' · '}
              <Link to="/admin/automation" className="text-electric-teal hover:underline">Automation Control Centre</Link>
            </p>
          </div>
        )}
      </div>
    </UnifiedAdminLayout>
  );
}
