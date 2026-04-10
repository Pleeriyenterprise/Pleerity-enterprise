import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI, parseApiError } from '../../api/client';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { useAuth } from '../../contexts/AuthContext';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import {
  Megaphone,
  RefreshCw,
  Send,
  Eye,
  History,
  FileText,
  Flag,
  Save,
  Trash2,
  CalendarClock,
} from 'lucide-react';

const MESSAGE_TYPES = [
  'INCIDENT',
  'DOWNTIME_ALERT',
  'SYSTEM_UPDATE',
  'IMPORTANT_NOTICE',
  'SERVICE_UPDATE',
  'MAINTENANCE_NOTICE',
  'ACCOUNT_ALERT',
  'GENERAL_ANNOUNCEMENT',
  'DIRECT_SUPPORT_MESSAGE',
  'FEATURE_ANNOUNCEMENT',
];

const SCOPES = [
  { value: 'ALL_CLIENTS', label: 'All clients' },
  { value: 'SELECTED', label: 'Selected / filtered' },
  { value: 'SINGLE', label: 'Single client' },
];

function canMutate(role) {
  return role === 'ROLE_OWNER' || role === 'ROLE_ADMIN';
}

export default function AdminCommunicationsPage() {
  const { user } = useAuth();
  const role = user?.role || '';
  const mutate = canMutate(role);

  const [tab, setTab] = useState('compose');

  const [messageType, setMessageType] = useState('SERVICE_UPDATE');
  const [severity, setSeverity] = useState('warning');
  const [targetScope, setTargetScope] = useState('SINGLE');
  const [clientIdSingle, setClientIdSingle] = useState('');
  const [clientIdsList, setClientIdsList] = useState('');
  const [planCodes, setPlanCodes] = useState('');
  const [subscriptionStatuses, setSubscriptionStatuses] = useState('');
  const [onboardingStatuses, setOnboardingStatuses] = useState('');
  const [whiteLabelMode, setWhiteLabelMode] = useState('');
  const [subscriptionActiveOnly, setSubscriptionActiveOnly] = useState(false);

  const [channels, setChannels] = useState(['email']);
  const [subject, setSubject] = useState('');
  const [bodyHtml, setBodyHtml] = useState('<p></p>');
  const [inAppTitle, setInAppTitle] = useState('');
  const [inAppBody, setInAppBody] = useState('');
  const [bannerTitle, setBannerTitle] = useState('');
  const [bannerMessage, setBannerMessage] = useState('');

  const [previewChecksum, setPreviewChecksum] = useState('');
  const [recipientCount, setRecipientCount] = useState(null);
  const [sampleRecipients, setSampleRecipients] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [sendLoading, setSendLoading] = useState(false);
  const [confirmSend, setConfirmSend] = useState(false);
  const [ackHighRisk, setAckHighRisk] = useState(false);

  const [draftCommunicationId, setDraftCommunicationId] = useState(null);
  const [draftName, setDraftName] = useState('');
  const [drafts, setDrafts] = useState([]);
  const [draftSaveLoading, setDraftSaveLoading] = useState(false);
  const [scheduledAtLocal, setScheduledAtLocal] = useState('');
  const [scheduleLoading, setScheduleLoading] = useState(false);

  const [templates, setTemplates] = useState([]);
  const [historyItems, setHistoryItems] = useState([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [detailId, setDetailId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [resendBusyId, setResendBusyId] = useState(null);
  const [banners, setBanners] = useState([]);
  const [includeDraftsScheduledInHistory, setIncludeDraftsScheduledInHistory] = useState(false);

  const buildTargetFilters = () => {
    const f = {};
    if (targetScope === 'SINGLE' && clientIdSingle.trim()) f.client_id = clientIdSingle.trim();
    if (targetScope === 'SELECTED' && clientIdsList.trim()) {
      f.client_ids = clientIdsList.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean);
    }
    if (planCodes.trim()) f.plan_codes = planCodes.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean);
    if (subscriptionStatuses.trim()) {
      f.subscription_statuses = subscriptionStatuses.split(/[\s,]+/).map((s) => s.trim().toUpperCase()).filter(Boolean);
    }
    if (onboardingStatuses.trim()) {
      f.onboarding_statuses = onboardingStatuses.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean);
    }
    if (whiteLabelMode) f.white_label_mode = whiteLabelMode;
    if (subscriptionActiveOnly) f.subscription_active_only = true;
    return f;
  };

  const loadTemplates = useCallback(() => {
    adminAPI.communicationsTemplates().then((r) => setTemplates(r.data.items || [])).catch(() => toast.error('Failed to load templates'));
  }, []);

  const loadHistory = useCallback(() => {
    adminAPI
      .communicationsMessages({
        limit: 50,
        include_drafts_and_scheduled: includeDraftsScheduledInHistory,
      })
      .then((r) => {
        setHistoryItems(r.data.items || []);
        setHistoryTotal(r.data.total || 0);
      })
      .catch(() => toast.error('Failed to load history'));
  }, [includeDraftsScheduledInHistory]);

  const loadDrafts = useCallback(() => {
    adminAPI.communicationsDrafts().then((r) => setDrafts(r.data.items || [])).catch(() => {});
  }, []);

  const loadBanners = useCallback(() => {
    adminAPI.communicationsBanners({}).then((r) => setBanners(r.data.items || [])).catch(() => toast.error('Failed to load banners'));
  }, []);

  useEffect(() => {
    if (tab === 'templates') loadTemplates();
    if (tab === 'history') loadHistory();
    if (tab === 'banners') loadBanners();
    if (tab === 'compose' && mutate) loadDrafts();
  }, [tab, loadTemplates, loadHistory, loadBanners, loadDrafts, mutate, includeDraftsScheduledInHistory]);

  const toggleChannel = (c) => {
    setChannels((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  };

  const runPreview = async () => {
    if (!mutate) return;
    setPreviewLoading(true);
    setPreviewChecksum('');
    setRecipientCount(null);
    setSampleRecipients([]);
    try {
      const payload = buildComposePayload();
      const { data } = await adminAPI.communicationsPreview(payload);
      setPreviewChecksum(data.preview_checksum);
      setRecipientCount(data.recipient_count);
      setSampleRecipients(data.sample_recipients || []);
      toast.success(`Preview ready: ${data.recipient_count} recipient(s)`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Preview failed');
    } finally {
      setPreviewLoading(false);
    }
  };

  const buildComposePayload = () => ({
    target_scope: targetScope,
    target_filters: buildTargetFilters(),
    message_type: messageType,
    severity,
    subject,
    body_html: bodyHtml,
    body_text: '',
    in_app_title: inAppTitle,
    in_app_body: inAppBody,
    banner_title: bannerTitle,
    banner_message: bannerMessage,
    channels,
  });

  const saveDraft = async () => {
    if (!mutate) return;
    setDraftSaveLoading(true);
    try {
      const { data } = await adminAPI.communicationsDraftUpsert({
        ...buildComposePayload(),
        draft_communication_id: draftCommunicationId || undefined,
        draft_name: draftName.trim() || undefined,
        template_id: undefined,
      });
      setDraftCommunicationId(data.communication_id);
      toast.success('Draft saved');
      loadDrafts();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Save draft failed');
    } finally {
      setDraftSaveLoading(false);
    }
  };

  const applyDraftRow = (d) => {
    setDraftCommunicationId(d.communication_id);
    setDraftName(d.draft_name || '');
    setMessageType(d.message_type || 'SERVICE_UPDATE');
    setSeverity(d.severity || 'warning');
    setTargetScope(d.target_scope || 'SINGLE');
    const tf = d.target_filters || {};
    setClientIdSingle(tf.client_id || '');
    setClientIdsList(Array.isArray(tf.client_ids) ? tf.client_ids.join(' ') : '');
    setPlanCodes(Array.isArray(tf.plan_codes) ? tf.plan_codes.join(' ') : '');
    setSubscriptionStatuses(Array.isArray(tf.subscription_statuses) ? tf.subscription_statuses.join(' ') : '');
    setOnboardingStatuses(Array.isArray(tf.onboarding_statuses) ? tf.onboarding_statuses.join(' ') : '');
    setWhiteLabelMode(tf.white_label_mode || '');
    setSubscriptionActiveOnly(Boolean(tf.subscription_active_only));
    setChannels(Array.isArray(d.channels) && d.channels.length ? d.channels : ['email']);
    setSubject(d.subject || '');
    setBodyHtml(d.body_html_snapshot || '<p></p>');
    setInAppTitle(d.in_app_title || '');
    setInAppBody(d.in_app_body || '');
    setBannerTitle(d.banner_title || '');
    setBannerMessage(d.banner_message || '');
    setPreviewChecksum('');
    setRecipientCount(null);
    setSampleRecipients([]);
    setConfirmSend(false);
    setAckHighRisk(false);
    toast.message('Draft loaded—run preview before sending.');
  };

  const deleteCurrentDraft = async () => {
    if (!mutate || !draftCommunicationId) return;
    try {
      await adminAPI.communicationsDraftDelete(draftCommunicationId);
      setDraftCommunicationId(null);
      setDraftName('');
      loadDrafts();
      toast.success('Draft deleted');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Delete failed');
    }
  };

  const runSchedule = async () => {
    if (!mutate) return;
    if (!previewChecksum || recipientCount === null) {
      toast.error('Run preview first');
      return;
    }
    if (recipientCount === 0) {
      toast.error('Zero recipients');
      return;
    }
    if (!scheduledAtLocal) {
      toast.error('Choose schedule date and time');
      return;
    }
    if ((targetScope === 'ALL_CLIENTS' || messageType === 'INCIDENT') && !ackHighRisk) {
      toast.error('Acknowledge high-risk broadcast');
      return;
    }
    const scheduled_at = new Date(scheduledAtLocal).toISOString();
    setScheduleLoading(true);
    try {
      const { data } = await adminAPI.communicationsSchedule({
        ...buildComposePayload(),
        preview_checksum: previewChecksum,
        expected_recipient_count: recipientCount,
        acknowledge_high_risk: ackHighRisk,
        scheduled_at,
      });
      toast.success(`Scheduled: ${data.communication_id}`);
      setPreviewChecksum('');
      setRecipientCount(null);
      setScheduledAtLocal('');
      setAckHighRisk(false);
      loadHistory();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Schedule failed');
    } finally {
      setScheduleLoading(false);
    }
  };

  const runSend = async () => {
    if (!mutate) return;
    if (!previewChecksum || recipientCount === null) {
      toast.error('Run preview first');
      return;
    }
    if (recipientCount === 0) {
      toast.error('Zero recipients');
      return;
    }
    if (!confirmSend) {
      toast.error('Confirm send');
      return;
    }
    if ((targetScope === 'ALL_CLIENTS' || messageType === 'INCIDENT') && !ackHighRisk) {
      toast.error('Acknowledge high-risk broadcast');
      return;
    }
    setSendLoading(true);
    try {
      const payload = {
        ...buildComposePayload(),
        preview_checksum: previewChecksum,
        expected_recipient_count: recipientCount,
        confirm_send: true,
        acknowledge_high_risk: ackHighRisk,
      };
      const { data } = await adminAPI.communicationsSend(payload);
      toast.success(`Sent: ${data.status} — ${data.communication_id}`);
      setPreviewChecksum('');
      setRecipientCount(null);
      setConfirmSend(false);
      setAckHighRisk(false);
      loadHistory();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Send failed');
    } finally {
      setSendLoading(false);
    }
  };

  const applyTemplate = (t) => {
    setMessageType(t.default_message_type || messageType);
    setSubject(t.subject_template || '');
    setBodyHtml(t.body_template || '<p></p>');
    setInAppTitle(t.in_app_title_template || '');
    setInAppBody(t.in_app_body_template || '');
    setBannerTitle('');
    setBannerMessage(t.banner_text_template || '');
    toast.message('Template applied — review and edit before preview');
  };

  const openDetail = async (id) => {
    setDetailId(id);
    try {
      const { data } = await adminAPI.communicationsMessage(id);
      setDetail(data);
    } catch {
      toast.error('Failed to load message');
    }
  };

  const resendFailedDeliveryEmail = async (deliveryId) => {
    if (!mutate || !deliveryId) return;
    setResendBusyId(deliveryId);
    try {
      const { data } = await adminAPI.communicationsResendDeliveryEmail(deliveryId);
      toast.success(data?.email_status === 'SENT' ? 'Email resent successfully' : `Resend finished: ${data?.outcome || data?.email_status || 'done'}`);
      if (detailId) await openDetail(detailId);
    } catch (e) {
      toast.error(parseApiError(e, 'Resend failed'));
    } finally {
      setResendBusyId(null);
    }
  };

  const createStandaloneBanner = async () => {
    if (!mutate) return;
    if (!bannerTitle.trim() || !bannerMessage.trim()) {
      toast.error('Title and message required');
      return;
    }
    try {
      const body = {
        title: bannerTitle,
        message: bannerMessage,
        severity,
        target_all: targetScope === 'ALL_CLIENTS',
        target_client_ids: targetScope === 'SINGLE' && clientIdSingle.trim() ? [clientIdSingle.trim()] : [],
        target_scope: targetScope === 'SELECTED' ? 'SELECTED' : null,
        target_filters: targetScope === 'SELECTED' ? buildTargetFilters() : null,
      };
      await adminAPI.communicationsBannerCreate(body);
      toast.success('Banner created');
      loadBanners();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed');
    }
  };

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-6xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Megaphone className="w-7 h-7" />
            Communications
          </h1>
          <Link to="/admin/ops" className="text-sm text-electric-teal hover:underline">
            Operations
          </Link>
        </div>

        <div className="flex gap-2 border-b border-gray-200 mb-6">
          {[
            { id: 'compose', label: 'Compose', icon: Send },
            { id: 'templates', label: 'Templates', icon: FileText },
            { id: 'history', label: 'History', icon: History },
            { id: 'banners', label: 'Banners', icon: Flag },
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
                tab === id ? 'border-electric-teal text-electric-teal' : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {tab === 'compose' && (
          <div className="space-y-4 bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
            {!mutate && (
              <div className="rounded-md bg-amber-50 text-amber-900 px-4 py-3 text-sm">
                Only Owner or Admin can preview, send, or change templates. You can use History and read-only views.
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Message type</label>
                <select
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={messageType}
                  onChange={(e) => setMessageType(e.target.value)}
                  disabled={!mutate}
                >
                  {MESSAGE_TYPES.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Severity</label>
                <select
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value)}
                  disabled={!mutate}
                >
                  {['info', 'warning', 'critical'].map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Target scope</label>
                <select
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={targetScope}
                  onChange={(e) => setTargetScope(e.target.value)}
                  disabled={!mutate}
                >
                  {SCOPES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>
              {targetScope === 'SINGLE' && (
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Client ID</label>
                  <input
                    className="w-full border rounded-md px-3 py-2 text-sm font-mono"
                    value={clientIdSingle}
                    onChange={(e) => setClientIdSingle(e.target.value)}
                    placeholder="client_..."
                    disabled={!mutate}
                  />
                </div>
              )}
              {targetScope === 'SELECTED' && (
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Client IDs (comma or space)</label>
                  <input
                    className="w-full border rounded-md px-3 py-2 text-sm font-mono"
                    value={clientIdsList}
                    onChange={(e) => setClientIdsList(e.target.value)}
                    disabled={!mutate}
                  />
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Plan codes (optional)</label>
                <input
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={planCodes}
                  onChange={(e) => setPlanCodes(e.target.value)}
                  placeholder="PLAN_1_SOLO PLAN_2_PORTFOLIO"
                  disabled={!mutate}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Subscription statuses (optional)</label>
                <input
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={subscriptionStatuses}
                  onChange={(e) => setSubscriptionStatuses(e.target.value)}
                  placeholder="ACTIVE TRIAL"
                  disabled={!mutate}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Onboarding statuses (optional)</label>
                <input
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={onboardingStatuses}
                  onChange={(e) => setOnboardingStatuses(e.target.value)}
                  disabled={!mutate}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">White-label filter</label>
                <select
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={whiteLabelMode}
                  onChange={(e) => setWhiteLabelMode(e.target.value)}
                  disabled={!mutate}
                >
                  <option value="">Any</option>
                  <option value="white_label_only">White-label only</option>
                  <option value="non_white_label_only">Non-white-label only</option>
                </select>
              </div>
              <div className="flex items-center gap-2 pt-6">
                <input
                  type="checkbox"
                  id="subActive"
                  checked={subscriptionActiveOnly}
                  onChange={(e) => setSubscriptionActiveOnly(e.target.checked)}
                  disabled={!mutate}
                />
                <label htmlFor="subActive" className="text-sm text-gray-700">
                  Active subscription only
                </label>
              </div>
            </div>

            <div>
              <span className="block text-sm font-medium text-gray-700 mb-2">Channels</span>
              <div className="flex flex-wrap gap-4">
                {['email', 'in_app', 'banner'].map((c) => (
                  <label key={c} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={channels.includes(c)}
                      onChange={() => toggleChannel(c)}
                      disabled={!mutate}
                    />
                    {c}
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email subject</label>
              <input
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                disabled={!mutate}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email body (HTML)</label>
              <textarea
                className="w-full border rounded-md px-3 py-2 text-sm font-mono min-h-[160px]"
                value={bodyHtml}
                onChange={(e) => setBodyHtml(e.target.value)}
                disabled={!mutate}
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">In-app title</label>
                <input
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={inAppTitle}
                  onChange={(e) => setInAppTitle(e.target.value)}
                  disabled={!mutate}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">In-app body</label>
                <input
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={inAppBody}
                  onChange={(e) => setInAppBody(e.target.value)}
                  disabled={!mutate}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Banner title (if banner channel)</label>
                <input
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={bannerTitle}
                  onChange={(e) => setBannerTitle(e.target.value)}
                  disabled={!mutate}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Banner message</label>
                <input
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={bannerMessage}
                  onChange={(e) => setBannerMessage(e.target.value)}
                  disabled={!mutate}
                />
              </div>
            </div>

            {recipientCount !== null && (
              <div className="rounded-md bg-slate-50 border border-slate-200 px-4 py-3 text-sm">
                <strong>Recipients:</strong> {recipientCount}
                {sampleRecipients.length > 0 && (
                  <ul className="mt-2 list-disc list-inside text-gray-600 max-h-32 overflow-auto">
                    {sampleRecipients.slice(0, 15).map((r) => (
                      <li key={r.client_id}>
                        {r.client_id} — {r.email || 'no email'} — {r.plan_name}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {mutate && (
              <div className="flex flex-wrap gap-3 items-end border-t border-gray-100 pt-4">
                <div className="min-w-[12rem]">
                  <label className="block text-xs font-medium text-gray-600 mb-1">Draft name (optional)</label>
                  <input
                    className="w-full border rounded-md px-3 py-2 text-sm"
                    value={draftName}
                    onChange={(e) => setDraftName(e.target.value)}
                    placeholder="e.g. Q1 notice"
                  />
                </div>
                <Button type="button" variant="outline" disabled={draftSaveLoading} onClick={saveDraft}>
                  <Save className="w-4 h-4 mr-2" />
                  {draftSaveLoading ? 'Saving…' : 'Save draft'}
                </Button>
                {draftCommunicationId && (
                  <Button type="button" variant="ghost" size="sm" onClick={deleteCurrentDraft}>
                    <Trash2 className="w-4 h-4 mr-2" />
                    Delete draft
                  </Button>
                )}
                <div className="min-w-[14rem]">
                  <label className="block text-xs font-medium text-gray-600 mb-1">Load draft</label>
                  <select
                    className="w-full border rounded-md px-3 py-2 text-sm"
                    value=""
                    onChange={(e) => {
                      const id = e.target.value;
                      if (!id) return;
                      const d = drafts.find((x) => x.communication_id === id);
                      if (d) applyDraftRow(d);
                      e.target.value = '';
                    }}
                  >
                    <option value="">—</option>
                    {drafts.map((d) => (
                      <option key={d.communication_id} value={d.communication_id}>
                        {(d.draft_name || d.subject || 'Draft').slice(0, 48)} ({d.communication_id})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            <div className="flex flex-wrap gap-3 items-center">
              <Button type="button" variant="outline" disabled={!mutate || previewLoading} onClick={runPreview}>
                <Eye className="w-4 h-4 mr-2" />
                {previewLoading ? 'Preview…' : 'Preview recipients'}
              </Button>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={confirmSend} onChange={(e) => setConfirmSend(e.target.checked)} disabled={!mutate} />
                I confirm sending to the shown recipient count
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={ackHighRisk}
                  onChange={(e) => setAckHighRisk(e.target.checked)}
                  disabled={!mutate}
                />
                Acknowledge broadcast / incident
              </label>
              <Button type="button" disabled={!mutate || sendLoading} onClick={runSend}>
                <Send className="w-4 h-4 mr-2" />
                {sendLoading ? 'Sending…' : 'Send'}
              </Button>
            </div>

            {mutate && recipientCount !== null && previewChecksum && (
              <div className="flex flex-wrap gap-3 items-end rounded-md bg-slate-50 border border-slate-200 px-4 py-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Schedule send (local time)</label>
                  <input
                    type="datetime-local"
                    className="border rounded-md px-3 py-2 text-sm"
                    value={scheduledAtLocal}
                    onChange={(e) => setScheduledAtLocal(e.target.value)}
                  />
                </div>
                <Button type="button" variant="outline" disabled={scheduleLoading} onClick={runSchedule}>
                  <CalendarClock className="w-4 h-4 mr-2" />
                  {scheduleLoading ? 'Scheduling…' : 'Schedule'}
                </Button>
              </div>
            )}
          </div>
        )}

        {tab === 'templates' && (
          <div className="space-y-4">
            <p className="text-sm text-gray-600">
              Variables: <code className="bg-gray-100 px-1 rounded">{'{{client_name}} {{plan_name}} {{incident_title}} {{support_email}} {{portal_link}} {{customer_reference}}'}</code>
            </p>
            <div className="grid gap-4">
              {templates.map((t) => (
                <div key={t.template_id} className="border rounded-lg p-4 bg-white shadow-sm flex justify-between gap-4">
                  <div>
                    <h3 className="font-semibold text-gray-900">{t.name}</h3>
                    <p className="text-sm text-gray-600">{t.description}</p>
                    <p className="text-xs text-gray-500 mt-1 font-mono">{t.template_id}</p>
                  </div>
                  {mutate && (
                    <Button type="button" variant="outline" size="sm" onClick={() => applyTemplate(t)}>
                      Apply to compose
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'history' && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-4">
              <Button type="button" variant="outline" size="sm" onClick={loadHistory}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={includeDraftsScheduledInHistory}
                  onChange={(e) => setIncludeDraftsScheduledInHistory(e.target.checked)}
                />
                Show drafts &amp; scheduled
              </label>
            </div>
            <p className="text-sm text-gray-500">Total: {historyTotal}</p>
            <div className="overflow-x-auto border rounded-lg">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="text-left p-2">ID</th>
                    <th className="text-left p-2">Type</th>
                    <th className="text-left p-2">Scope</th>
                    <th className="text-left p-2">Status</th>
                    <th className="text-left p-2">Recipients</th>
                    <th className="text-left p-2">When</th>
                    <th className="text-left p-2" />
                  </tr>
                </thead>
                <tbody>
                  {historyItems.map((row) => (
                    <tr key={row.communication_id} className="border-t">
                      <td className="p-2 font-mono text-xs">{row.communication_id}</td>
                      <td className="p-2">{row.message_type}</td>
                      <td className="p-2">{row.target_scope}</td>
                      <td className="p-2">{row.status}</td>
                      <td className="p-2">{row.recipient_count}</td>
                      <td className="p-2 whitespace-nowrap">{row.created_at ? String(row.created_at).slice(0, 19) : ''}</td>
                      <td className="p-2">
                        <Button type="button" variant="ghost" size="sm" onClick={() => openDetail(row.communication_id)}>
                          Details
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {detail && detailId && (
              <div className="border rounded-lg p-4 bg-slate-50 text-sm">
                <div className="flex justify-between mb-2">
                  <strong>{detail.communication_id}</strong>
                  <button type="button" className="text-electric-teal" onClick={() => { setDetail(null); setDetailId(null); }}>
                    Close
                  </button>
                </div>
                {Array.isArray(detail.deliveries) && detail.deliveries.length > 0 && (
                  <div className="mb-4 overflow-x-auto">
                    <p className="text-xs font-semibold text-gray-700 mb-2">Per-recipient delivery</p>
                    <table className="w-full text-xs border border-gray-200 bg-white rounded">
                      <thead>
                        <tr className="bg-gray-50 text-left">
                          <th className="p-2">Client</th>
                          <th className="p-2">Email</th>
                          <th className="p-2">In-app</th>
                          <th className="p-2">Attempts</th>
                          <th className="p-2" />
                        </tr>
                      </thead>
                      <tbody>
                        {detail.deliveries.map((d) => (
                          <tr key={d.delivery_id} className="border-t border-gray-100">
                            <td className="p-2 font-mono">{d.client_id}</td>
                            <td className="p-2">
                              <span className="font-medium">{d.email_status}</span>
                              {d.error_message && <span className="block text-red-600 truncate max-w-[200px]" title={d.error_message}>{d.error_message}</span>}
                              {Array.isArray(d.email_attempts) && d.email_attempts.length > 1 && (
                                <span className="block text-gray-500">Retried {d.email_attempts.length}×</span>
                              )}
                            </td>
                            <td className="p-2">{d.in_app_status}</td>
                            <td className="p-2 text-gray-600">{Array.isArray(d.email_attempts) ? d.email_attempts.length : '—'}</td>
                            <td className="p-2">
                              {mutate && d.email_status === 'FAILED' && (
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  disabled={resendBusyId === d.delivery_id}
                                  onClick={() => resendFailedDeliveryEmail(d.delivery_id)}
                                >
                                  {resendBusyId === d.delivery_id ? 'Sending…' : 'Resend email'}
                                </Button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <pre className="text-xs overflow-auto max-h-96 bg-white p-2 rounded border">{JSON.stringify(detail, null, 2)}</pre>
              </div>
            )}
          </div>
        )}

        {tab === 'banners' && (
          <div className="space-y-6">
            {mutate && (
              <div className="border rounded-lg p-4 bg-white space-y-3">
                <h3 className="font-semibold">Create standalone banner</h3>
                <p className="text-xs text-gray-500">
                  Uses current scope: all clients, single client ID, or adjust compose scope first.
                </p>
                <Button type="button" onClick={createStandaloneBanner}>
                  Create banner from fields above (title/message/severity/scope)
                </Button>
              </div>
            )}
            <Button type="button" variant="outline" size="sm" onClick={loadBanners}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
            <div className="space-y-2">
              {banners.map((b) => (
                <div key={b.banner_id} className="flex justify-between items-center border rounded-lg p-3 bg-white">
                  <div>
                    <span className="font-medium">{b.title}</span>
                    <span className={`ml-2 text-xs px-2 py-0.5 rounded ${b.active ? 'bg-green-100 text-green-800' : 'bg-gray-100'}`}>
                      {b.active ? 'active' : 'inactive'}
                    </span>
                    <p className="text-sm text-gray-600">{b.message}</p>
                    <p className="text-xs font-mono text-gray-400">{b.banner_id}</p>
                  </div>
                  {mutate && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        adminAPI
                          .communicationsBannerPatch(b.banner_id, { active: !b.active })
                          .then(() => {
                            toast.success('Updated');
                            loadBanners();
                          })
                          .catch(() => toast.error('Failed'))
                      }
                    >
                      {b.active ? 'Deactivate' : 'Activate'}
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </UnifiedAdminLayout>
  );
}
