import fs from 'fs';
import path from 'path';

const PAGE = path.join(__dirname, 'DocumentsPage.js');

describe('DocumentsPage capability consumption', () => {
  it('uses runtime contract capabilities instead of entitlements', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/useDocumentCapabilities/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
    expect(src).not.toMatch(/UpgradeRequired/);
  });

  it('gates upload and write actions on capability grants', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/canUploadDocuments/);
    expect(src).toMatch(/canViewDocuments/);
    expect(src).toMatch(/canBulkZipUpload/);
    expect(src).toMatch(/canUseAdvancedExtraction/);
    expect(src).toMatch(/data-testid="upload-form-card"/);
    expect(src).toMatch(/remove-doc-btn-/);
  });
});
