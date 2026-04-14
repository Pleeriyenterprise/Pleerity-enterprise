/**
 * Client portal vocabulary — use for consistent, credible user-facing terms.
 * Prefer importing labels from here over scattering ad-hoc strings.
 */
export const PORTAL_COPY = {
  requirement: 'Requirement',
  requirements: 'Requirements',
  complianceJob: 'Compliance job',
  maintenanceJob: 'Maintenance job',
  /** Nav / list: portfolio execution surface (maintenance + compliance); URLs may still use /operations/work-orders. */
  jobs: 'Jobs',
  job: 'Job',
  jobsListDescription: 'Maintenance and compliance jobs for your portfolio.',
  workOrders: 'Jobs',
  maintenanceIssue: 'Maintenance issue',
  /** Plural label — use this instead of `{singular}s` in JSX to avoid parse/TDZ edge cases. */
  maintenanceIssues: 'Maintenance issues',
  /** Predictive / rule-based flags — not the maintenance issues queue. */
  riskSignal: 'Flagged issue',
  riskSignalsActiveHeading: 'Flagged issues (active)',
  uploadDocument: 'Upload document',
  viewDocuments: 'View documents',
  startRenewal: 'Start renewal',
  requestContractor: 'Request contractor',
  confirmVisit: 'Confirm visit',
  awaitingVerification: 'Awaiting verification',
  estimatedDate: 'Estimated date',
  verifiedDocument: 'Verified document',
  viewDetails: 'View details',
  fixComplianceIssue: 'Fix compliance issue',
  fixIssue: 'Fix issue',
  reviewIssue: 'Review issue',
  viewProperty: 'View property',
  trackedItem: 'tracked item',
  trackedItems: 'tracked items',
  addWorkOrder: 'Fix issue',
  upgradeForWorkOrders: 'Upgrade for jobs',
  viewReports: 'View reports',
  reportIssue: 'Report issue',
  loadingApprovals: 'Loading approvals…',
  loadingBilling: 'Loading billing…',
  loadingReports: 'Loading reports…',
  loadingProperties: 'Loading properties…',
  recordPayment: 'Record payment',
  reviewApproval: 'Review approval',
};
