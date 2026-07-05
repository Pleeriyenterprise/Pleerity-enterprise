import fs from 'fs';
import path from 'path';

const COMPONENT = path.join(__dirname, 'PropertyEvidenceRegistrySections.js');

describe('PropertyEvidenceRegistrySections capability consumption', () => {
  it('accepts evidence and document capability props for gated actions', () => {
    const src = fs.readFileSync(COMPONENT, 'utf8');
    expect(src).toMatch(/canViewEvidence/);
    expect(src).toMatch(/canDownloadEvidence/);
    expect(src).toMatch(/canUploadDocuments/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
  });
});
