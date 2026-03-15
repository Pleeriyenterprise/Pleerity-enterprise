import React from 'react';
import { useNavigate } from 'react-router-dom';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';

export default function AdminOpsPlaceholderPage({ title, icon: Icon, description }) {
  const navigate = useNavigate();
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
        <button
          type="button"
          onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/admin/ops'))}
          className="text-electric-teal hover:underline text-sm"
        >
          ← Back
        </button>
      </div>
    </UnifiedAdminLayout>
  );
}
