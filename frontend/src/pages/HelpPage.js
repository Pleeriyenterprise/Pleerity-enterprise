import React from 'react';
import { SUPPORT_EMAIL } from '../config';
import { HelpCircle, Mail, FileText, ExternalLink } from 'lucide-react';

/** Client portal Help page. Linked from footer. */
export default function HelpPage() {
  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-midnight-blue mb-2">Help</h1>
      <p className="text-gray-600 mb-6">Resources and support for Compliance Vault Pro.</p>
      <div className="space-y-4">
        <a
          href={`mailto:${SUPPORT_EMAIL}`}
          className="flex items-center gap-3 p-4 rounded-xl border border-gray-200 bg-white hover:border-electric-teal hover:shadow-sm transition-colors"
        >
          <Mail className="w-5 h-5 text-electric-teal" />
          <div>
            <p className="font-medium text-midnight-blue">Email support</p>
            <p className="text-sm text-gray-500">{SUPPORT_EMAIL}</p>
          </div>
          <ExternalLink className="w-4 h-4 text-gray-400 ml-auto" />
        </a>
        <a
          href="/support/knowledge-base"
          className="flex items-center gap-3 p-4 rounded-xl border border-gray-200 bg-white hover:border-electric-teal hover:shadow-sm transition-colors"
        >
          <FileText className="w-5 h-5 text-electric-teal" />
          <div>
            <p className="font-medium text-midnight-blue">Knowledge base</p>
            <p className="text-sm text-gray-500">Articles and guides</p>
          </div>
          <ExternalLink className="w-4 h-4 text-gray-400 ml-auto" />
        </a>
      </div>
    </div>
  );
}
