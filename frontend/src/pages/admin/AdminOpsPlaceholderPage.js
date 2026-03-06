import React from 'react';
import { Link } from 'react-router-dom';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';

export default function AdminOpsPlaceholderPage({ title, icon: Icon, description }) {
  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-4">
          {Icon && <Icon className="w-7 h-7" />}
          {title}
        </h1>
        <p className="text-gray-600 mb-6">
          {description || 'This section is wired to the data model and will show content when the module is implemented.'}
        </p>
        <Link to="/admin/ops" className="text-electric-teal hover:underline text-sm">← Back to Operations overview</Link>
      </div>
    </UnifiedAdminLayout>
  );
}
