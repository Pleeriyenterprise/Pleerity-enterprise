import { getBuildMetadata, exposeBuildMetadataOnWindow } from './buildMetadata';

describe('buildMetadata', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
    delete window.__CVP_BACKEND_URL;
    delete window.__CVP_BUILD_SHA;
    delete window.__CVP_DEPLOYMENT_ENV;
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('returns commit SHA, deployment env, and API base URL', () => {
    process.env.REACT_APP_BUILD_SHA = '0904b29c';
    process.env.REACT_APP_DEPLOYMENT_ENV = 'preview';
    process.env.REACT_APP_BACKEND_URL = 'https://pleerity-enterprise.onrender.com';
    window.__CVP_BACKEND_URL = 'https://pleerity-enterprise.onrender.com';

    const meta = getBuildMetadata();
    expect(meta.buildSha).toBe('0904b29c');
    expect(meta.deploymentEnv).toBe('preview');
    expect(meta.apiBaseUrl).toBe('https://pleerity-enterprise.onrender.com');
  });

  it('prefers window backend URL when set', () => {
    process.env.REACT_APP_BACKEND_URL = 'https://ignored.example.com';
    window.__CVP_BACKEND_URL = 'https://pleerity-enterprise.onrender.com';

    expect(getBuildMetadata().apiBaseUrl).toBe('https://pleerity-enterprise.onrender.com');
  });

  it('exposes metadata on window without secrets', () => {
    process.env.REACT_APP_BUILD_SHA = 'abc12345';
    process.env.REACT_APP_DEPLOYMENT_ENV = 'preview';

    exposeBuildMetadataOnWindow();

    expect(window.__CVP_BUILD_SHA).toBe('abc12345');
    expect(window.__CVP_DEPLOYMENT_ENV).toBe('preview');
  });
});
