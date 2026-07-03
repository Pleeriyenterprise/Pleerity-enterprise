/**
 * Annotate navigation model with lifecycle presentation hints (ILP-3).
 * Presentation only — routes remain registered; permissions unchanged.
 */
function routeMatches(pathname, routePrefix) {
  const p = String(pathname || '');
  const r = String(routePrefix || '');
  if (!r) return false;
  if (r === '/') return p === '/';
  return p === r || p.startsWith(`${r}/`);
}

function classifyPath(path, navigationPolicy) {
  const locked = navigationPolicy?.locked_routes || [];
  const readOnly = navigationPolicy?.read_only_routes || [];
  const hidden = navigationPolicy?.hidden_routes || [];
  if (hidden.some((r) => routeMatches(path, r))) return 'de_emphasized';
  if (locked.some((r) => routeMatches(path, r))) return 'locked';
  if (readOnly.some((r) => routeMatches(path, r))) return 'read_only';
  return 'normal';
}

function annotateItem(item, navigationPolicy) {
  if (!item || item.type === 'group') return item;
  return {
    ...item,
    lifecycleNavHint: classifyPath(item.path, navigationPolicy),
  };
}

export function annotateNavWithLifecyclePolicy(navModel, navigationPolicy) {
  if (!navModel) return navModel;
  return {
    primaryLinks: (navModel.primaryLinks || []).map((item) => annotateItem(item, navigationPolicy)),
    operationsGroup: navModel.operationsGroup
      ? {
          ...navModel.operationsGroup,
          children: (navModel.operationsGroup.children || []).map((child) =>
            annotateItem(child, navigationPolicy),
          ),
        }
      : null,
    secondaryItems: (navModel.secondaryItems || []).map((item) => annotateItem(item, navigationPolicy)),
  };
}

export function isPathLifecycleLocked(pathname, navigationPolicy) {
  return classifyPath(pathname, navigationPolicy) === 'locked';
}

export function isPathLifecycleReadOnly(pathname, navigationPolicy) {
  return classifyPath(pathname, navigationPolicy) === 'read_only';
}
