/**
 * Canonical admin customer discovery — calls GET /api/admin/search only.
 * Selecting a row opens Admin Client Control Panel (/admin/clients/:id) unless onSelectRow overrides.
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Loader2, AlertCircle } from 'lucide-react';
import { adminAPI } from '../../api/client';
import AccountEnvironmentBadge from './AccountEnvironmentBadge';

const MIN_CHARS = 2;

export default function AdminClientSupportSearch({
  variant = 'panel',
  showIncludeArchived = false,
  limit = 20,
  onSelectRow,
  placeholder,
  className = '',
  initialQuery = '',
}) {
  const navigate = useNavigate();
  const [query, setQuery] = useState(initialQuery || '');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [open, setOpen] = useState(false);
  const [includeArchived, setIncludeArchived] = useState(false);
  const debounceRef = useRef(null);
  const rootRef = useRef(null);
  const includeArchivedRef = useRef(false);
  includeArchivedRef.current = Boolean(showIncludeArchived && includeArchived);

  const ph = placeholder || 'Name, email, company, CRN, postcode, address, order ref, Stripe cus_… or sub_…';

  const runSearch = useCallback(async (raw) => {
    const q = (raw ?? '').trim();
    if (q.length < MIN_CHARS) {
      setResults([]);
      setError('');
      setOpen(q.length > 0);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await adminAPI.globalSearch(q, limit, includeArchivedRef.current);
      setResults(Array.isArray(res.data?.results) ? res.data.results : []);
      setOpen(true);
    } catch (e) {
      const d = e?.response?.data?.detail;
      setError(typeof d === 'string' ? d : 'Search failed');
      setResults([]);
      setOpen(true);
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    const onDoc = (ev) => {
      if (rootRef.current && !rootRef.current.contains(ev.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  useEffect(() => {
    if (!showIncludeArchived) return;
    if (query.trim().length < MIN_CHARS) return;
    runSearch(query);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional: toggle only
  }, [includeArchived]);

  const onChange = (e) => {
    const v = e.target.value;
    setQuery(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runSearch(v), 280);
  };

  const pickRow = (row) => {
    const url = row.primary_support_url || `/admin/clients/${row.client_id}`;
    if (onSelectRow) onSelectRow(row, url);
    else navigate(url);
    setQuery('');
    setResults([]);
    setOpen(false);
  };

  const inputClasses =
    variant === 'header'
      ? 'bg-transparent border-none outline-none text-sm w-full text-gray-900 placeholder:text-gray-500'
      : 'w-full border border-gray-300 rounded-lg px-3 py-2 pl-9 text-sm text-gray-900 placeholder:text-gray-500';

  const wrapClasses =
    variant === 'header'
      ? 'flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg w-full max-w-md'
      : 'relative';

  const hintShort = query.trim().length > 0 && query.trim().length < MIN_CHARS;

  return (
    <div ref={rootRef} className={`relative ${className}`} data-testid="admin-client-support-search">
      <div className={wrapClasses}>
        <Search className={variant === 'header' ? 'w-4 h-4 text-gray-400 shrink-0' : 'absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400'} />
        <input
          type="text"
          value={query}
          onChange={onChange}
          placeholder={ph}
          className={inputClasses}
          aria-label="Find customer"
          data-testid="admin-client-support-search-input"
        />
        {loading ? <Loader2 className="w-4 h-4 animate-spin text-gray-400 shrink-0" /> : null}
      </div>

      {showIncludeArchived ? (
        <label className="flex items-center gap-2 mt-2 text-xs text-gray-600 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(e) => {
              const next = e.target.checked;
              includeArchivedRef.current = Boolean(showIncludeArchived && next);
              setIncludeArchived(next);
              if (query.trim().length >= MIN_CHARS) runSearch(query);
            }}
            className="rounded border-gray-300"
            data-testid="admin-client-support-search-include-archived"
          />
          Include archived &amp; suspended
        </label>
      ) : null}

      <p className="text-[11px] text-gray-500 mt-1" data-testid="admin-client-support-search-hint">
        Type at least {MIN_CHARS} characters. Matches name, email, company, CRN, property, order ref, Stripe customer/subscription id.
      </p>

      {hintShort ? (
        <p className="text-xs text-amber-800 mt-2" data-testid="admin-client-support-search-too-short">
          Enter at least {MIN_CHARS} characters to search.
        </p>
      ) : null}

      {error ? (
        <div
          className="mt-2 flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-100 rounded-md px-3 py-2"
          data-testid="admin-client-support-search-error"
        >
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      ) : null}

      {open && query.trim().length >= MIN_CHARS && !loading && !error && results.length === 0 ? (
        <div
          className="absolute z-50 mt-2 w-full min-w-[18rem] max-w-lg bg-white border border-gray-200 rounded-lg shadow-lg p-4 text-sm text-gray-600"
          data-testid="admin-client-support-search-empty"
        >
          <p>No matching customers.</p>
          {!includeArchived && showIncludeArchived ? (
            <p className="text-xs text-gray-500 mt-2">Try including archived &amp; suspended if this is a dormant account.</p>
          ) : null}
        </div>
      ) : null}

      {open && results.length > 0 ? (
        <div
          className="absolute z-50 mt-2 w-full min-w-[20rem] max-w-xl bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden"
          data-testid="admin-client-support-search-results"
        >
          <div className="px-3 py-2 text-xs text-gray-500 border-b border-gray-100">
            {results.length} result{results.length === 1 ? '' : 's'} — opens Client Control Panel
          </div>
          <ul className="max-h-80 overflow-y-auto">
            {results.map((row) => (
              <li key={row.client_id}>
                <button
                  type="button"
                  onClick={() => pickRow(row)}
                  className="w-full text-left px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors"
                  data-testid={`admin-client-support-search-row-${row.client_id}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="font-medium text-midnight-blue text-sm truncate">
                          {row.client_name || row.full_name || row.company_name || 'Unknown'}
                        </span>
                        <AccountEnvironmentBadge doc={row} />
                      </div>
                      <p className="text-xs text-gray-600 truncate">{row.email || '—'}</p>
                      {row.company_name && row.full_name ? (
                        <p className="text-[11px] text-gray-500 truncate">{row.company_name}</p>
                      ) : null}
                      {row.customer_reference || row.crn ? (
                        <p className="text-[11px] text-gray-400 font-mono mt-0.5">CRN {row.customer_reference || row.crn}</p>
                      ) : null}
                      {row.matched_via ? (
                        <p className="text-[10px] text-gray-400 mt-0.5">via {row.matched_via}</p>
                      ) : null}
                    </div>
                    <div className="text-right text-[11px] text-gray-600 shrink-0 space-y-0.5">
                      <div>{row.current_plan_label || row.plan_name || row.plan || '—'}</div>
                      <div>{row.subscription_status || row.status || '—'}</div>
                      <div className="text-gray-500">{row.onboarding_status || '—'}</div>
                      {typeof row.property_count === 'number' ? <div>{row.property_count} properties</div> : null}
                    </div>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
