/**
 * Checkout API Utilities
 * 
 * Provides checkout validation and service info retrieval
 * before initiating Stripe payment.
 */
import client from './client';

/**
 * Validate checkout before creating Stripe session
 * 
 * @param {Object} params - Validation parameters
 * @param {string} params.service_code - Service code to validate
 * @param {Array<string>} params.selected_documents - For document packs, list of doc_keys
 * @param {string} params.variant_code - Pricing variant (standard, fast_track, printed)
 * @returns {Promise<Object>} Validation result with pricing and pack info
 */
export async function validateCheckout({ service_code, selected_documents = [], variant_code = 'standard' }) {
  try {
    const response = await client.post('/checkout/validate', {
      service_code,
      selected_documents,
      variant_code,
    });
    return response.data;
  } catch (error) {
    console.error('Checkout validation error:', error);
    throw error;
  }
}

/**
 * Get service information for checkout display
 * 
 * @param {string} serviceCode - Service code to look up
 * @returns {Promise<Object>} Service details including pack info if applicable
 */
export async function getServiceCheckoutInfo(serviceCode) {
  try {
    const response = await client.get(`/checkout/service-info/${serviceCode}`);
    return response.data;
  } catch (error) {
    console.error('Service info error:', error);
    throw error;
  }
}

/**
 * Get all document packs with inheritance info
 * 
 * @returns {Promise<Object>} Document packs list with hierarchy
 */
export async function getDocumentPacks() {
  try {
    const response = await client.get('/checkout/document-packs');
    return response.data;
  } catch (error) {
    console.error('Document packs error:', error);
    throw error;
  }
}

/**
 * Validate Stripe alignment status
 * 
 * @returns {Promise<Object>} Stripe alignment status
 */
export async function validateStripeAlignment() {
  try {
    const response = await client.get('/checkout/validate-stripe-alignment');
    return response.data;
  } catch (error) {
    console.error('Stripe alignment error:', error);
    throw error;
  }
}

/**
 * Check if a service code is a document pack
 * 
 * @param {string} serviceCode - Service code to check
 * @returns {boolean} True if document pack
 */
export function isDocumentPack(serviceCode) {
  return ['DOC_PACK_ESSENTIAL', 'DOC_PACK_PLUS', 'DOC_PACK_PRO'].includes(serviceCode);
}

/**
 * Get pack tier display name
 * 
 * @param {string} serviceCode - Pack service code
 * @returns {string} Display name
 */
export function getPackTierName(serviceCode) {
  const names = {
    'DOC_PACK_ESSENTIAL': 'Essential Pack',
    'DOC_PACK_PLUS': 'Plus Pack (Essential + Tenancy)',
    'DOC_PACK_PRO': 'Pro Pack (All Documents)',
  };
  return names[serviceCode] || serviceCode;
}

/**
 * Map variant code to display name
 * 
 * @param {string} variantCode - Variant code
 * @returns {string} Display name
 */
export function getVariantDisplayName(variantCode) {
  const names = {
    'standard': 'Standard Delivery',
    'fast_track': 'Fast Track (24h)',
    'printed': 'With Printed Copy',
  };
  return names[variantCode] || variantCode;
}

export default {
  validateCheckout,
  getServiceCheckoutInfo,
  getDocumentPacks,
  validateStripeAlignment,
  isDocumentPack,
  getPackTierName,
  getVariantDisplayName,
};
