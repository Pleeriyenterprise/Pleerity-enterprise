import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { clientAPI } from '../../api/client';
import { usePropertyCapabilities } from '../../utils/propertyCapabilityAccess';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { PortalLoadingPanel } from '../client/ClientPortalPatterns';
import { formatMinorUnits } from '../../utils/rentMoney';
import {
  Users,
  AlertTriangle,
  Wrench,
  Mail,
  Calendar,
  Banknote,
  FileCheck,
  Bell,
  ExternalLink,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { cn } from '../../lib/utils';

function Section({ title, icon: Icon, children, defaultOpen = true, testId }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Card className="border-gray-200" data-testid={testId}>
      <button
        type="button"
        className="w-full flex items-center justify-between px-4 py-3 text-left"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-midnight-blue">
          {Icon ? <Icon className="h-4 w-4 text-electric-teal" /> : null}
          {title}
        </span>
        {open ? <ChevronUp className="h-4 w-4 text-gray-400" /> : <ChevronDown className="h-4 w-4 text-gray-400" />}
      </button>
      {open ? <CardContent className="pt-0 pb-4 space-y-2 text-sm">{children}</CardContent> : null}
    </Card>
  );
}

function AlertRow({ alert }) {
  const sev = alert.severity === 'critical' ? 'text-red-700 bg-red-50 border-red-100' : alert.severity === 'high' ? 'text-orange-800 bg-orange-50 border-orange-100' : 'text-slate-700 bg-slate-50 border-slate-200';
  return (
    <div className={cn('rounded-lg border px-3 py-2 flex items-center justify-between gap-2', sev)} data-testid={`occupancy-alert-${alert.kind}`}>
      <span>
        {alert.kind.replace(/_/g, ' ')} ({alert.count})
      </span>
      {alert.route ? (
        <Button variant="ghost" size="sm" asChild className="shrink-0 h-8">
          <Link to={alert.route}>View</Link>
        </Button>
      ) : null}
    </div>
  );
}

/**
 * Property-scoped occupancy/tenancy operational layer (derived; no duplicate rent authority).
 */
export default function PropertyOccupancyTenancyPanel({ propertyId }) {
  const { canUseTenantPortal, canUseOpsRent, canUseOpsMaintenance } = usePropertyCapabilities();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const hasTenantPortal = canUseTenantPortal;
  const hasRent = canUseOpsRent;
  const hasMaintenance = canUseOpsMaintenance;

  useEffect(() => {
    if (!propertyId) return;
    setLoading(true);
    setError(null);
    clientAPI
      .getPropertyOccupancyOperationalSummary(propertyId)
      .then((res) => setData(res.data))
      .catch(() => {
        setError('Unable to load occupancy operational summary');
        setData(null);
      })
      .finally(() => setLoading(false));
  }, [propertyId]);

  if (loading) {
    return (
      <div data-testid="property-occupancy-loading">
        <PortalLoadingPanel message="Loading occupancy & tenancy…" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <Card className="border-gray-200" data-testid="property-occupancy-error">
        <CardContent className="py-6 text-sm text-gray-500">{error || 'No data'}</CardContent>
      </Card>
    );
  }

  const rent = data.rent_status;
  const links = data.deep_links || {};

  return (
    <div className="space-y-4" data-testid="property-occupancy-panel">
      <p className="text-sm text-gray-600 bg-slate-50 border border-slate-100 rounded-lg px-3 py-2">
        {data.authority_note}
        {data.generated_at_utc ? (
          <span className="block text-xs text-gray-500 mt-1">As of {String(data.generated_at_utc).slice(0, 19).replace('T', ' ')} UTC</span>
        ) : null}
      </p>

      {(data.operational_alerts || []).length > 0 ? (
        <Section title="Operational alerts" icon={AlertTriangle} testId="occupancy-section-alerts">
          {(data.operational_alerts || []).map((a) => (
            <AlertRow key={a.kind} alert={a} />
          ))}
        </Section>
      ) : null}

      <Section title="Tenancy lifecycle" icon={Users} testId="occupancy-section-lifecycle">
        <p>
          Occupancy: <strong>{data.applicability?.occupancy || '—'}</strong>
          {' · '}
          Tenancy active: <strong>{data.tenancy_lifecycle?.tenancy_active ? 'Yes' : 'No / unknown'}</strong>
        </p>
        <p className="text-xs text-gray-500">Move state: {data.tenancy_lifecycle?.move_state || '—'}</p>
      </Section>

      {hasTenantPortal ? (
        <Section title="Active tenants" icon={Users} testId="occupancy-section-tenants">
          {(data.active_tenants || []).length === 0 ? (
            <p className="text-gray-500">No tenants assigned to this property.</p>
          ) : (
            <ul className="space-y-2">
              {(data.active_tenants || []).map((t) => (
                <li key={t.tenant_id} className="flex flex-wrap justify-between gap-2 border-b border-gray-100 pb-2">
                  <span>{t.full_name || t.email}</span>
                  <span className="text-xs text-gray-500 capitalize">{t.portal_activity?.replace(/_/g, ' ')}</span>
                </li>
              ))}
            </ul>
          )}
          <Button variant="outline" size="sm" asChild className="mt-2">
            <Link to={links.tenants || '/tenants'}>
              Manage tenants <ExternalLink className="h-3 w-3 ml-1" />
            </Link>
          </Button>
        </Section>
      ) : (
        <Card className="border-dashed border-gray-200">
          <CardContent className="py-4 text-sm text-gray-500">Tenant portal not enabled on your plan.</CardContent>
        </Card>
      )}

      {hasRent && rent ? (
        <Section title="Rent status" icon={Banknote} testId="occupancy-section-rent">
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded px-2 py-1 mb-2">
            {rent.disclaimer}
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div>
              <p className="text-xs text-gray-500">Overdue periods</p>
              <p className="font-semibold text-orange-700">{rent.overdue_count ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Severely overdue</p>
              <p className="font-semibold text-red-700">{rent.severely_overdue_count ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Outstanding</p>
              <p className="font-semibold">{formatMinorUnits(rent.total_outstanding_minor, rent.currency)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Collected this month</p>
              <p className="font-semibold text-emerald-700">
                {formatMinorUnits(rent.rent_collected_this_month_minor, rent.currency)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Last payment</p>
              <p className="font-semibold">{rent.last_payment_at ? String(rent.last_payment_at).slice(0, 10) : '—'}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 mt-2">
            <Button variant="outline" size="sm" asChild>
              <Link to={links.rent_operations || `/operations/rent?property_id=${propertyId}`}>
                Rent operations <ExternalLink className="h-3 w-3 ml-1" />
              </Link>
            </Button>
            <Button size="sm" asChild data-testid="occupancy-enable-rent-tracking">
              <Link to={`/operations/rent?property_id=${propertyId}&setup=1`}>
                Enable rent tracking
              </Link>
            </Button>
          </div>
        </Section>
      ) : hasRent ? (
        <Section title="Rent tracking" icon={Banknote} testId="occupancy-section-rent-setup">
          <p className="text-gray-600 text-sm">No rent schedule linked to this property yet.</p>
          <Button size="sm" asChild data-testid="occupancy-enable-rent-tracking">
            <Link to={`/operations/rent?property_id=${propertyId}&setup=1`}>Enable rent tracking</Link>
          </Button>
        </Section>
      ) : null}

      {hasMaintenance ? (
        <Section title="Maintenance & issues" icon={Wrench} testId="occupancy-section-maintenance">
          <p>
            Open issues: <strong>{data.open_maintenance?.open_issues_count ?? 0}</strong>
            {' · '}
            Tenant-reported open: <strong>{data.open_maintenance?.tenant_reported_open ?? 0}</strong>
          </p>
          <p className="text-xs text-gray-500">Reported ≠ resolved. Scheduled visit ≠ issue fixed.</p>
          {(data.open_maintenance?.items || []).slice(0, 5).map((i) => (
            <div key={i.issue_id} className="text-xs border-l-2 border-orange-200 pl-2">
              {i.title || i.issue_id} — {i.status}
            </div>
          ))}
          <Button variant="outline" size="sm" asChild className="mt-2">
            <Link to={links.maintenance || '#'}>
              Jobs & issues <ExternalLink className="h-3 w-3 ml-1" />
            </Link>
          </Button>
        </Section>
      ) : null}

      {hasTenantPortal ? (
        <>
          <Section title="Certificate requests" icon={FileCheck} defaultOpen={false} testId="occupancy-section-certs">
            {(data.certificate_requests || []).length === 0 ? (
              <p className="text-gray-500">None for this property.</p>
            ) : (
              (data.certificate_requests || []).slice(0, 8).map((r) => (
                <div key={r.request_id} className="text-xs border-b border-gray-100 py-1">
                  {r.tenant_name}: {r.certificate_type} — {r.status}
                </div>
              ))
            )}
            <Button variant="outline" size="sm" asChild className="mt-2">
              <Link to="/tenants/certificate-requests">Certificate requests</Link>
            </Button>
          </Section>

          <Section title="Compliance pack delivery" icon={Mail} defaultOpen={false} testId="occupancy-section-delivery">
            {(data.compliance_pack_deliveries || []).length === 0 ? (
              <p className="text-gray-500">No delivery records.</p>
            ) : (
              (data.compliance_pack_deliveries || []).slice(0, 5).map((d) => (
                <div key={d.delivery_id} className="text-xs">
                  {d.sent_at?.slice(0, 10)} — {d.status || 'sent'}
                </div>
              ))
            )}
            <Button variant="outline" size="sm" asChild className="mt-2">
              <Link to={links.tenant_delivery || '/tenants/delivery'}>Delivery history</Link>
            </Button>
          </Section>

          <Section title="Portal activity" icon={Users} defaultOpen={false} testId="occupancy-section-portal">
            {(data.portal_activity || []).map((p) => (
              <div key={p.tenant_id} className="flex justify-between text-xs py-1">
                <span>{p.label}</span>
                <span className="text-gray-500 capitalize">{p.activity?.replace(/_/g, ' ')}</span>
              </div>
            ))}
          </Section>
        </>
      ) : null}

      <Section title="Reminders & visits" icon={Calendar} defaultOpen={false} testId="occupancy-section-visits">
        {(data.reminder_history || []).length > 0 ? (
          <>
            <p className="text-xs font-medium text-gray-600">Rent reminders (recent)</p>
            {(data.reminder_history || []).slice(0, 5).map((r) => (
              <div key={r.reminder_key} className="text-xs text-gray-600">
                {r.reminder_type} — {r.sent_at?.slice(0, 10)}
              </div>
            ))}
          </>
        ) : null}
        {(data.upcoming_visits || []).length > 0 ? (
          <>
            <p className="text-xs font-medium text-gray-600 mt-2">Upcoming / scheduled</p>
            {(data.upcoming_visits || []).slice(0, 8).map((v, idx) => (
              <div key={`${v.work_order_id || v.event_type}-${idx}`} className="text-xs border-l-2 border-teal-200 pl-2 py-0.5">
                {v.title || v.event_type}
                {v.date ? ` (${v.date})` : ''}
                {v.note ? <span className="block text-gray-400">{v.note}</span> : null}
              </div>
            ))}
          </>
        ) : (
          <p className="text-gray-500">No upcoming visits in range.</p>
        )}
        <Button variant="outline" size="sm" asChild className="mt-2">
          <Link to={links.calendar || '/calendar'}>Calendar</Link>
        </Button>
      </Section>
    </div>
  );
}
