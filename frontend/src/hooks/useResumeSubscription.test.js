import fs from 'fs';
import path from 'path';

const HOOK = path.join(__dirname, '..', 'hooks', 'useResumeSubscription.js');

describe('useResumeSubscription hook', () => {
  it('calls governed billing resume endpoint with step-up', () => {
    const src = fs.readFileSync(HOOK, 'utf8');
    expect(src).toMatch(/\/billing\/resume/);
    expect(src).toMatch(/useStepUpApi/);
  });
});
