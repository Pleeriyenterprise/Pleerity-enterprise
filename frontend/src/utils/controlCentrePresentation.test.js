import {
  displayJobName,
  overallAutomationHealthLabel,
  threatDetectionsToDisplayRows,
  threatDetectionsRawJson,
  complianceStatusBucketLabel,
  complianceScoreBandLabel,
  humanizeScoringNoteText,
  humanizeScoringNoteKey,
  THREAT_DETECTION_LABELS,
} from './controlCentrePresentation';

describe('controlCentrePresentation', () => {
  describe('displayJobName', () => {
    it('maps known worker ids to readable titles', () => {
      expect(displayJobName('compliance_recalc_worker')).toBe('Compliance score recalculation worker');
      expect(displayJobName('risk_signal_regen_worker')).toBe('Risk signal refresh worker');
    });

    it('title-cases unknown snake_case ids', () => {
      expect(displayJobName('custom_batch_job')).toBe('Custom Batch Job');
    });
  });

  describe('overallAutomationHealthLabel', () => {
    it('maps API overall health enums', () => {
      expect(overallAutomationHealthLabel('healthy')).toBe('Healthy');
      expect(overallAutomationHealthLabel('degraded')).toBe('Degraded');
      expect(overallAutomationHealthLabel('attention_required')).toBe('Attention required');
    });
  });

  describe('threatDetectionsToDisplayRows', () => {
    it('does not emit raw snake_case keys as primary labels for known types', () => {
      const rows = threatDetectionsToDisplayRows({
        endpoint_probing: 2,
        token_reuse_multi_ip: 1,
        cross_user_data_access_probe: 3,
      });
      const labels = rows.map((r) => r[0]).join(' ');
      expect(labels).not.toMatch(/endpoint_probing/);
      expect(labels).not.toMatch(/token_reuse_multi_ip/);
      expect(labels).not.toMatch(/cross_user_data_access_probe/);
      expect(labels).toContain('Endpoint probing');
      expect(labels).toContain('Token reuse across multiple IPs');
    });

    it('returns a single friendly row when all counts are zero', () => {
      const rows = threatDetectionsToDisplayRows({});
      expect(rows).toHaveLength(1);
      expect(rows[0][1]).toBe('0');
    });
  });

  describe('threatDetectionsRawJson', () => {
    it('preserves raw structure for diagnostics', () => {
      const raw = threatDetectionsRawJson({ endpoint_probing: 1 });
      expect(raw).toContain('endpoint_probing');
    });
  });

  describe('complianceStatusBucketLabel', () => {
    it('renders UNKNOWN as human-friendly', () => {
      expect(complianceStatusBucketLabel('UNKNOWN')).toBe('Unclassified');
    });
  });

  describe('complianceScoreBandLabel', () => {
    it('maps unknown bucket to no score stored', () => {
      expect(complianceScoreBandLabel('unknown')).toBe('No score stored');
    });
  });

  describe('humanizeScoringNoteText', () => {
    it('replaces delivery_unknown with admin phrasing', () => {
      expect(humanizeScoringNoteText('stale delivery_unknown.')).toBe('stale delivery confirmation still pending.');
    });
  });

  describe('humanizeScoringNoteKey', () => {
    it('maps scoring note keys', () => {
      expect(humanizeScoringNoteKey('automation_health')).toBe('Automation health');
    });
  });

  it('THREAT_DETECTION_LABELS covers keys referenced in audit', () => {
    expect(THREAT_DETECTION_LABELS.endpoint_probing).toBeDefined();
    expect(THREAT_DETECTION_LABELS.token_reuse_multi_ip).toBeDefined();
    expect(THREAT_DETECTION_LABELS.cross_user_data_access_probe).toBeDefined();
  });
});
