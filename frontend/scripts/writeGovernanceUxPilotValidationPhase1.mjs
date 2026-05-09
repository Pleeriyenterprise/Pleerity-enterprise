/**
 * Writes docs/audit/GOVERNANCE_UX_PILOT_VALIDATION_PHASE1.json from a fixed demo fixture.
 * Run: node scripts/writeGovernanceUxPilotValidationPhase1.mjs (from frontend/)
 */
import { mkdirSync, writeFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath, pathToFileURL } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '..');

const validationUrl = pathToFileURL(join(root, 'src', 'utils', 'governanceUxPilotValidation.js')).href;
const { buildGovernanceUxPilotValidationPhase1Snapshot, stableStringifySnapshot } = await import(validationUrl);

const demoRequirements = [
  { requirement_id: 'r1', semantic_state: 'PARTIALLY_COMPLETE', status: 'COMPLIANT' },
  { requirement_id: 'r2', semantic_state: 'OPERATIONALLY_OPEN', status: 'COMPLIANT' },
  { requirement_id: 'r3', semantic_state: 'VERIFIED_CURRENT', status: 'COMPLIANT' },
  { requirement_id: 'r4', semantic_state: 'UNKNOWN_CUSTOM', status: 'COMPLIANT' },
  { requirement_id: 'r5', evidence_authority: { semantic_state: 'DECLARATION_RECORDED' }, status: 'COMPLIANT' },
  { requirement_id: 'r6', evidence_state: 'VERIFIED_CURRENT', status: 'COMPLIANT' },
  { requirement_id: 'r7', status: 'COMPLIANT' },
];

const snap = buildGovernanceUxPilotValidationPhase1Snapshot(demoRequirements);
const outDir = join(root, 'docs', 'audit');
mkdirSync(outDir, { recursive: true });
const dest = join(outDir, 'GOVERNANCE_UX_PILOT_VALIDATION_PHASE1.json');
writeFileSync(dest, stableStringifySnapshot(snap), 'utf8');
console.log('Wrote', dest);
