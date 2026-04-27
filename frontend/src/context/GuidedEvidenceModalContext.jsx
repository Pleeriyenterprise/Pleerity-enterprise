import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import ComplianceEvidenceResolveModal from '../components/ComplianceEvidenceResolveModal';

const GuidedEvidenceModalContext = createContext(null);

/**
 * Single portal-wide ComplianceEvidenceResolveModal; surfaces open via {@link useGuidedEvidenceModal}.
 */
export function GuidedEvidenceModalProvider({ children }) {
  const [open, setOpen] = useState(false);
  const [propertyId, setPropertyId] = useState(null);
  const [requirement, setRequirement] = useState(null);
  const [onSubmittedCb, setOnSubmittedCb] = useState(null);
  const [initialEvidenceMode, setInitialEvidenceMode] = useState(null);

  const openGuidedEvidence = useCallback((payload) => {
    if (!payload || typeof payload !== 'object') return;
    const pid = payload.propertyId || payload.property_id;
    const req = payload.requirement;
    const rid = payload.requirementId || payload.requirement_id || req?.requirement_id;
    if (!pid || !rid) return;
    setPropertyId(String(pid));
    setRequirement(req && typeof req === 'object' && req.requirement_id ? req : { requirement_id: String(rid) });
    setOnSubmittedCb(() => (typeof payload.onSubmitted === 'function' ? payload.onSubmitted : null));
    const init = payload.initialEvidenceMode || payload.initial_evidence_mode;
    setInitialEvidenceMode(init ? String(init) : null);
    setOpen(true);
  }, []);

  const handleOpenChange = useCallback((v) => {
    setOpen(v);
    if (!v) {
      setRequirement(null);
      setOnSubmittedCb(null);
      setInitialEvidenceMode(null);
    }
  }, []);

  const value = useMemo(() => ({ openGuidedEvidence }), [openGuidedEvidence]);

  return (
    <GuidedEvidenceModalContext.Provider value={value}>
      {children}
      <ComplianceEvidenceResolveModal
        open={open}
        onOpenChange={handleOpenChange}
        propertyId={propertyId}
        requirement={requirement}
        initialEvidenceMode={initialEvidenceMode}
        onSubmitted={() => {
          onSubmittedCb?.();
        }}
      />
    </GuidedEvidenceModalContext.Provider>
  );
}

export function useGuidedEvidenceModal() {
  const ctx = useContext(GuidedEvidenceModalContext);
  if (!ctx) {
    throw new Error('useGuidedEvidenceModal must be used within GuidedEvidenceModalProvider');
  }
  return ctx;
}
