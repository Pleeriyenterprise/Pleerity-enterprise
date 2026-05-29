import fs from 'fs';
import path from 'path';

/**
 * Static guard: operational authority surfaces must not fetch requirements with list-only projection.
 * OTI-NO-LIST-PROJECTION-ON-OPERATIONAL-ROWS
 */
const ROOT = path.join(__dirname, '..');

const AUTHORITY_PAGES = [
  { file: 'pages/ClientTasksPage.js', mustInclude: ['requirementsOperational', "projection: 'full'"] },
  { file: 'pages/RequirementsPage.js', mustInclude: ['requirementsOperational', "projection: 'full'"] },
];

const KNOWN_GAPS = [
  {
    file: 'pages/ClientCommandCenterPage.js',
    reason: 'P0 RM-P0-001 — still uses OPERATIONAL_CACHE_KEYS.requirements (list default)',
  },
  {
    file: 'pages/ClientDashboard.js',
    reason: 'P0 RM-P0-001 — still uses OPERATIONAL_CACHE_KEYS.requirements (list default)',
  },
];

describe('operationalProjectionGuard', () => {
  for (const { file, mustInclude } of AUTHORITY_PAGES) {
    it(`${file} uses full operational requirements projection`, () => {
      const src = fs.readFileSync(path.join(ROOT, file), 'utf8');
      for (const needle of mustInclude) {
        expect(src).toContain(needle);
      }
      expect(src).not.toMatch(/getRequirements\(\)\.then/);
    });
  }

  it('documents known projection gaps pending P0 remediation', () => {
    for (const gap of KNOWN_GAPS) {
      const src = fs.readFileSync(path.join(ROOT, gap.file), 'utf8');
      expect(src).toContain('OPERATIONAL_CACHE_KEYS.requirements');
      expect(gap.reason).toMatch(/P0/);
    }
  });
});
