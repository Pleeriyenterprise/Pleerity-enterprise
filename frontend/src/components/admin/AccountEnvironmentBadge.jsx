import React from 'react';
import { isNonProductionAccount, NON_PRODUCTION_BADGE_TEXT } from '../../utils/adminAccountClassification';

/**
 * High-contrast badge for non-production; optional compact "LIVE" for production rows in dense tables.
 */
export default function AccountEnvironmentBadge({ doc, showLiveBadge = false, className = '' }) {
  const nonProd = isNonProductionAccount(doc);
  if (nonProd) {
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] sm:text-xs font-extrabold uppercase tracking-wide bg-fuchsia-100 text-fuchsia-950 border-2 border-fuchsia-500 shadow-sm ${className}`}
        title="Flagged non-production (is_test_like). Not a live customer account."
      >
        {NON_PRODUCTION_BADGE_TEXT}
      </span>
    );
  }
  if (showLiveBadge) {
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] sm:text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-300 ${className}`}
        title="Production (live) account — no test flag."
      >
        LIVE
      </span>
    );
  }
  return null;
}
