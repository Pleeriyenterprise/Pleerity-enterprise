"""Shared Playwright helpers for GUIDED-FLOW-CLOSURE-01 operational verification."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple


def post_evidence_authority_state(post_snap: dict) -> str | None:
    auth = ((post_snap or {}).get("requirement") or {}).get("authority") or {}
    ea = auth.get("evidence_authority") if isinstance(auth.get("evidence_authority"), dict) else auth
    if not isinstance(ea, dict):
        return None
    return ea.get("state") or ea.get("semantic_state")


def checkpoint_a3_satisfied(post_snap: dict) -> bool:
    if post_snap.get("authority_changed_from_baseline"):
        return True
    return bool(post_evidence_authority_state(post_snap))


def dismiss_overlays(page) -> None:
    """Close cookie banners and modals that intercept guided submit clicks."""
    _dismiss_cookies(page)
    for _ in range(4):
        if page.get_by_test_id("view-requirement-modal").count():
            try:
                page.get_by_role("button", name="Close").first.click(timeout=2000)
            except Exception:
                page.keyboard.press("Escape")
            page.wait_for_timeout(500)
        if page.get_by_test_id("compliance-evidence-submit-summary-done").count():
            page.get_by_test_id("compliance-evidence-submit-summary-done").click()
            page.wait_for_timeout(800)
        if not page.get_by_test_id("view-requirement-modal").count():
            break


def guided_submit_evidence(page, out: dict) -> Tuple[bool, bool]:
    """
    Click Submit evidence inside resolve modal; capture HTTP 200 + body on `out`.
    Returns (summary_ok, http_ok).
    """
    dismiss_overlays(page)
    modal = page.get_by_test_id("compliance-evidence-resolve-modal")
    if not modal.count():
        return False, False
    btn = modal.get_by_role("button", name="Submit evidence")
    with page.expect_response(
        lambda r: "/compliance-evidence" in r.url and r.request.method == "POST",
        timeout=120_000,
    ) as resp_info:
        btn.click()
    resp = resp_info.value
    out.setdefault("submit_response", {})
    out["submit_response"]["http_status"] = resp.status
    try:
        body = resp.json()
        out["submit_response"]["body"] = body
        er = (body or {}).get("evidence_record") or {}
        if isinstance(er, dict) and er.get("evidence_record_id"):
            out["submit_response"]["evidence_record_id"] = er["evidence_record_id"]
    except Exception as exc:
        out["submit_response"]["parse_error"] = str(exc)
    page.wait_for_selector('[data-testid="compliance-evidence-submit-summary"]', timeout=90_000)
    summary = page.get_by_test_id("compliance-evidence-submit-summary").inner_text()
    submit_ok = any(x in summary.lower() for x in ("submission", "recorded", "saved", "review", "pending"))
    http_ok = resp.status in (200, 201)
    return submit_ok, http_ok


def resolve_guided_queue_row(
    post_snap: dict, conv_snap: dict, requirement_id: str, cer_id: Optional[str] = None
) -> dict:
    qr = conv_snap.get("queue_row_for_correlation") or post_snap.get("queue_row_for_correlation") or {}
    if str(qr.get("status") or "").upper() == "DONE":
        return qr
    needle = cer_id or ""
    for snap in (post_snap, conv_snap):
        for row in ((snap or {}).get("queue") or {}).get("recent_rows") or []:
            cid = str(row.get("correlation_id") or "")
            if requirement_id not in cid:
                continue
            if needle and needle not in cid:
                continue
            if "GUIDED_EVIDENCE" in cid and str(row.get("status") or "").upper() == "DONE":
                return row
    return qr


def classify_guided_operational_closure(
    cps: Dict[str, bool],
    ui: Dict[str, Any],
    *,
    cer_gained: bool,
    trust_risk: bool = False,
) -> Dict[str, Any]:
    """Strict closure classifier: requires A-1, A-2, A-7, A-5, A-9 together for VERIFIED_OPERATIONALLY."""
    failed = [k for k, v in cps.items() if not v]
    if trust_risk or ui.get("trust_risk"):
        return {"classification": "TRUST_RISK_PRESENT", "failed_checkpoints": failed, "reasons": ["trust_risk"]}
    if not cps.get("A-1"):
        return {"classification": "SYSTEM_OUTCOME_UNPROVEN", "failed_checkpoints": failed, "reasons": ["browser_submit_failed"]}
    if not cer_gained:
        return {"classification": "SYSTEM_OUTCOME_UNPROVEN", "failed_checkpoints": failed, "reasons": ["no_cer_delta"]}
    if not cps.get("A-7"):
        return {"classification": "ASYNC_CONVERGENCE_PARTIAL", "failed_checkpoints": failed, "reasons": ["queue_not_done"]}
    if not (cps.get("A-5") and cps.get("A-9")):
        return {"classification": "ASYNC_CONVERGENCE_PARTIAL", "failed_checkpoints": failed, "reasons": ["ui_inspect_partial"]}
    if (
        cps.get("A-1")
        and cps.get("A-2")
        and cps.get("A-3")
        and cps.get("A-7")
        and cps.get("A-5")
        and cps.get("A-9")
    ):
        return {"classification": "VERIFIED_OPERATIONALLY", "failed_checkpoints": failed, "reasons": []}
    return {"classification": "IMPLEMENTED_NOT_VERIFIED", "failed_checkpoints": failed, "reasons": ["checkpoints_incomplete"]}


def _dismiss_cookies(page) -> None:
    for label in ("Accept", "Accept all", "Got it", "OK"):
        btn = page.get_by_role("button", name=label)
        if btn.count():
            try:
                btn.first.click(timeout=2000)
            except Exception:
                pass


def wait_compliance_matrix_refresh(page, property_id: str, timeout_ms: int = 60_000) -> None:
    try:
        page.wait_for_response(
            lambda r: "compliance-detail" in r.url and r.request.method == "GET",
            timeout=timeout_ms,
        )
    except Exception:
        pass
    page.wait_for_timeout(1500)


def _wait_matrix_reflects_submission(page, req_code: str, max_wait_s: int = 45) -> None:
    row = page.locator(f'[data-req-code="{req_code}"]')
    markers = ("awaiting review", "submission on file", "pending review", "recorded")
    for _ in range(max_wait_s):
        if row.count():
            txt = row.first.inner_text().lower()
            if any(m in txt for m in markers):
                return
        page.wait_for_timeout(1000)


def _wait_intel_submission_panel(page, timeout_s: int = 90) -> bool:
    """Wait for inspect panel or CER-ready intel dialog after deeplink / matrix open."""
    for _ in range(timeout_s):
        if page.get_by_test_id("requirement-submission-inspect-panel").count() > 0:
            return True
        dlg = page.get_by_test_id("requirement-intel-dialog")
        if dlg.count() and dlg.get_attribute("data-cer-ready") == "true":
            vs = page.get_by_test_id("requirement-intel-view-submission")
            if vs.count():
                vs.click()
                page.wait_for_timeout(1200)
            if page.get_by_test_id("requirement-submission-inspect-panel").count() > 0:
                return True
        page.wait_for_timeout(1000)
    return page.get_by_test_id("requirement-submission-inspect-panel").count() > 0


def open_intel_inspect_panel(page, req_code: str, requirement_id: str) -> bool:
    dismiss_overlays(page)
    if page.get_by_test_id("compliance-evidence-resolve-modal").count():
        done = page.get_by_test_id("compliance-evidence-submit-summary-done")
        if done.count():
            done.click()
            page.wait_for_timeout(1500)
        close = page.get_by_role("button", name="Close")
        if close.count():
            close.first.click()
            page.wait_for_timeout(800)
    row = page.locator(f'[data-req-code="{req_code}"]')
    if row.count() == 0:
        row = page.locator(f'[data-testid="requirement-row-{requirement_id}"]')
    view_btn = page.locator(f'[data-testid="property-compliance-requirement-intel-{requirement_id}"]')
    matrix_btn = page.locator(f'[data-testid="compliance-matrix-action-{requirement_id}"]')
    opened = False
    if view_btn.count():
        view_btn.first.scroll_into_view_if_needed()
        view_btn.first.click()
        opened = True
    elif matrix_btn.count():
        matrix_btn.first.click()
        opened = True
    elif row.count():
        row.first.click()
        opened = True
    if not opened:
        return False
    try:
        page.wait_for_selector('[data-testid="view-requirement-modal"]', timeout=60_000)
    except Exception:
        return _wait_intel_submission_panel(page)
    return _wait_intel_submission_panel(page)


def inspect_after_guided_submit(
    page,
    *,
    frontend: str,
    property_id: str,
    req_code: str,
    requirement_id: str,
) -> bool:
    _dismiss_cookies(page)
    intel_url = (
        f"{frontend}/properties/{property_id}?open=intel&requirement_id={requirement_id}&focus=submission#compliance"
    )
    page.goto(intel_url, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(4000)
    _dismiss_cookies(page)
    try:
        page.wait_for_selector('[data-testid="view-requirement-modal"]', timeout=60_000)
    except Exception:
        pass
    for _ in range(50):
        dlg = page.get_by_test_id("requirement-intel-dialog")
        if dlg.count() and dlg.get_attribute("data-cer-ready") == "true":
            break
        if page.get_by_test_id("requirement-submission-inspect-panel").count() > 0:
            return True
        page.wait_for_timeout(400)
    if page.get_by_test_id("requirement-submission-inspect-panel").count() > 0:
        return True
    page.goto(f"{frontend}/properties/{property_id}#compliance", wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(3000)
    tab = page.get_by_role("tab", name="Compliance")
    if tab.count():
        tab.first.click()
        page.wait_for_timeout(2000)
    wait_compliance_matrix_refresh(page, property_id)
    _wait_matrix_reflects_submission(page, req_code)
    dismiss_overlays(page)
    return open_intel_inspect_panel(page, req_code, requirement_id)


def refresh_inspect_persisted(
    page,
    *,
    frontend: str,
    property_id: str,
    req_code: str,
    requirement_id: str,
) -> bool:
    intel_url = (
        f"{frontend}/properties/{property_id}?open=intel&requirement_id={requirement_id}&focus=submission#compliance"
    )
    page.goto(intel_url, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(4000)
    _dismiss_cookies(page)
    dismiss_overlays(page)
    try:
        page.wait_for_selector('[data-testid="view-requirement-modal"]', timeout=60_000)
    except Exception:
        pass
    return _wait_intel_submission_panel(page, timeout_s=90)
