/**
 * Frontend build/deployment metadata for staging verification.
 * No secrets — commit SHA, environment label, and public API base URL only.
 */

const NOT_SET = '(not set)';

export function getBuildMetadata() {
  const buildSha = process.env.REACT_APP_BUILD_SHA || NOT_SET;
  const deploymentEnv = process.env.REACT_APP_DEPLOYMENT_ENV || process.env.NODE_ENV || NOT_SET;
  const rawApi = typeof process.env.REACT_APP_BACKEND_URL === 'string' ? process.env.REACT_APP_BACKEND_URL.trim() : '';
  const apiBaseUrl =
    (typeof window !== 'undefined' && window.__CVP_BACKEND_URL) ||
    (rawApi ? rawApi.replace(/\/$/, '') : NOT_SET);

  return { buildSha, deploymentEnv, apiBaseUrl };
}

export function exposeBuildMetadataOnWindow() {
  if (typeof window === 'undefined') return;
  const meta = getBuildMetadata();
  window.__CVP_BUILD_SHA = meta.buildSha;
  window.__CVP_DEPLOYMENT_ENV = meta.deploymentEnv;
}

export function logBuildMetadata() {
  if (typeof window === 'undefined') return;
  const meta = getBuildMetadata();
  const line = `[CVP] Build metadata: sha=${meta.buildSha} env=${meta.deploymentEnv} api=${meta.apiBaseUrl}`;
  if (process.env.NODE_ENV === 'production' && !window.__CVP_DEBUG) {
    console.debug(line);
  } else {
    console.log(line);
  }
}
