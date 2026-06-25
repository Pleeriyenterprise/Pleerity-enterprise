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
  fieldErrors = {},
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
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-electric-teal ${
                fieldErrors[fieldId] ? 'border-red-500' : 'border-gray-200'
              }`}
              data-testid={`${testIdPrefix}-${fieldId}`}
              aria-invalid={fieldErrors[fieldId] ? 'true' : undefined}
              aria-describedby={
                fieldErrors[fieldId] ? `${testIdPrefix}-${fieldId}-error` : undefined
              }
            />
            {fieldErrors[fieldId] ? (
              <p
                id={`${testIdPrefix}-${fieldId}-error`}
                className="mt-1 text-sm text-red-600"
                data-testid={`${testIdPrefix}-${fieldId}-error`}
              >
                {fieldErrors[fieldId]}
              </p>
            ) : null}
          </div>
        ))}
      </div>
      {children}
    </div>
  );
}

export { buildLifecycleConfirmPayload, isLifecycleConfirmContractPresent };
