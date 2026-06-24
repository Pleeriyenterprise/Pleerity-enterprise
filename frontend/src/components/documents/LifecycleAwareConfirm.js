import React from 'react';
import {
  buildLifecycleConfirmPayload,
  fieldLabel,
  getConfirmFieldIds,
  isDateField,
  isFieldForbidden,
  isLifecycleConfirmContractPresent,
} from '../../utils/lifecycleAwareConfirm';

/**
 * Contract-driven confirm fields for document extraction review.
 * Renders only when lifecycle_confirm_contract is present on GET extraction.
 */
export default function LifecycleAwareConfirm({
  contract,
  values,
  onChange,
  testIdPrefix = 'lifecycle-confirm',
  children,
}) {
  if (!isLifecycleConfirmContractPresent(contract)) {
    return null;
  }

  const required = new Set(contract.confirm_fields || []);
  const fieldIds = getConfirmFieldIds(contract).filter(
    (fieldId) => !isFieldForbidden(contract, fieldId),
  );

  return (
    <div className="space-y-4" data-testid={`${testIdPrefix}-form`}>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {fieldIds.map((fieldId) => (
          <div key={fieldId}>
            <label
              className="block text-sm font-medium text-gray-700 mb-1"
              htmlFor={`${testIdPrefix}-${fieldId}`}
            >
              {fieldLabel(contract, fieldId)}
              {required.has(fieldId) ? <span className="text-red-500"> *</span> : null}
            </label>
            <input
              id={`${testIdPrefix}-${fieldId}`}
              type={isDateField(fieldId) ? 'date' : 'text'}
              value={values[fieldId] || ''}
              onChange={(e) => onChange(fieldId, e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
              data-testid={`${testIdPrefix}-${fieldId}`}
            />
          </div>
        ))}
      </div>
      {children}
    </div>
  );
}

export { buildLifecycleConfirmPayload, isLifecycleConfirmContractPresent };
