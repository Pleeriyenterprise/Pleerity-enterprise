/**
 * TRUST-01: read-only presentation helpers for persisted compliance evidence records (CER).
 * Authoritative persisted values only — no lifecycle/authority projection.
 */

/**
 * @param {Array<Record<string, unknown>>|null|undefined} records
 * @returns {Record<string, unknown>|null}
 */
export function pickLatestComplianceEvidenceRecord(records) {
  if (!Array.isArray(records) || records.length === 0) return null;
  for (const rec of records) {
    if (!rec || typeof rec !== 'object') continue;
    if (rec.archived === true) continue;
    return rec;
  }
  return null;
}

/**
 * @param {string} key
 */
function humanizeFieldKey(key) {
  return String(key || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** @param {unknown} val */
function isEmptyDisplayValue(val) {
  return val == null || val === '' || val === undefined;
}

/**
 * Client-facing display formatter — never exposes raw JSON or internal nulls.
 * @param {unknown} val
 * @param {{ missingLabel?: string }} [options]
 */
export function formatFieldValueForDisplay(val, options = {}) {
  const missingLabel = options.missingLabel || 'Not provided';
  if (isEmptyDisplayValue(val)) return missingLabel;
  if (typeof val === 'boolean') return val ? 'Yes' : 'No';
  if (typeof val === 'object') {
    if (Array.isArray(val)) {
      const parts = val.map((x) => formatFieldValueForDisplay(x, options)).filter((x) => x !== missingLabel);
      return parts.length ? parts.join(', ') : missingLabel;
    }
    const answer = val.answer ?? val.value;
    const notes = val.notes ?? val.observation;
    if (!isEmptyDisplayValue(answer)) {
      const base = formatFieldValueForDisplay(answer, options);
      const noteText = !isEmptyDisplayValue(notes) ? String(notes).trim() : '';
      return noteText ? `${base} (${noteText})` : base;
    }
    if (!isEmptyDisplayValue(notes)) return String(notes).trim();
    return missingLabel;
  }
  return String(val);
}

/** @param {unknown} val */
function formatFieldValue(val) {
  return formatFieldValueForDisplay(val, { missingLabel: '—' });
}

/**
 * @param {Record<string, unknown>|null|undefined} record
 * @param {{ operatorPresentation?: boolean }} [options]
 * @returns {{ sections: Array<{ title: string, rows: Array<{ label: string, value: string }> }>, meta: Array<{ label: string, value: string }> }}
 */
export function buildComplianceEvidenceRecordDisplay(record, options = {}) {
  if (!record || typeof record !== 'object') {
    return { sections: [], meta: [] };
  }

  const mode = String(record.evidence_mode || '').trim().toUpperCase();
  const payload = record.evidence_payload && typeof record.evidence_payload === 'object' ? record.evidence_payload : {};
  /** @type {Array<{ title: string, rows: Array<{ label: string, value: string }> }>} */
  const sections = [];
  /** @type {Array<{ label: string, value: string }>} */
  const meta = [];

  if (mode) meta.push({ label: 'Evidence method', value: humanizeFieldKey(mode) });

  const vs = String(record.verification_status || '').trim();
  if (vs) meta.push({ label: 'Verification', value: humanizeFieldKey(vs) });
  if (record.verified_at) meta.push({ label: 'Verified at', value: formatFieldValue(record.verified_at) });
  if (record.created_at) meta.push({ label: 'Submitted at', value: formatFieldValue(record.created_at) });
  if (record.evidence_confidence_level && !options.operatorPresentation) {
    meta.push({ label: 'Confidence', value: humanizeFieldKey(String(record.evidence_confidence_level)) });
  }

  if (mode === 'STRUCTURED_DECLARATION') {
    const rows = [];
    const stmt = String(payload.declaration_statement || '').trim();
    if (stmt) rows.push({ label: 'Declaration', value: stmt });
    const fields = payload.structured_fields;
    if (fields && typeof fields === 'object') {
      for (const [key, val] of Object.entries(fields)) {
        const display = formatFieldValueForDisplay(val);
        if (display === 'Not provided') continue;
        rows.push({ label: humanizeFieldKey(key), value: display });
      }
    }
    if (rows.length) sections.push({ title: 'Structured declaration', rows });
  } else if (mode === 'CONTRACTOR_CONFIRMATION') {
    const rows = [];
    for (const key of [
      'contractor_name',
      'company_name',
      'completion_date',
      'work_summary',
      'contractor_email',
      'contractor_phone',
      'trade_type',
      'accreditation_number',
    ]) {
      if (payload[key] != null && String(payload[key]).trim() !== '') {
        rows.push({ label: humanizeFieldKey(key), value: formatFieldValue(payload[key]) });
      }
    }
    if (rows.length) sections.push({ title: 'Contractor confirmation', rows });
  } else if (mode === 'INSPECTION_CHECKLIST') {
    const rows = [];
    if (payload.inspection_date) rows.push({ label: 'Inspection date', value: formatFieldValue(payload.inspection_date) });
    if (payload.responsible_person) rows.push({ label: 'Responsible person', value: formatFieldValue(payload.responsible_person) });
    if (payload.optional_notes) rows.push({ label: 'Notes', value: formatFieldValue(payload.optional_notes) });
    const answers = payload.checklist_answers;
    if (answers && typeof answers === 'object') {
      for (const [key, val] of Object.entries(answers)) {
        const display = formatFieldValueForDisplay(val);
        if (display === 'Not provided') continue;
        rows.push({ label: humanizeFieldKey(key), value: display });
      }
    }
    if (rows.length) sections.push({ title: 'Inspection checklist', rows });
  } else if (Object.keys(payload).length > 0) {
    const rows = Object.entries(payload).map(([key, val]) => ({
      label: humanizeFieldKey(key),
      value: formatFieldValue(val),
    }));
    sections.push({ title: 'Evidence details', rows });
  }

  return { sections, meta };
}

/**
 * @param {Record<string, unknown>|null|undefined} ta
 */
export function isViewExistingSubmissionCta(ta) {
  if (!ta || typeof ta !== 'object') return false;
  if (String(ta.primary_action_handler || '') !== 'guided_evidence') return false;
  const label = String(ta.primary_action_label || '').trim();
  return (
    /^view submission$/i.test(label) ||
    /^view verified evidence$/i.test(label) ||
    /^review submission$/i.test(label) ||
    /^view or update evidence$/i.test(label)
  );
}

/**
 * Compact summary lines for post-submit confirmation (authoritative evidence_record only).
 * @param {Record<string, unknown>|null|undefined} record
 * @returns {string[]}
 */
export function summarizeSubmittedEvidenceRecord(record) {
  if (!record || typeof record !== 'object') return [];
  const { sections, meta } = buildComplianceEvidenceRecordDisplay(record);
  const lines = [];
  for (const m of meta) {
    if (m.label === 'Submitted at' || m.label === 'Evidence method' || m.label === 'Verification') {
      lines.push(`${m.label}: ${m.value}`);
    }
  }
  for (const sec of sections) {
    for (const row of sec.rows.slice(0, 4)) {
      lines.push(`${row.label}: ${row.value}`);
    }
  }
  return lines.slice(0, 8);
}
