/**
 * Dev-only: proxy /api to local backend when REACT_APP_BACKEND_URL is unset.
 * Keeps CRA dev server + Playwright OPS-VERIFY runs working against :8000.
 */
const { createProxyMiddleware } = require('http-proxy-middleware');

const target =
  (process.env.REACT_APP_BACKEND_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

module.exports = function setupProxy(app) {
  app.use(
    '/api',
    createProxyMiddleware({
      target,
      changeOrigin: true,
    }),
  );
};
