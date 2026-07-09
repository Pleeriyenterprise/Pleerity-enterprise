import { useMemo } from 'react';
import { useLifecycleRuntime } from '../contexts/LifecycleRuntimeContext';
import {
  evaluateCapabilityGrant,
  extractCapabilityDeniedFromError,
  GRANT_ALLOW,
  GRANT_DENY,
} from './capabilityRuntime';

/** Governed Runtime Contract capability ids for the Billing domain. */
export const BILLING_CAPABILITY = {
  VIEW: 'CAP_BILLING_VIEW',
  INVOICES: 'CAP_BILLING_INVOICES',
  PAYMENT_METHODS: 'CAP_BILLING_PAYMENT_METHODS',
  CHECKOUT: 'CAP_BILLING_CHECKOUT',
  SUB_MANAGE: 'CAP_SUB_MANAGE',
  SUB_CANCEL: 'CAP_SUB_CANCEL',
};

/**
 * Runtime Contract capability consumption for Billing UI.
 */
export function useBillingCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      canViewBilling: capabilityAllowed(BILLING_CAPABILITY.VIEW, 'read'),
      canViewInvoices: capabilityAllowed(BILLING_CAPABILITY.INVOICES, 'read'),
      canViewPaymentMethods: capabilityAllowed(BILLING_CAPABILITY.PAYMENT_METHODS, 'read'),
      canCheckout: capabilityAllowed(BILLING_CAPABILITY.CHECKOUT, 'write'),
      canManageSubscription: capabilityAllowed(BILLING_CAPABILITY.SUB_MANAGE, 'write'),
      canCancelSubscription: capabilityAllowed(BILLING_CAPABILITY.SUB_CANCEL, 'write'),
      getCapabilityGrant,
    }),
    [capabilityAllowed, getCapabilityGrant],
  );
}

export function getCapabilityDeniedMessage(error, fallback = 'Action not permitted') {
  const detail = extractCapabilityDeniedFromError(error);
  return detail?.message || fallback;
}

export function isCapabilityDeniedApiError(error) {
  return Boolean(extractCapabilityDeniedFromError(error));
}

/** Portfolio usage hint from billing status API (not entitlements). */
export function formatBillingUsageHint(billingStatus) {
  if (!billingStatus || typeof billingStatus.properties_used !== 'number') return null;
  const n = billingStatus.properties_used;
  const cap = billingStatus.properties_limit;
  if (typeof cap === 'number' && cap > 0) {
    if (n >= cap) {
      return `You're at your plan's property limit (${n} of ${cap}). Higher tiers can add capacity and optional automation — Billing lists current limits.`;
    }
    return `You have ${n} propert${n === 1 ? 'y' : 'ies'} on file; your plan allows up to ${cap}.`;
  }
  return `You have ${n} propert${n === 1 ? 'y' : 'ies'} on file.`;
}

/**
 * Lifecycle grant fixtures mirroring backend billing-exempt recovery matrix (CAP_BILLING_* = ALLOW).
 */
export const BILLING_LIFECYCLE_GRANT_FIXTURES = {
  ACTIVE: {
    CAP_BILLING_VIEW: GRANT_ALLOW,
    CAP_BILLING_INVOICES: GRANT_ALLOW,
    CAP_BILLING_PAYMENT_METHODS: GRANT_ALLOW,
    CAP_BILLING_CHECKOUT: GRANT_ALLOW,
    CAP_SUB_MANAGE: GRANT_ALLOW,
    CAP_SUB_CANCEL: GRANT_ALLOW,
  },
  TRIAL: {
    CAP_BILLING_VIEW: GRANT_ALLOW,
    CAP_BILLING_INVOICES: GRANT_ALLOW,
    CAP_BILLING_PAYMENT_METHODS: GRANT_ALLOW,
    CAP_BILLING_CHECKOUT: GRANT_ALLOW,
    CAP_SUB_MANAGE: GRANT_ALLOW,
    CAP_SUB_CANCEL: GRANT_ALLOW,
  },
  GRACE_PERIOD: {
    CAP_BILLING_VIEW: GRANT_ALLOW,
    CAP_BILLING_INVOICES: GRANT_ALLOW,
    CAP_BILLING_PAYMENT_METHODS: GRANT_ALLOW,
    CAP_BILLING_CHECKOUT: GRANT_ALLOW,
    CAP_SUB_MANAGE: GRANT_ALLOW,
    CAP_SUB_CANCEL: GRANT_ALLOW,
  },
  CANCELLATION_SCHEDULED: {
    CAP_BILLING_VIEW: GRANT_ALLOW,
    CAP_BILLING_INVOICES: GRANT_ALLOW,
    CAP_BILLING_PAYMENT_METHODS: GRANT_ALLOW,
    CAP_BILLING_CHECKOUT: GRANT_ALLOW,
    CAP_SUB_MANAGE: GRANT_ALLOW,
    CAP_SUB_CANCEL: GRANT_ALLOW,
  },
  CANCELLED_IMMEDIATE: {
    CAP_BILLING_VIEW: GRANT_ALLOW,
    CAP_BILLING_INVOICES: GRANT_ALLOW,
    CAP_BILLING_PAYMENT_METHODS: GRANT_ALLOW,
    CAP_BILLING_CHECKOUT: GRANT_ALLOW,
    CAP_SUB_MANAGE: GRANT_ALLOW,
    CAP_SUB_CANCEL: GRANT_ALLOW,
  },
  SUBSCRIPTION_EXPIRED: {
    CAP_BILLING_VIEW: GRANT_ALLOW,
    CAP_BILLING_INVOICES: GRANT_ALLOW,
    CAP_BILLING_PAYMENT_METHODS: GRANT_ALLOW,
    CAP_BILLING_CHECKOUT: GRANT_ALLOW,
    CAP_SUB_MANAGE: GRANT_ALLOW,
    CAP_SUB_CANCEL: GRANT_ALLOW,
  },
  READ_ONLY: {
    CAP_BILLING_VIEW: GRANT_ALLOW,
    CAP_BILLING_INVOICES: GRANT_ALLOW,
    CAP_BILLING_PAYMENT_METHODS: GRANT_ALLOW,
    CAP_BILLING_CHECKOUT: GRANT_ALLOW,
    CAP_SUB_MANAGE: GRANT_ALLOW,
    CAP_SUB_CANCEL: GRANT_ALLOW,
  },
  SUSPENDED: {
    CAP_BILLING_VIEW: GRANT_ALLOW,
    CAP_BILLING_INVOICES: GRANT_ALLOW,
    CAP_BILLING_PAYMENT_METHODS: GRANT_ALLOW,
    CAP_BILLING_CHECKOUT: GRANT_ALLOW,
    CAP_SUB_MANAGE: GRANT_ALLOW,
    CAP_SUB_CANCEL: GRANT_ALLOW,
  },
  ARCHIVED: {
    CAP_BILLING_VIEW: GRANT_DENY,
    CAP_BILLING_INVOICES: GRANT_DENY,
    CAP_BILLING_PAYMENT_METHODS: GRANT_DENY,
    CAP_BILLING_CHECKOUT: GRANT_DENY,
    CAP_SUB_MANAGE: GRANT_DENY,
    CAP_SUB_CANCEL: GRANT_DENY,
  },
  ACCOUNT_DELETED: {
    CAP_BILLING_VIEW: GRANT_DENY,
    CAP_BILLING_INVOICES: GRANT_DENY,
    CAP_BILLING_PAYMENT_METHODS: GRANT_DENY,
    CAP_BILLING_CHECKOUT: GRANT_DENY,
    CAP_SUB_MANAGE: GRANT_DENY,
    CAP_SUB_CANCEL: GRANT_DENY,
  },
  UNKNOWN: {
    CAP_BILLING_VIEW: GRANT_DENY,
    CAP_BILLING_INVOICES: GRANT_DENY,
    CAP_BILLING_PAYMENT_METHODS: GRANT_DENY,
    CAP_BILLING_CHECKOUT: GRANT_DENY,
    CAP_SUB_MANAGE: GRANT_DENY,
    CAP_SUB_CANCEL: GRANT_DENY,
  },
};

export function evaluateBillingCapabilitiesFromMap(capabilities) {
  const caps = capabilities || {};
  return {
    canViewBilling: evaluateCapabilityGrant(caps, BILLING_CAPABILITY.VIEW, 'read').allowed,
    canViewInvoices: evaluateCapabilityGrant(caps, BILLING_CAPABILITY.INVOICES, 'read').allowed,
    canViewPaymentMethods: evaluateCapabilityGrant(caps, BILLING_CAPABILITY.PAYMENT_METHODS, 'read').allowed,
    canCheckout: evaluateCapabilityGrant(caps, BILLING_CAPABILITY.CHECKOUT, 'write').allowed,
    canManageSubscription: evaluateCapabilityGrant(caps, BILLING_CAPABILITY.SUB_MANAGE, 'write').allowed,
    canCancelSubscription: evaluateCapabilityGrant(caps, BILLING_CAPABILITY.SUB_CANCEL, 'write').allowed,
  };
}
