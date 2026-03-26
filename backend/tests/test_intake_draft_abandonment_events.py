import asyncio
from unittest.mock import AsyncMock

from services import intake_draft_service as svc


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, _limit):
        return list(self._rows)


class _FakeIntakeDrafts:
    def __init__(self, stale_rows=None):
        self.update_one = AsyncMock()
        self.find = lambda *_args, **_kwargs: _Cursor(stale_rows or [])


class _FakeLeads:
    def __init__(self, side_effect):
        self.find_one = AsyncMock(side_effect=side_effect)


class _FakeDb:
    def __init__(self, *, lead_find_side_effect, stale_rows=None):
        self.intake_drafts = _FakeIntakeDrafts(stale_rows=stale_rows)
        self.leads = _FakeLeads(lead_find_side_effect)


def test_mark_draft_abandoned_emits_checkout_abandoned_event(monkeypatch):
    draft_before = {
        "draft_id": "DRAFT-1",
        "service_code": "DOC_PACK_ESSENTIAL",
        "client_identity": {"email": "lead@example.com"},
    }
    draft_after = {**draft_before, "status": svc.DraftStatus.ABANDONED}
    monkeypatch.setattr(svc, "get_draft", AsyncMock(side_effect=[draft_before, draft_after]))

    fake_db = _FakeDb(
        lead_find_side_effect=[{"lead_id": "LEAD-1"}],
    )
    monkeypatch.setattr(svc.database, "get_db", lambda: fake_db)

    import services.lead_automation_service as las
    rec = AsyncMock()
    eval_rules = AsyncMock()
    monkeypatch.setattr(las, "record_event", rec)
    monkeypatch.setattr(las, "evaluate_automation_rules", eval_rules)

    result = asyncio.run(svc.mark_draft_abandoned("DRAFT-1"))

    assert result["status"] == svc.DraftStatus.ABANDONED
    fake_db.intake_drafts.update_one.assert_awaited()
    rec.assert_awaited_once()
    eval_rules.assert_awaited_once_with("LEAD-1", las.EVENT_CHECKOUT_ABANDONED)


def test_mark_draft_abandoned_uses_email_fallback_for_lead_resolution(monkeypatch):
    draft_before = {
        "draft_id": "DRAFT-2",
        "service_code": "HMO_AUDIT",
        "client_identity": {"email": "fallback@example.com"},
    }
    draft_after = {**draft_before, "status": svc.DraftStatus.ABANDONED}
    monkeypatch.setattr(svc, "get_draft", AsyncMock(side_effect=[draft_before, draft_after]))

    fake_db = _FakeDb(
        # 1) lookup by intake_draft_id -> none, 2) fallback by email -> lead
        lead_find_side_effect=[None, {"lead_id": "LEAD-FALLBACK"}],
    )
    monkeypatch.setattr(svc.database, "get_db", lambda: fake_db)

    import services.lead_automation_service as las
    rec = AsyncMock()
    eval_rules = AsyncMock()
    monkeypatch.setattr(las, "record_event", rec)
    monkeypatch.setattr(las, "evaluate_automation_rules", eval_rules)

    asyncio.run(svc.mark_draft_abandoned("DRAFT-2"))

    assert fake_db.leads.find_one.await_count == 2
    eval_rules.assert_awaited_once_with("LEAD-FALLBACK", las.EVENT_CHECKOUT_ABANDONED)


def test_cleanup_abandoned_drafts_calls_mark_and_appends_auto_audit(monkeypatch):
    stale_rows = [{"draft_id": "D-A"}, {"draft_id": "D-B"}]
    fake_db = _FakeDb(lead_find_side_effect=[None], stale_rows=stale_rows)
    monkeypatch.setattr(svc.database, "get_db", lambda: fake_db)
    monkeypatch.setattr(svc, "mark_draft_abandoned", AsyncMock())

    modified = asyncio.run(svc.cleanup_abandoned_drafts(hours_old=24))

    assert modified == 2
    assert svc.mark_draft_abandoned.await_count == 2
    assert fake_db.intake_drafts.update_one.await_count == 2
