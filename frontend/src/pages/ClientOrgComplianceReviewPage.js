/**
 * Operations → Compliance review: org-admin queue for ORG_ADMIN_REVIEWED family.
 * Discovery + visibility only — verify/reject uses existing compliance-evidence verification API.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
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
import { ClipboardCheck, Loader2, Eye, CheckCircle, XCircle } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';
import { PortalLoadingPanel, portalPageRoot } from '../components/client/ClientPortalPatterns';
import { submitOrgComplianceEvidenceVerification } from '../utils/orgComplianceReviewOperator';

function formatDate(s) {
  if (!s) return '—';
  try {
    return new Date(s).toLocaleDateString(undefined, { dateStyle: 'short' });
  } catch {
    return s;
  }
}

export default function ClientOrgComplianceReviewPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);
  const [actingId, setActingId] = useState(null);

  const isOrgReviewer = String(user?.role || '').toUpperCase() === 'ROLE_CLIENT_ADMIN';

  const load = useCallback(async () => {
    if (!isOrgReviewer) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const res = await clientAPI.getOrgReviewQueue();
      setItems(res?.data?.items || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load compliance review queue');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [isOrgReviewer]);

  useEffect(() => {
    load();
  }, [load]);

  const openReview = (row) => {
    const route = row?.review_deeplink || row?.review_route;
    if (route) navigate(route);
  };

  const verify = async (row, decision) => {
    const pid = row?.property_id;
    const rid = row?.requirement_id;
    const eid = row?.evidence_record_id;
    if (!pid || !rid || !eid) {
      toast.error('Missing evidence context for verification');
      return;
    }
    setActingId(`${eid}:${decision}`);
    try {
      await submitOrgComplianceEvidenceVerification({
        propertyId: pid,
        requirementId: rid,
        evidenceRecordId: eid,
        decision,
      });
      toast.success(decision === 'VERIFY' ? 'Submission verified' : 'Submission rejected');
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Verification failed');
    } finally {
      setActingId(null);
    }
  };

  if (!isOrgReviewer) {
    return (
      <div className={portalPageRoot}>
        <Card>
          <CardHeader>
            <CardTitle>Compliance review</CardTitle>
            <CardDescription>
              Organisation review queue is available to client organisation admins only.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className={portalPageRoot}>
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <ClipboardCheck className="h-6 w-6 text-teal-700" />
            Compliance review queue
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Organisation-admin review for recorded compliance declarations. Uses existing verification flows.
          </p>
        </div>
        <Button variant="outline" onClick={load} disabled={loading}>
          Refresh
        </Button>
      </div>

      {loading ? (
        <PortalLoadingPanel label="Loading review queue…" />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Pending organisation review ({items.length})</CardTitle>
          </CardHeader>
          <CardContent>
            {items.length === 0 ? (
              <p className="text-sm text-muted-foreground">No submissions awaiting organisation review.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Property</TableHead>
                    <TableHead>Requirement</TableHead>
                    <TableHead>Submitted</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Review owner</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((row) => (
                    <TableRow key={`${row.property_id}-${row.requirement_id}`}>
                      <TableCell>{row.property_label || row.property_id}</TableCell>
                      <TableCell>{row.display_label || row.requirement_type}</TableCell>
                      <TableCell>{formatDate(row.submitted_at)}</TableCell>
                      <TableCell>{row.truth_presentation_label || '—'}</TableCell>
                      <TableCell>{row.review_owner || '—'}</TableCell>
                      <TableCell className="text-right space-x-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => openReview(row)}
                          data-testid={`org-review-open-${row.requirement_id}`}
                        >
                          <Eye className="h-4 w-4 mr-1" />
                          Review submission
                        </Button>
                        {row.evidence_record_id && (
                          <>
                            <Button
                              size="sm"
                              variant="default"
                              disabled={actingId === `${row.evidence_record_id}:VERIFY`}
                              onClick={() => verify(row, 'VERIFY')}
                            >
                              {actingId === `${row.evidence_record_id}:VERIFY` ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <>
                                  <CheckCircle className="h-4 w-4 mr-1" />
                                  Verify
                                </>
                              )}
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              disabled={actingId === `${row.evidence_record_id}:REJECT`}
                              onClick={() => verify(row, 'REJECT')}
                            >
                              {actingId === `${row.evidence_record_id}:REJECT` ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <>
                                  <XCircle className="h-4 w-4 mr-1" />
                                  Reject
                                </>
                              )}
                            </Button>
                          </>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
