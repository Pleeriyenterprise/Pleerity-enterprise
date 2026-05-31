/**
 * Admin escalation review queue — separate from routine document certificate verification.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { adminAPI } from '../api/client';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { AlertTriangle, Loader2, RefreshCw } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';

function formatDate(s) {
  if (!s) return '—';
  try {
    return new Date(s).toLocaleDateString(undefined, { dateStyle: 'short' });
  } catch {
    return s;
  }
}

export default function AdminEscalationReviewQueuePage() {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.getEscalationReviewQueue();
      setItems(res?.data?.items || []);
    } catch (e) {
      toast.error('Failed to load escalation queue');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <AlertTriangle className="h-6 w-6 text-amber-600" />
            Escalation review queue
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Risk-triggered escalations only — not routine EPC/Gas/EICR certificate verification.
          </p>
        </div>
        <Button variant="outline" onClick={load} disabled={loading}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1" />}
          Refresh
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Escalated items ({items.length})</CardTitle>
          <CardDescription>review_owner = platform_admin_escalation</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-muted-foreground">No escalated review items.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Client</TableHead>
                  <TableHead>Property</TableHead>
                  <TableHead>Requirement</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead>Truth label</TableHead>
                  <TableHead>Semantic state</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((row) => (
                  <TableRow key={`${row.client_id}-${row.requirement_id}`}>
                    <TableCell>{row.client_name || row.client_id}</TableCell>
                    <TableCell>{row.property_label || row.property_id}</TableCell>
                    <TableCell>{row.display_label || row.requirement_type}</TableCell>
                    <TableCell>{formatDate(row.submitted_at)}</TableCell>
                    <TableCell>{row.truth_presentation_label || '—'}</TableCell>
                    <TableCell>{row.semantic_state || '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
