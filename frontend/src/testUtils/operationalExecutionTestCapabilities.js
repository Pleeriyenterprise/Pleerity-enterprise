/** Maps legacy hasFeature keys to operational execution capability flags for unit tests. */
export function defaultOperationalExecutionTestCaps(hasFeature = () => false) {
  return {
    canUseOpsMaintenance: hasFeature('maintenance_workflows'),
    canWriteOpsMaintenance: hasFeature('maintenance_workflows'),
    canUseOpsPredictive: hasFeature('predictive_maintenance'),
    canWriteOpsPredictive: hasFeature('predictive_maintenance'),
    canUseOpsContractors: hasFeature('contractor_network'),
    canWriteOpsContractors: hasFeature('contractor_network'),
    canUseOpsApprovals: hasFeature('invoicing'),
    canWriteOpsApprovals: hasFeature('invoicing'),
    canUseOpsComplianceReview: hasFeature('compliance_engine'),
    canWriteOpsComplianceReview: hasFeature('compliance_engine'),
    canViewDocuments: hasFeature('document_upload'),
    canUploadDocuments: hasFeature('document_upload'),
    canViewEvidence: hasFeature('document_upload'),
  };
}

export function allEnabledOperationalExecutionTestCaps() {
  return defaultOperationalExecutionTestCaps(() => true);
}
