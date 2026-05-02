/**
 * Unified Compliance Work Queue (v1) — read-only list projection from the same unified task
 * pipeline as priorities; primary actions reuse the shared CTA resolver (see ctaRegistry).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { clientAPI, parseApiError } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import { AlertCircle, ListTodo } from 'lucide-react';
import { PortalLoadingPanel, portalPageRoot } from '../components/client/ClientPortalPatterns';
import { resolveTaskCta } from '../utils/ctaRegistry';
import { useGuidedEvidenceModal } from '../context/GuidedEvidenceModalContext';
import { resolveClientPortalPath, recordClientPortalInteraction } from '../utils/clientPortalNavigation';

/** Map UCWQ API row to unified-task-shaped object for {@link resolveTaskCta}. */
export function workQueueRowToTask(row) {
  const rid = row?.related_ids && typeof row.related_ids === 'object' ? row.related_ids : {};
  const meta = {};
  if (rid.requirement_id) meta.requirement_id = rid.requirement_id;
  if (rid.gap_key) meta.gap_key = rid.gap_key;
  if (rid.signal_id) meta.related_risk_signal_id = rid.signal_id;
  if (rid.work_order_id) meta.related_work_order_id = rid.work_order_id;
  if (rid.issue_id) meta.related_issue_id = rid.issue_id;
  if (rid.invoice_id) meta.related_invoice_id = rid.invoice_id;
  const pa = row?.primary_action && typeof row.primary_action === 'object' ? row.primary_action : {};
  if (pa.take_action && typeof pa.take_action === 'object') {
    meta.take_action = pa.take_action;
  }
  return {
    id: row.queue_item_id,
    source_type: row.source_system,
    source_entity_type: row.source_system,
    primary_action_type: pa.type,
    primary_action_label: pa.label,
    primary_action_url: pa.url,
    inline_action_supported: pa.inline_supported,
    property_id: row.property_id,
    metadata: meta,
    action_context_type: pa.type,
  };
}

function urgencyBadgeVariant(band) {
  const b = String(band || '').toLowerCase();
  if (b === 'urgent') return 'destructive';
  if (b === 'soon') return 'default';
  return 'secondary';
}

export default function ClientWorkQueuePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { openGuidedEvidence } = useGuidedEvidenceModal();
  const isClientUser = user && (user.role === 'ROLE_CLIENT' || user.role === 'ROLE_CLIENT_ADMIN') && user.client_id;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [items, setItems] = useState([]);

  const load = useCallback(() => {
    if (!isClientUser) return;
    setLoading(true);
    setError('');
    clientAPI
      .getWorkQueue({})
      .then((r) => {
        const list = Array.isArray(r.data?.items) ? r.data.items : [];
        setItems(list);
      })
      .catch((err) => {
        setError(parseApiError(err, 'Could not load work queue'));
        setItems([]);
      })
      .finally(() => setLoading(false));
  }, [isClientUser]);

  useEffect(() => {
    load();
  }, [load]);

  const onPrimaryAction = useCallback(
    (row) => {
      const task = workQueueRowToTask(row);
      const cta = resolveTaskCta(task, 'primary');
      if (cta.guidedEvidence) {
        openGuidedEvidence({
          propertyId: cta.guidedEvidence.propertyId,
          requirementId: cta.guidedEvidence.requirementId,
          initialEvidenceMode: cta.guidedEvidence.initialEvidenceMode || undefined,
        });
        return;
      }
      const url = cta.route || task.primary_action_url;
      if (url && url.startsWith('/')) {
        const target = resolveClientPortalPath(url, '/dashboard');
        recordClientPortalInteraction('work_queue_primary_action', { task_id: task.id, target });
        navigate(target);
      } else if (url && /^https?:\/\//i.test(url)) {
        window.open(url, '_blank', 'noopener,noreferrer');
      } else if (url) {
        window.location.assign(url);
      } else {
        navigate('/dashboard');
      }
    },
    [navigate, openGuidedEvidence],
  );

  if (!isClientUser) {
    return (
      <div className={portalPageRoot} data-testid="work-queue-forbidden">
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>Sign in as a client to view the work queue.</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (loading) {
    return (
      <div className={portalPageRoot} data-testid="work-queue-loading">
        <PortalLoadingPanel message="Loading work queue…" />
      </div>
    );
  }

  return (
    <div className={portalPageRoot} data-testid="work-queue-root">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-midnight-blue flex items-center gap-2">
          <ListTodo className="h-7 w-7 text-teal-600 shrink-0" aria-hidden />
          Work queue
        </h1>
        <p className="text-sm text-gray-600 mt-1 max-w-2xl">
          Open compliance and operations items in one sortable list. Actions use the same routes as your priorities
          inbox; hiding items elsewhere does not clear underlying obligations.
        </p>
      </div>

      {error ? (
        <Alert className="mb-4 border-amber-200 bg-amber-50">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {items.length === 0 && !error ? (
        <Card className="border border-gray-200" data-testid="work-queue-empty">
          <CardContent className="py-10 text-center text-gray-600 text-sm">
            Nothing in your work queue right now. When priorities or open jobs need attention, they will appear here.
          </CardContent>
        </Card>
      ) : null}

      {items.length > 0 ? (
        <ul className="space-y-3" data-testid="work-queue-list">
          {items.map((row) => {
            const label = row?.primary_action?.label || 'Open';
            const propLine = row.property_label || row.property_id || '';
            return (
              <li key={row.queue_item_id}>
                <Card
                  className="border border-gray-200 shadow-sm"
                  data-testid={`work-queue-row-${row.queue_item_id}`}
                >
                  <CardHeader className="pb-2">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={urgencyBadgeVariant(row.urgency_band)} data-testid="work-queue-urgency-badge">
                            {row.urgency_band}
                          </Badge>
                          <CardTitle className="text-base font-semibold text-midnight-blue break-words">
                            {row.title}
                          </CardTitle>
                        </div>
                        {propLine ? <p className="text-xs text-gray-500">{propLine}</p> : null}
                        {row.subtitle ? <p className="text-sm text-gray-700 break-words">{row.subtitle}</p> : null}
                        <p className="text-xs text-gray-600 italic" data-testid="work-queue-closure-line">
                          {row.closure_summary_user}
                        </p>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        className="shrink-0 bg-midnight-blue hover:bg-midnight-blue/90"
                        data-testid="work-queue-primary-action"
                        onClick={() => onPrimaryAction(row)}
                      >
                        {label}
                      </Button>
                    </div>
                  </CardHeader>
                </Card>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
