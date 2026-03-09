/**
 * Operations → Approvals: placeholder for invoice/approval workflows.
 * Gated by invoicing.
 */
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { ClipboardCheck } from 'lucide-react';
import { EntitlementProtectedRoute } from '../utils/EntitlementProtectedRoute';

function ClientApprovalsPageInner() {
  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-2">
        <ClipboardCheck className="w-7 h-7" />
        Approvals
      </h1>
      <p className="text-gray-600 mb-6">
        Approve invoices and other items requiring your sign-off. This section is coming soon.
      </p>
      <Card>
        <CardHeader>
          <CardTitle>Coming soon</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500">
            Approval workflows for invoices and work orders will appear here. Contact your administrator if you need access.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

export default function ClientApprovalsPage() {
  return (
    <EntitlementProtectedRoute requiredFeature="invoicing">
      <ClientApprovalsPageInner />
    </EntitlementProtectedRoute>
  );
}
