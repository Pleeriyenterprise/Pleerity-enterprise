import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Globe2, Loader2, Save, Shield } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { toast } from '@/utils/portalNotifications';
import { clientAPI } from '../api/client';
import { PortalLoadingPanel, portalPageRoot } from '../components/client/ClientPortalPatterns';
import {
  JURISDICTION_OPTIONS,
  JURISDICTION_IMPACT_INTRO,
  JURISDICTION_SCOPE_GLOBAL,
  JURISDICTION_SCOPE_PER_PROPERTY,
  JURISDICTION_NI_NOTE,
  impactRuleExamplesForProfile,
  scoringProfileForDefaultLabel,
} from '../utils/jurisdictionComplianceCopy';

export default function JurisdictionSettingsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const fromOnboarding = searchParams.get('from') === 'onboarding';

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [justSaved, setJustSaved] = useState(false);
  const [recalcHint, setRecalcHint] = useState(null);
  const [bulkMissingLoading, setBulkMissingLoading] = useState(false);

  const [defaultJurisdiction, setDefaultJurisdiction] = useState('Scotland');
  /** Initialise narrow; load() replaces from API (never assume all regions selected). */
  const [enabledSet, setEnabledSet] = useState(() => new Set(['Scotland']));

  const profileKey = useMemo(() => scoringProfileForDefaultLabel(defaultJurisdiction), [defaultJurisdiction]);
  const examples = useMemo(() => impactRuleExamplesForProfile(profileKey), [profileKey]);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    try {
      const res = await clientAPI.getJurisdictionSettings();
      const d = res.data?.default_jurisdiction;
      const en = Array.isArray(res.data?.enabled_jurisdictions) ? res.data.enabled_jurisdictions : [];
      const filtered = en.filter((j) => JURISDICTION_OPTIONS.includes(j));
      setDefaultJurisdiction(d && JURISDICTION_OPTIONS.includes(d) ? d : filtered[0] || 'Scotland');
      const next = new Set(filtered.length ? filtered : ['Scotland']);
      setEnabledSet(next);
    } catch {
      setLoadError('Could not load jurisdiction settings. Try again or contact support.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const list = JURISDICTION_OPTIONS.filter((j) => enabledSet.has(j));
    if (list.length && !list.includes(defaultJurisdiction)) {
      setDefaultJurisdiction(list[0]);
    }
  }, [enabledSet, defaultJurisdiction]);

  const toggleEnabled = (j, checked) => {
    setEnabledSet((prev) => {
      const n = new Set(prev);
      if (checked) n.add(j);
      else n.delete(j);
      if (n.size === 0) return prev;
      if (!n.has(defaultJurisdiction)) {
        const first = JURISDICTION_OPTIONS.find((x) => n.has(x));
        if (first) setDefaultJurisdiction(first);
      }
      return n;
    });
  };

  const save = async () => {
    const enabled_jurisdictions = JURISDICTION_OPTIONS.filter((j) => enabledSet.has(j));
    if (enabled_jurisdictions.length === 0) {
      toast.error('Select at least one jurisdiction for your portfolio.');
      return;
    }
    if (!enabled_jurisdictions.includes(defaultJurisdiction)) {
      toast.error('Default jurisdiction must be one of the jurisdictions you enable.');
      return;
    }
    setSaving(true);
    setJustSaved(false);
    setRecalcHint(null);
    try {
      const res = await clientAPI.updateJurisdictionSettings({
        default_jurisdiction: defaultJurisdiction,
        enabled_jurisdictions,
      });
      const n = typeof res.data?.recalc_enqueued === 'number' ? res.data.recalc_enqueued : null;
      setRecalcHint(n);
      setJustSaved(true);
      toast.success('Compliance defaults saved', {
        description:
          n != null && n > 0
            ? `Scores and risk signals are refreshing for ${n} propert${n === 1 ? 'y' : 'ies'}. This may take a minute.`
            : 'Your jurisdiction profile is updated. Scores will use these rules on the next calculation.',
      });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      const d = err.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : 'Could not save jurisdiction settings.');
    } finally {
      setSaving(false);
    }
  };

  const applyDefaultToMissingProperties = async () => {
    const ok = window.confirm(
      'Apply your saved account default jurisdiction only to properties that have no jurisdiction on the property record? ' +
        'Properties that already have a jurisdiction set will not be changed.',
    );
    if (!ok) return;
    setBulkMissingLoading(true);
    try {
      const res = await clientAPI.applyDefaultJurisdictionToMissingProperties();
      const updated = typeof res.data?.properties_updated === 'number' ? res.data.properties_updated : 0;
      const updatedIds = Array.isArray(res.data?.updated_property_ids) ? res.data.updated_property_ids : [];
      const enq = typeof res.data?.recalc_enqueued === 'number' ? res.data.recalc_enqueued : 0;
      if (updated > 0) {
        toast.success(`Updated ${updated} propert${updated === 1 ? 'y' : 'ies'}`, {
          description:
            enq > 0
              ? `Background refresh started for ${enq} propert${enq === 1 ? 'y' : 'ies'}.`
              : (updatedIds.length ? `Updated IDs: ${updatedIds.slice(0, 5).join(', ')}${updatedIds.length > 5 ? '…' : ''}` : undefined),
        });
      } else {
        toast.message('No changes needed', {
          description: 'Every property already has a jurisdiction on record, or your default could not be applied.',
        });
      }
    } catch (err) {
      const d = err.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : 'Could not apply default to properties.');
    } finally {
      setBulkMissingLoading(false);
    }
  };

  if (loading) {
    return (
      <div className={portalPageRoot}>
        <PortalLoadingPanel message="Loading jurisdiction settings…" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className={portalPageRoot}>
        <Alert className="border-red-200 bg-red-50">
          <AlertDescription className="text-red-900">{loadError}</AlertDescription>
        </Alert>
        <Button variant="outline" className="mt-4" onClick={() => load()}>
          Try again
        </Button>
      </div>
    );
  }

  const enabledList = JURISDICTION_OPTIONS.filter((j) => enabledSet.has(j));

  return (
    <div className={`${portalPageRoot} max-w-3xl`} data-testid="jurisdiction-settings-page">
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <Button type="button" variant="ghost" size="sm" className="shrink-0 -ml-2" onClick={() => navigate(-1)}>
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back
        </Button>
      </div>

      {fromOnboarding ? (
        <Alert className="mb-6 border-electric-teal/30 bg-electric-teal/5">
          <Shield className="h-4 w-4 text-electric-teal" />
          <AlertTitle className="text-midnight-blue">Finish onboarding</AlertTitle>
          <AlertDescription className="text-gray-700 text-sm">
            You’re setting the compliance defaults for your account. Save below, then return to the dashboard to continue the
            checklist.
          </AlertDescription>
        </Alert>
      ) : null}

      {justSaved ? (
        <Alert className="mb-6 border-green-200 bg-green-50" data-testid="jurisdiction-saved-confirmation">
          <AlertTitle className="text-green-900">Compliance rules updated</AlertTitle>
          <AlertDescription className="text-green-900/90 text-sm space-y-1">
            <p>Your default jurisdiction and enabled regions are saved. Compliance scoring now uses this profile for properties without their own jurisdiction.</p>
            {recalcHint != null && recalcHint > 0 ? (
              <p className="text-green-800/90">
                Background refresh started for <strong>{recalcHint}</strong> propert{recalcHint === 1 ? 'y' : 'ies'} (scores and
                related risk signals).
              </p>
            ) : null}
          </AlertDescription>
        </Alert>
      ) : null}

      <Card className="border-2 border-electric-teal/20 shadow-md mb-6">
        <CardHeader>
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-electric-teal/15 text-electric-teal shrink-0">
              <Globe2 className="w-6 h-6" />
            </div>
            <div>
              <CardTitle className="text-xl text-midnight-blue">Jurisdiction & compliance profile</CardTitle>
              <CardDescription className="text-gray-600 mt-2 text-base leading-relaxed">
                {JURISDICTION_IMPACT_INTRO}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="rounded-lg border border-amber-100 bg-amber-50/80 p-4 text-sm text-amber-950 space-y-2">
            <p className="font-semibold text-amber-950">Scope</p>
            <p>{JURISDICTION_SCOPE_GLOBAL}</p>
            <p>{JURISDICTION_SCOPE_PER_PROPERTY}</p>
            <p className="text-xs text-amber-900/85 pt-1">{JURISDICTION_NI_NOTE}</p>
          </div>

          <div className="space-y-3">
            <Label className="text-base font-medium text-midnight-blue">Regions you operate in</Label>
            <p className="text-sm text-gray-600">Used for your portfolio context. Your default (below) must stay within this set.</p>
            <div className="grid sm:grid-cols-2 gap-3">
              {JURISDICTION_OPTIONS.map((j) => (
                <label key={j} className="flex items-center gap-2 text-sm text-gray-800 cursor-pointer">
                  <Checkbox checked={enabledSet.has(j)} onCheckedChange={(c) => toggleEnabled(j, Boolean(c))} />
                  {j}
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="default-jurisdiction" className="text-base font-medium text-midnight-blue">
              Default jurisdiction
            </Label>
            <p className="text-sm text-gray-600">
              Default jurisdiction is used for new properties and any property that does not yet have its own jurisdiction set.
              Scoring may use this value when the property record is blank; you should still confirm jurisdiction on each property
              record when you can.
            </p>
            <ul className="list-disc pl-5 text-sm text-gray-600 space-y-1 mt-2">
              <li>Saving here updates your account only — it does not backfill existing property records automatically.</li>
              <li>
                After you save, use “Apply default to missing properties only” (below) to write this default onto properties that
                have no jurisdiction on record.
              </li>
              <li>That action does not overwrite properties that already have explicit jurisdiction on the property record.</li>
            </ul>
            <Select value={defaultJurisdiction} onValueChange={setDefaultJurisdiction}>
              <SelectTrigger id="default-jurisdiction" className="max-w-md">
                <SelectValue placeholder="Choose default" />
              </SelectTrigger>
              <SelectContent>
                {enabledList.map((j) => (
                  <SelectItem key={j} value={j}>
                    {j}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-lg border border-gray-200 bg-gray-50/80 p-4">
            <p className="text-sm font-semibold text-midnight-blue mb-2">How this affects your account</p>
            <p className="text-xs text-gray-600 mb-3">
              Examples of requirement areas tracked in your score for the{' '}
              <strong>{profileKey === 'SCOTLAND' ? 'Scotland' : 'England & Wales'}</strong> profile (wording simplified; your
              actual requirements still depend on property attributes and documents):
            </p>
            <ul className="list-disc pl-5 text-sm text-gray-800 space-y-1">
              {examples.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>

          <div className="flex flex-wrap gap-3 pt-2">
            <Button
              type="button"
              className="bg-electric-teal hover:bg-electric-teal/90"
              onClick={save}
              disabled={saving}
              data-testid="jurisdiction-save-btn"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
              Save compliance defaults
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="border border-gray-200 shadow-sm" data-testid="jurisdiction-bulk-missing-card">
        <CardHeader>
          <CardTitle className="text-lg text-midnight-blue">Properties missing jurisdiction</CardTitle>
          <CardDescription className="text-gray-600 text-sm space-y-2">
            <p>
              Apply your saved account default only to properties with no jurisdiction on the property record. Properties that
              already have explicit jurisdiction saved are never overwritten.
            </p>
            <p>This does not replace reviewing each property — it only fills empty records to match your current account default.</p>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            type="button"
            variant="outline"
            onClick={applyDefaultToMissingProperties}
            disabled={bulkMissingLoading || saving}
            data-testid="jurisdiction-apply-missing-btn"
          >
            {bulkMissingLoading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
            Apply default to missing properties only
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
