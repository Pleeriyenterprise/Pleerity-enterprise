import fs from 'fs';
import path from 'path';

const PAGE = path.join(__dirname, 'PropertyDetailPage.js');

describe('PropertyDetailPage capability consumption', () => {
  it('uses runtime contract capabilities instead of entitlements', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/usePropertyWorkflowCapabilities/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
  });

  it('gates property workflow surfaces on runtime capability flags', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/canUseOpsMaintenance/);
    expect(src).toMatch(/canUseOpsPredictive/);
    expect(src).toMatch(/canUseOpsContractors/);
    expect(src).toMatch(/canUseOpsComplianceReview/);
    expect(src).toMatch(/canViewScoreExplain/);
    expect(src).toMatch(/canViewScoreTrend/);
    expect(src).toMatch(/canViewEvidence/);
    expect(src).toMatch(/canUploadDocuments/);
    expect(src).toMatch(/isCapabilityDeniedApiError/);
  });
});
