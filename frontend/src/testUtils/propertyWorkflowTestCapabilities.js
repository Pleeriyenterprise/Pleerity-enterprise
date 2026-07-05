/** Maps legacy hasFeature keys to property workflow capability flags for unit tests. */
export function defaultPropertyWorkflowTestCaps(hasFeature = () => false) {
  return {
    canViewProperties: true,
    canEditProperty: true,
    canViewScoreExplain: true,
    canViewScoreTrend: true,
    canViewEvidence: true,
    canViewDocuments: true,
    canUploadDocuments: true,
    canDownloadEvidence: true,
    canResolveRequirements: true,
    canMarkRequirementNotApplicable: true,
    canUseOpsMaintenance: hasFeature('maintenance_workflows'),
    canWriteOpsMaintenance: hasFeature('maintenance_workflows'),
    canUseOpsPredictive: hasFeature('predictive_maintenance'),
    canUseOpsContractors: hasFeature('contractor_network'),
    canUseOpsComplianceReview: hasFeature('compliance_engine'),
    canWriteOpsComplianceReview: hasFeature('compliance_engine'),
  };
}

/** All workflow capabilities enabled (Requirements integration tests). */
export function allEnabledPropertyWorkflowTestCaps() {
  return defaultPropertyWorkflowTestCaps(() => true);
}
