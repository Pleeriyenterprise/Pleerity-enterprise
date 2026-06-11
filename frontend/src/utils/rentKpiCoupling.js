/**
 * Build ledger list API params from tab, filters, and active KPI.
 */
import { rentKpiCompatibleWithTab } from './rentKpiCopy';

const LEDGER_LIMIT = 200;

/**
 * @param {{
 *   tab: string,
 *   filterProperty?: string,
 *   filterStatus?: string,
 *   activeKpi?: { filter?: Record<string, unknown> } | null,
 * }} opts
 */
export function buildRentLedgerParams(opts) {
  const { tab, filterProperty, filterStatus, activeKpi } = opts;
  const params = { limit: LEDGER_LIMIT };
  if (filterProperty) params.property_id = filterProperty;

  const kpi = activeKpi && rentKpiCompatibleWithTab(activeKpi, tab) ? activeKpi : null;

  if (kpi?.filter?.overdue_only) {
    params.overdue_only = true;
  } else if (tab === 'attention' || kpi?.filter?.attention_only) {
    params.attention_only = true;
  } else if (filterStatus && tab === 'ledger') {
    params.status = filterStatus;
  } else if (kpi?.filter?.status) {
    params.status = kpi.filter.status;
  }

  return params;
}

export { LEDGER_LIMIT };
