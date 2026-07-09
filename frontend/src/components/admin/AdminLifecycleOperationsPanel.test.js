import fs from 'fs';
import path from 'path';

const panelPath = path.join(__dirname, 'AdminLifecycleOperationsPanel.jsx');
const controlPath = path.join(__dirname, '../../pages/AdminClientControlPanelPage.js');

describe('AdminLifecycleOperationsPanel', () => {
  it('exports governed lifecycle operations UI', () => {
    const src = fs.readFileSync(panelPath, 'utf8');
    expect(src).toMatch(/admin-lifecycle-operations-panel/);
    expect(src).toMatch(/lifecycle-ops-action-reconcile/);
    expect(src).toMatch(/Reconcile from Stripe/);
    expect(src).toMatch(/Refresh Runtime Contract/);
    expect(src).not.toMatch(/Set user to ACTIVE/i);
  });

  it('exports phase 2 customer operations sections', () => {
    const src = fs.readFileSync(panelPath, 'utf8');
    expect(src).toMatch(/customer-health-summary/);
    expect(src).toMatch(/authority-chain/);
    expect(src).toMatch(/operational-timeline/);
    expect(src).toMatch(/lifecycle-ops-export-bundle/);
    expect(src).toMatch(/Customer Operations Centre/);
  });
});

describe('AdminClientControlPanelPage lifecycle ops tab', () => {
  it('wires lifecycle ops tab', () => {
    const src = fs.readFileSync(controlPath, 'utf8');
    expect(src).toMatch(/lifecycle-ops/);
    expect(src).toMatch(/AdminLifecycleOperationsPanel/);
  });

  it('uses Customer ops tab label', () => {
    const src = fs.readFileSync(controlPath, 'utf8');
    expect(src).toMatch(/Customer ops/);
  });
});
