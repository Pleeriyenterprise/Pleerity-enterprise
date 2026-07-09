import fs from 'fs';
import path from 'path';

const PAGE = path.join(__dirname, 'BulkUploadPage.js');

describe('BulkUploadPage capability consumption', () => {
  it('uses runtime contract bulk zip capability instead of entitlements', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/useDocumentCapabilities/);
    expect(src).toMatch(/canBulkZipUpload/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
    expect(src).not.toMatch(/UpgradeRequired/);
  });
});
