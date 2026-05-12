/**
 * Shared client document file fetch / preview / download helpers.
 * Used by DocumentsPage and Property → Documents preview. Same endpoints and error shaping.
 */

/**
 * @param {import('axios').AxiosInstance} api
 * @param {string} documentId
 * @returns {Promise<Blob>}
 */
export async function fetchClientDocumentFileBlob(api, documentId) {
  if (!documentId) {
    throw new Error('Missing document');
  }
  const res = await api.get(`/documents/${encodeURIComponent(documentId)}/file`, { responseType: 'blob' });
  return new Blob([res.data], { type: res.data.type || 'application/octet-stream' });
}

/**
 * Parse axios error where `response.data` may be JSON-as-Blob (common for 4xx on blob requests).
 * @param {unknown} err
 * @param {string} fallback
 * @returns {Promise<string>}
 */
export async function resolveClientDocumentFileErrorMessage(err, fallback = 'Request failed') {
  const data = err?.response?.data;
  if (data instanceof Blob) {
    try {
      const text = await data.text();
      const parsed = JSON.parse(text);
      return (
        parsed.detail?.message ??
        (typeof parsed.detail === 'string' ? parsed.detail : parsed.detail?.msg) ??
        parsed.message ??
        fallback
      );
    } catch {
      return fallback;
    }
  }
  if (data && typeof data === 'string') return data;
  if (data?.detail && typeof data.detail === 'string') return data.detail;
  if (data?.detail?.message) return data.detail.message;
  return fallback;
}

/**
 * Open document file in a new browser tab (same behaviour as legacy Documents "View").
 * @param {import('axios').AxiosInstance} api
 * @param {string} documentId
 * @param {{ revokeDelayMs?: number }} [opts]
 */
export async function openClientDocumentFileInNewTab(api, documentId, opts = {}) {
  const { revokeDelayMs = 60000 } = opts;
  let objectUrl;
  try {
    const blob = await fetchClientDocumentFileBlob(api, documentId);
    objectUrl = URL.createObjectURL(blob);
    window.open(objectUrl, '_blank', 'noopener,noreferrer');
    setTimeout(() => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    }, revokeDelayMs);
  } catch (err) {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    const message = await resolveClientDocumentFileErrorMessage(err, 'Could not open document');
    throw Object.assign(new Error(message), { cause: err });
  }
}

/**
 * Trigger browser download for a document (same as legacy Documents download).
 * @param {import('axios').AxiosInstance} api
 * @param {{ document_id: string, file_name?: string, original_filename?: string }} doc
 * @param {{ showSuccessToast?: (msg: string) => void, onError?: (msg: string) => void }} [opts]
 */
export async function downloadClientDocumentFile(api, doc, opts = {}) {
  const { showSuccessToast, onError } = opts;
  try {
    const res = await api.get(`/documents/${encodeURIComponent(doc.document_id)}/file`, {
      params: { download: true },
      responseType: 'blob',
    });
    const blob = new Blob([res.data], { type: res.data.type || 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = doc.file_name || doc.original_filename || 'document';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showSuccessToast?.('Download started—open the file from your device when it finishes.');
  } catch (err) {
    const message = await resolveClientDocumentFileErrorMessage(err, 'Could not download document');
    if (onError) onError(message);
    else throw Object.assign(new Error(message), { cause: err });
  }
}
