import React from 'react';
import { render, screen } from '@testing-library/react';
import DebugPanel from './DebugPanel';

const TEST_BACKEND_URL = 'https://api.example.test';

describe('DebugPanel', () => {
  beforeEach(() => {
    process.env.REACT_APP_BUILD_SHA = '0904b29c';
    process.env.REACT_APP_DEPLOYMENT_ENV = 'preview';
    window.__CVP_BACKEND_URL = TEST_BACKEND_URL;
    window.history.pushState({}, '', '/intake?debug=1');
  });

  it('shows build metadata when debug=1', () => {
    render(<DebugPanel />);
    expect(screen.getByTestId('debug-panel')).toBeInTheDocument();
    expect(screen.getByTestId('debug-build-sha')).toHaveTextContent('0904b29c');
    expect(screen.getByTestId('debug-deployment-env')).toHaveTextContent('preview');
    expect(screen.getByTestId('debug-backend-url')).toHaveTextContent(TEST_BACKEND_URL);
  });

  it('is hidden without debug=1', () => {
    window.history.pushState({}, '', '/intake');
    render(<DebugPanel />);
    expect(screen.queryByTestId('debug-panel')).not.toBeInTheDocument();
  });
});
