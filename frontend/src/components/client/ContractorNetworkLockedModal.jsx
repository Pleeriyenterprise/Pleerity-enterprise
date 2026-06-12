import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { LifeBuoy } from 'lucide-react';
import { useEntitlements } from '../../contexts/EntitlementsContext';
import { getFeatureDisplayInfo } from '../UpgradePrompt';
import {
  CONTRACTOR_NETWORK_FEATURE_KEY,
  CONTRACTOR_NETWORK_LOCKED_BODY,
  CONTRACTOR_NETWORK_LOCKED_TITLE,
} from '../../utils/contractorNetworkEntitlement';
import { buildSafeQueryPath, resolveClientPortalPath } from '../../utils/clientPortalNavigation';

/**
 * Upgrade/support explanation when contractor_network is required but not enabled.
 */
export function ContractorNetworkLockedModal({ open, onOpenChange }) {
  const navigate = useNavigate();
  const { entitlements } = useEntitlements();
  const info = getFeatureDisplayInfo(CONTRACTOR_NETWORK_FEATURE_KEY, entitlements);

  const close = () => onOpenChange?.(false);

  const goBilling = () => {
    navigate(buildSafeQueryPath('/settings/billing', { upgrade_to: info.requiredPlan }));
    close();
  };

  const goHelp = () => {
    navigate(resolveClientPortalPath('/help', '/help'));
    close();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="contractor-network-locked-modal">
        <DialogHeader>
          <DialogTitle>{CONTRACTOR_NETWORK_LOCKED_TITLE}</DialogTitle>
          <DialogDescription className="text-left pt-1">{CONTRACTOR_NETWORK_LOCKED_BODY}</DialogDescription>
        </DialogHeader>
        <p className="text-sm text-gray-600">
          Available on the <span className="font-medium text-midnight-blue">{info.requiredPlanName}</span> plan.
        </p>
        <DialogFooter className="flex-col gap-2 sm:flex-col sm:space-x-0">
          <Button type="button" className="w-full bg-electric-teal hover:bg-electric-teal/90" onClick={goBilling}>
            View plans in Billing
          </Button>
          <Button type="button" variant="outline" className="w-full" onClick={goHelp}>
            <LifeBuoy className="w-4 h-4 mr-2 shrink-0" aria-hidden />
            Contact support
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
