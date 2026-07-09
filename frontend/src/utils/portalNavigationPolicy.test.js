import { annotateNavWithLifecyclePolicy, isPathLifecycleReadOnly } from './portalNavigationPolicy';

describe('portalNavigationPolicy', () => {
  const baseModel = {
    primaryLinks: [{ path: '/today', label: 'Today' }],
    operationsGroup: null,
    secondaryItems: [{ path: '/reports', label: 'Reports' }],
  };

  it('annotates locked and read-only routes for presentation', () => {
    const annotated = annotateNavWithLifecyclePolicy(baseModel, {
      locked_routes: ['/today'],
      read_only_routes: ['/reports'],
      hidden_routes: [],
    });
    expect(annotated.primaryLinks[0].lifecycleNavHint).toBe('locked');
    expect(annotated.secondaryItems[0].lifecycleNavHint).toBe('read_only');
  });

  it('annotates de-emphasized routes from hidden_routes policy', () => {
    const annotated = annotateNavWithLifecyclePolicy(baseModel, {
      locked_routes: [],
      read_only_routes: [],
      hidden_routes: ['/reports'],
    });
    expect(annotated.secondaryItems[0].lifecycleNavHint).toBe('de_emphasized');
  });

  it('does not remove routes when policy marks them hidden', () => {
    const annotated = annotateNavWithLifecyclePolicy(baseModel, {
      hidden_routes: ['/reports'],
    });
    expect(annotated.secondaryItems).toHaveLength(1);
    expect(annotated.secondaryItems[0].path).toBe('/reports');
  });

  it('detects read-only paths for lifecycle shell hints', () => {
    expect(
      isPathLifecycleReadOnly('/documents', {
        read_only_routes: ['/documents'],
      }),
    ).toBe(true);
  });
});
