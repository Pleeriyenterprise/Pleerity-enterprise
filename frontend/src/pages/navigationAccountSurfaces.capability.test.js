import fs from 'fs';
import path from 'path';

const FILES = [
  '../components/ClientPortalLayout.jsx',
  '../components/SettingsLayout.jsx',
  'ProfilePage.js',
  'JurisdictionSettingsPage.js',
  'BrandingSettingsPage.js',
  'NotificationPreferencesPage.js',
  'HelpPage.js',
  'ClientNotificationInboxPage.js',
  '../components/SupportChatWidget.js',
];

describe('navigation and account surfaces capability consumption', () => {
  it.each(FILES)('%s avoids entitlement permission decisions', (file) => {
    const src = fs.readFileSync(path.join(__dirname, file), 'utf8');
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
    expect(src).toMatch(/accountCapabilityAccess|useProfileCapabilities|useSupportCapabilities|useBrandingCapabilities|usePortalNavigationCapabilities/);
  });
});

describe('ClientPortalLayout navigation', () => {
  it('uses portal navigation capabilities', () => {
    const src = fs.readFileSync(path.join(__dirname, '../components/ClientPortalLayout.jsx'), 'utf8');
    expect(src).toMatch(/usePortalNavigationCapabilities/);
    expect(src).toMatch(/showBilling/);
  });
});
