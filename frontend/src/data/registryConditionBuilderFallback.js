/**
 * Fallback when GET /admin/compliance/registry/controlled-field-options fails.
 * Keep aligned with ``condition_builder_options_payload`` in compliance_registry_conditions.py.
 */
export const REGISTRY_CONDITION_BUILDER_FALLBACK = {
  condition_fields: [
    {
      value: 'building_age_years',
      label: 'Building age (years)',
      kind: 'number',
      operators: [
        { storage: '!=', label: 'Does not equal' },
        { storage: '==', label: 'Equals' },
        { storage: 'gt', label: 'Greater than' },
        { storage: 'lt', label: 'Less than' },
      ],
    },
    {
      value: 'cert_gas_safety',
      label: 'Gas safety certificate',
      kind: 'boolean',
      operators: [
        { storage: '!=', label: 'Does not equal' },
        { storage: '==', label: 'Equals' },
        { storage: 'false', label: 'Is false (no)' },
        { storage: 'true', label: 'Is true (yes)' },
      ],
    },
    {
      value: 'cert_licence',
      label: 'Licence certificate',
      kind: 'boolean',
      operators: [
        { storage: '!=', label: 'Does not equal' },
        { storage: '==', label: 'Equals' },
        { storage: 'false', label: 'Is false (no)' },
        { storage: 'true', label: 'Is true (yes)' },
      ],
    },
    {
      value: 'deposit_taken',
      label: 'Deposit taken',
      kind: 'boolean',
      operators: [
        { storage: '!=', label: 'Does not equal' },
        { storage: '==', label: 'Equals' },
        { storage: 'false', label: 'Is false (no)' },
        { storage: 'true', label: 'Is true (yes)' },
      ],
    },
    {
      value: 'furnished',
      label: 'Furnished',
      kind: 'boolean',
      operators: [
        { storage: '!=', label: 'Does not equal' },
        { storage: '==', label: 'Equals' },
        { storage: 'false', label: 'Is false (no)' },
        { storage: 'true', label: 'Is true (yes)' },
      ],
    },
    {
      value: 'has_communal_areas',
      label: 'Has communal areas',
      kind: 'boolean',
      operators: [
        { storage: '!=', label: 'Does not equal' },
        { storage: '==', label: 'Equals' },
        { storage: 'false', label: 'Is false (no)' },
        { storage: 'true', label: 'Is true (yes)' },
      ],
    },
    {
      value: 'has_gas_supply',
      label: 'Has gas supply',
      kind: 'boolean',
      operators: [
        { storage: '!=', label: 'Does not equal' },
        { storage: '==', label: 'Equals' },
        { storage: 'false', label: 'Is false (no)' },
        { storage: 'true', label: 'Is true (yes)' },
      ],
    },
    {
      value: 'is_hmo',
      label: 'Is HMO',
      kind: 'boolean',
      operators: [
        { storage: '!=', label: 'Does not equal' },
        { storage: '==', label: 'Equals' },
        { storage: 'false', label: 'Is false (no)' },
        { storage: 'true', label: 'Is true (yes)' },
      ],
    },
    {
      value: 'licence_required',
      label: 'Licence required',
      kind: 'boolean',
      operators: [
        { storage: '!=', label: 'Does not equal' },
        { storage: '==', label: 'Equals' },
        { storage: 'false', label: 'Is false (no)' },
        { storage: 'true', label: 'Is true (yes)' },
      ],
    },
    {
      value: 'licence_type',
      label: 'Licence type',
      kind: 'string',
      operators: [
        { storage: '!=', label: 'Does not equal' },
        { storage: '==', label: 'Equals' },
        { storage: 'in', label: 'Is one of' },
        { storage: 'not_in', label: 'Is not one of' },
      ],
    },
    {
      value: 'local_authority',
      label: 'Local authority',
      kind: 'string',
      operators: [
        { storage: '!=', label: 'Does not equal' },
        { storage: '==', label: 'Equals' },
        { storage: 'in', label: 'Is one of' },
        { storage: 'not_in', label: 'Is not one of' },
      ],
    },
    {
      value: 'property_type',
      label: 'Property type',
      kind: 'string',
      operators: [
        { storage: '!=', label: 'Does not equal' },
        { storage: '==', label: 'Equals' },
        { storage: 'in', label: 'Is one of' },
        { storage: 'not_in', label: 'Is not one of' },
      ],
    },
    {
      value: 'tenancy_active',
      label: 'Tenancy active',
      kind: 'boolean',
      operators: [
        { storage: '!=', label: 'Does not equal' },
        { storage: '==', label: 'Equals' },
        { storage: 'false', label: 'Is false (no)' },
        { storage: 'true', label: 'Is true (yes)' },
      ],
    },
  ],
  condition_logic_options: [
    { value: 'ALL', label: 'All rules must match (AND)' },
    { value: 'ANY', label: 'Any rule may match (OR)' },
  ],
  condition_templates: [
    { id: 'gas', label: 'Gas properties only', conditions: { logic: 'ALL', rules: [{ field: 'has_gas_supply', op: 'true' }] } },
    { id: 'hmo', label: 'HMO only', conditions: { logic: 'ALL', rules: [{ field: 'is_hmo', op: 'true' }] } },
    { id: 'tenancy', label: 'Active tenancy only', conditions: { logic: 'ALL', rules: [{ field: 'tenancy_active', op: 'true' }] } },
    { id: 'deposit', label: 'Deposit taken only', conditions: { logic: 'ALL', rules: [{ field: 'deposit_taken', op: 'true' }] } },
    { id: 'communal', label: 'Communal areas only', conditions: { logic: 'ALL', rules: [{ field: 'has_communal_areas', op: 'true' }] } },
    { id: 'clear', label: 'Clear all rules', conditions: { logic: 'ALL', rules: [] } },
  ],
};
