import React, { useCallback, useEffect, useState } from 'react';
import { clientAPI } from '../api/client';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Label } from './ui/label';
import { toast } from '../utils/portalNotifications';

/**
 * Guided "Resolve requirement" flow: loads allowed evidence modes from registry policy,
 * then submits non-document evidence via POST /client/properties/.../compliance-evidence.
 */
export default function ComplianceEvidenceResolveModal({
  open,
  onOpenChange,
  propertyId,
  requirement,
  initialEvidenceMode = null,
  onSubmitted,
}) {
  const rid = requirement?.requirement_id;
  const [loading, setLoading] = useState(false);
  const [info, setInfo] = useState(null);
  const [selectedMode, setSelectedMode] = useState('');
  const [declStatement, setDeclStatement] = useState('');
  const [declFieldsJson, setDeclFieldsJson] = useState('{}');
  const [cName, setCName] = useState('');
  const [cCompany, setCCompany] = useState('');
  const [cDate, setCDate] = useState('');
  const [cSummary, setCSummary] = useState('');
  const [inspDate, setInspDate] = useState('');
  const [inspPerson, setInspPerson] = useState('');
  const [inspAnswersJson, setInspAnswersJson] = useState('{}');
  const [inspNotes, setInspNotes] = useState('');
  const [saving, setSaving] = useState(false);

  const resetLocal = useCallback(() => {
    setInfo(null);
    setSelectedMode('');
    setDeclStatement('');
    setDeclFieldsJson('{}');
    setCName('');
    setCCompany('');
    setCDate('');
    setCSummary('');
    setInspDate('');
    setInspPerson('');
    setInspAnswersJson('{}');
    setInspNotes('');
  }, []);

  useEffect(() => {
    if (!open || !propertyId || !rid) return;
    let cancelled = false;
    setLoading(true);
    resetLocal();
    clientAPI
      .getRequirementEvidenceResolution(propertyId, rid)
      .then((res) => {
        if (!cancelled) setInfo(res.data || null);
      })
      .catch((e) => {
        if (!cancelled) {
          setInfo(null);
          toast.error(e?.response?.data?.detail || 'Could not load evidence options');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, propertyId, rid, resetLocal]);

  useEffect(() => {
    if (!open || loading || !initialEvidenceMode || !info) return;
    const im = String(initialEvidenceMode).trim().toUpperCase();
    const list = (info.allowed_evidence_modes || []).filter((m) => m && m !== 'DOCUMENT_UPLOAD');
    if (list.includes(im)) setSelectedMode(im);
  }, [open, loading, initialEvidenceMode, info]);

  const modes = (info?.allowed_evidence_modes || []).filter((m) => m && m !== 'DOCUMENT_UPLOAD');
  const cta = info?.primary_client_cta || 'Add compliance evidence';
  const modalTitle = String(info?.modal_title || 'Add compliance evidence').trim() || 'Add compliance evidence';

  const submit = async () => {
    if (!propertyId || !rid || !selectedMode) return;
    let body = { evidence_mode: selectedMode };
    try {
      if (selectedMode === 'STRUCTURED_DECLARATION') {
        const structured_fields = JSON.parse(declFieldsJson || '{}');
        body.structured_declaration = {
          declaration_statement: declStatement,
          structured_fields,
        };
      } else if (selectedMode === 'CONTRACTOR_CONFIRMATION') {
        body.contractor_confirmation = {
          contractor_name: cName,
          contractor_company: cCompany,
          completion_date: cDate,
          work_summary: cSummary,
        };
      } else if (selectedMode === 'INSPECTION_CHECKLIST') {
        const checklist_answers = JSON.parse(inspAnswersJson || '{}');
        body.inspection_checklist = {
          inspection_date: inspDate,
          checklist_answers,
          responsible_person: inspPerson,
          optional_notes: inspNotes || null,
        };
      } else {
        toast.error('Select an evidence method.');
        return;
      }
    } catch {
      toast.error('Invalid JSON in structured fields or checklist answers.');
      return;
    }
    setSaving(true);
    try {
      await clientAPI.postComplianceEvidence(propertyId, rid, body);
      toast.success('Evidence submitted for review.');
      onOpenChange(false);
      onSubmitted?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not save evidence');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="compliance-evidence-resolve-modal">
        <DialogHeader>
          <DialogTitle>{modalTitle}</DialogTitle>
          <DialogDescription>
            Choose how you want to evidence this obligation. Uploading a certificate stays on the Documents page (or
            use “Upload document” on the requirement when offered). Other methods create a compliance evidence record
            for review.
          </DialogDescription>
        </DialogHeader>
        {loading ? (
          <p className="text-sm text-gray-600">Loading allowed methods…</p>
        ) : modes.length === 0 ? (
          <p className="text-sm text-gray-600">
            This requirement only accepts a document upload. Use “Upload document” instead.
          </p>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-col gap-3">
              {modes.map((m) => {
                const row = (info?.guided_methods || []).find((x) => x.evidence_mode === m) || {};
                const label = row.label || m;
                const desc = row.description || '';
                const conf = row.typical_confidence || '';
                const ver = row.verification_note || '';
                return (
                  <button
                    key={m}
                    type="button"
                    data-testid={`guided-evidence-mode-${m}`}
                    onClick={() => setSelectedMode(m)}
                    className={`text-left rounded-lg border p-3 transition-colors ${
                      selectedMode === m ? 'border-electric-teal bg-teal-50/40 ring-1 ring-electric-teal/30' : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <p className="font-semibold text-midnight-blue text-sm">{label}</p>
                    {desc ? <p className="text-xs text-gray-600 mt-1">{desc}</p> : null}
                    {conf ? <p className="text-xs text-gray-500 mt-1">Typical confidence: {conf}</p> : null}
                    {ver ? <p className="text-xs text-gray-500 mt-1">{ver}</p> : null}
                  </button>
                );
              })}
            </div>
            {selectedMode === 'STRUCTURED_DECLARATION' ? (
              <div className="space-y-2">
                <Label>Declaration statement</Label>
                <textarea
                  className="w-full min-h-[100px] border rounded-md p-2 text-sm"
                  value={declStatement}
                  onChange={(e) => setDeclStatement(e.target.value)}
                />
                <Label>Structured fields (JSON object)</Label>
                <textarea
                  className="w-full min-h-[80px] border rounded-md p-2 font-mono text-xs"
                  value={declFieldsJson}
                  onChange={(e) => setDeclFieldsJson(e.target.value)}
                />
              </div>
            ) : null}
            {selectedMode === 'CONTRACTOR_CONFIRMATION' ? (
              <div className="space-y-2">
                <Label>Contractor name</Label>
                <input className="w-full border rounded-md p-2 text-sm" value={cName} onChange={(e) => setCName(e.target.value)} />
                <Label>Company</Label>
                <input className="w-full border rounded-md p-2 text-sm" value={cCompany} onChange={(e) => setCCompany(e.target.value)} />
                <Label>Completion date</Label>
                <input className="w-full border rounded-md p-2 text-sm" value={cDate} onChange={(e) => setCDate(e.target.value)} />
                <Label>Work / evidence summary</Label>
                <textarea className="w-full min-h-[80px] border rounded-md p-2 text-sm" value={cSummary} onChange={(e) => setCSummary(e.target.value)} />
              </div>
            ) : null}
            {selectedMode === 'INSPECTION_CHECKLIST' ? (
              <div className="space-y-2">
                <Label>Inspection date</Label>
                <input className="w-full border rounded-md p-2 text-sm" value={inspDate} onChange={(e) => setInspDate(e.target.value)} />
                <Label>Responsible person</Label>
                <input className="w-full border rounded-md p-2 text-sm" value={inspPerson} onChange={(e) => setInspPerson(e.target.value)} />
                <Label>Checklist answers (JSON object)</Label>
                <textarea
                  className="w-full min-h-[80px] border rounded-md p-2 font-mono text-xs"
                  value={inspAnswersJson}
                  onChange={(e) => setInspAnswersJson(e.target.value)}
                />
                <Label>Optional notes</Label>
                <textarea className="w-full min-h-[60px] border rounded-md p-2 text-sm" value={inspNotes} onChange={(e) => setInspNotes(e.target.value)} />
              </div>
            ) : null}
          </div>
        )}
        <DialogFooter className="gap-2 sm:gap-0">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            className="bg-electric-teal text-white"
            disabled={saving || !selectedMode || modes.length === 0}
            onClick={submit}
          >
            {saving ? 'Saving…' : 'Submit evidence'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
