import fs from 'fs';
import path from 'path';

const ROOT = path.join(__dirname, '..');

const AUTHORITY_PAGES = [
  { file: 'pages/ClientTasksPage.js', mustInclude: ['requirementsOperational', "projection: 'full'"] },
  { file: 'pages/RequirementsPage.js', mustInclude: ['requirementsOperational', "projection: 'full'"] },
  { file: 'pages/ClientCommandCenterPage.js', mustInclude: ['requirementsOperational', "projection: 'full'"] },
  { file: 'pages/ClientDashboard.js', mustInclude: ['requirementsOperational', "projection: 'full'"] },
];

const KNOWN_GAPS = [
  {
    file: 'pages/DocumentsPage.js',
    reason: 'Documents auxiliary context — list projection acceptable for document counts only',
  },
];

describe('operationalProjectionGuard', () => {
  for (const { file, mustInclude } of AUTHORITY_PAGES) {
    it(`${file} uses full operational requirements projection`, () => {
      const src = fs.readFileSync(path.join(ROOT, file), 'utf8');
      for (const needle of mustInclude) {
        expect(src).toContain(needle);
      }
      expect(src).not.toMatch(/OPERATIONAL_CACHE_KEYS\.requirements[^O]/);
    });
  }

  it('documents known lightweight list-projection surfaces', () => {
    for (const gap of KNOWN_GAPS) {
      const src = fs.readFileSync(path.join(ROOT, gap.file), 'utf8');
      expect(src).toContain('OPERATIONAL_CACHE_KEYS.requirements');
    }
  });
});
