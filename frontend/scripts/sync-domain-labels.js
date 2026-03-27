/**
 * Copy backend/presentation/domain_labels.json → src/domain/domain_labels.json
 * so the SPA mirror stays aligned with the canonical file. Run from repo root via npm.
 */
const fs = require('fs');
const path = require('path');

const enterpriseRoot = path.resolve(__dirname, '..', '..');
const src = path.join(enterpriseRoot, 'backend', 'presentation', 'domain_labels.json');
const dest = path.join(enterpriseRoot, 'frontend', 'src', 'domain', 'domain_labels.json');

if (!fs.existsSync(src)) {
  console.error('sync-domain-labels: missing source', src);
  process.exit(1);
}
fs.mkdirSync(path.dirname(dest), { recursive: true });
fs.copyFileSync(src, dest);
console.log('sync-domain-labels: copied to', dest);
