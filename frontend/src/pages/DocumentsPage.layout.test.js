import fs from 'fs';
import path from 'path';

const PAGE = path.join(__dirname, 'DocumentsPage.js');

describe('DocumentsPage attention card layout', () => {
  it('wraps document action buttons and constrains filename overflow', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/flex flex-wrap items-center justify-end gap-2/);
    expect(src).toMatch(/min-w-0/);
    expect(src).toMatch(/truncate max-w-full/);
    expect(src).toMatch(/flex-col sm:flex-row/);
  });
});
