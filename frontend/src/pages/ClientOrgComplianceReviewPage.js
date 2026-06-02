/**
 * Deprecated: organisation review queue removed (REVIEW-ASSURANCE-SIMPLIFICATION-01).
 * Declarations are self-recorded; platform oversight uses admin escalation + document verification.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { portalPageRoot } from '../components/client/ClientPortalPatterns';

export default function ClientOrgComplianceReviewPage() {
  const navigate = useNavigate();

  return (
    <div className={portalPageRoot} data-testid="compliance-review-deprecated">
      <Card>
        <CardHeader>
          <CardTitle>Compliance review</CardTitle>
          <CardDescription>
            Organisation review has been removed. Declarations you record are self-recorded on file (auditable and
            timestamped). Items requiring Pleerity oversight appear in platform review workflows — not a separate org
            queue.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Assurance tiers: self-recorded declarations, platform-reviewed escalations, and verified documents.
          </p>
          <Button variant="default" onClick={() => navigate('/requirements')}>
            Go to Requirements
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
