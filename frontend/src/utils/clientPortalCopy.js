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
  riskSignal: 'Risk signal',
  riskSignalsActiveHeading: 'Risk signals (active)',
  uploadDocument: 'Upload document',
  viewDocuments: 'View documents',
  startRenewal: 'Start renewal',
  requestContractor: 'Request contractor',
  confirmVisit: 'Confirm visit',
  awaitingVerification: 'Awaiting verification',
  estimatedDate: 'Estimated date',
  verifiedDocument: 'Verified document',
  viewDetails: 'View details',
  viewProperty: 'View property',
  trackedItem: 'tracked item',
  trackedItems: 'tracked items',
  addWorkOrder: 'Create job',
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
