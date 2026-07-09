# Permission Matrix Validation

**Programme:** PLATFORM-WIDE-RELEASE-READINESS-AUDIT-01  

## API capability counts

| Account | State | Capabilities |
|---------|-------|--------------|
| lere@yopmail.com | ACTIVE | 71 |
| allison@yopmail.com | SUSPENDED | 71 |

Runtime contract returns capability map for both states. SUSPENDED account uses SUSPENDED portal mode.

## Browser

- No capability leak markers on any customer page (11 routes)
- Admin routes require admin auth (browser login flow)

## Governed denial

Suspended customer pages load without exposing restricted actions via UI leak markers in harness.

## Admin roles

Governed admin actions enforced via `enforce_governed_admin_action` — verified in admin ops tests.
