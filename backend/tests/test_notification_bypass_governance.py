"""
CI governance: fail if any code bypasses NotificationOrchestrator.
Scans backend for direct email/SMS send patterns; only notification_orchestrator (and
legacy provider-holding modules) may use Postmark/Twilio or send_* entry points.
"""
import re
import pytest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATOR = BACKEND_ROOT / "services" / "notification_orchestrator.py"
EMAIL_SERVICE = BACKEND_ROOT / "services" / "email_service.py"  # Legacy; only orchestrator may call send_*
SMS_SERVICE = BACKEND_ROOT / "services" / "sms_service.py"  # Holds Twilio client; no send_sms outside orchestrator

# Files allowed to contain PostmarkClient / postmarker
ALLOWED_POSTMARK = {ORCHESTRATOR, EMAIL_SERVICE}
# Files allowed to contain twilio.rest.Client / from twilio
ALLOWED_TWILIO = {ORCHESTRATOR, SMS_SERVICE}
# No file except orchestrator may call email_service.send_* or sms_service.send_sms.
# send_otp (and verify_otp) remain in routes/sms.py for Twilio Verify flow until migrated.
ALLOWED_CALL_EMAIL_SERVICE_SEND = set()
ALLOWED_CALL_SMS_SERVICE_SEND = {BACKEND_ROOT / "routes" / "sms.py"}

# Patterns that indicate a bypass (caller or direct provider use)
PATTERN_EMAIL_SERVICE_SEND = re.compile(r"email_service\.send_")
PATTERN_SMS_SERVICE_SEND = re.compile(r"sms_service\.send_(?:sms|otp)\s*\(")
PATTERN_POSTMARK_CLIENT = re.compile(r"PostmarkClient\s*\(")
PATTERN_POSTMARKER = re.compile(r"postmarker\.core|from postmarker")
PATTERN_TWILIO_CLIENT = re.compile(r"twilio\.rest\.Client\s*\(|from twilio\.rest import Client")
PATTERN_EMails_SEND = re.compile(r"\.emails\.send\s*\(")  # postmark .emails.send( or client.emails.send(


def _collect_py_files():
    files = []
    for path in BACKEND_ROOT.rglob("*.py"):
        if "node_modules" in str(path) or "__pycache__" in str(path) or path.name.startswith("."):
            continue
        try:
            rel = path.relative_to(BACKEND_ROOT)
            if str(rel).startswith("tests" + path.anchor) or "test_" in path.name:
                continue  # Skip test files for "call" patterns so we can mock; still check test files for direct Postmark/Twilio?
            files.append(path)
        except ValueError:
            pass
    return files


def _file_contains(path: Path, pattern: re.Pattern) -> list[int]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    lines = text.splitlines()
    return [i + 1 for i, line in enumerate(lines) if pattern.search(line)]


def test_no_email_service_send_outside_orchestrator():
    """No code may call email_service.send_* except via orchestrator (no callers after migration)."""
    violations = []
    for path in _collect_py_files():
        if path in ALLOWED_CALL_EMAIL_SERVICE_SEND:
            continue
        if path.suffix != ".py":
            continue
        try:
            rel = path.relative_to(BACKEND_ROOT)
        except ValueError:
            continue
        if "test" in path.parts or path.name.startswith("test_"):
            continue
        lines = _file_contains(path, PATTERN_EMAIL_SERVICE_SEND)
        if lines:
            violations.append((str(rel), lines))
    assert not violations, (
        "Bypass: email_service.send_* must not be called outside NotificationOrchestrator. "
        "Violations: " + ", ".join(f"{f}:{ln}" for f, ln in violations)
    )


def test_no_sms_service_send_outside_orchestrator():
    """No code may call sms_service.send_sms (or send_otp) outside orchestrator after migration."""
    violations = []
    for path in _collect_py_files():
        if path in ALLOWED_CALL_SMS_SERVICE_SEND:
            continue
        if path.suffix != ".py":
            continue
        try:
            rel = path.relative_to(BACKEND_ROOT)
        except ValueError:
            continue
        if "test" in path.parts or path.name.startswith("test_"):
            continue
        lines = _file_contains(path, PATTERN_SMS_SERVICE_SEND)
        if lines:
            violations.append((str(rel), lines))
    assert not violations, (
        "Bypass: sms_service.send_sms/send_otp must not be called outside NotificationOrchestrator. "
        "Violations: " + ", ".join(f"{f}:{ln}" for f, ln in violations)
    )


def test_no_postmark_client_outside_allowed():
    """Only notification_orchestrator and email_service may use PostmarkClient."""
    violations = []
    for path in _collect_py_files():
        if path in ALLOWED_POSTMARK:
            continue
        if path.suffix != ".py":
            continue
        try:
            rel = path.relative_to(BACKEND_ROOT)
        except ValueError:
            continue
        for pattern in (PATTERN_POSTMARK_CLIENT, PATTERN_POSTMARKER):
            lines = _file_contains(path, pattern)
            if lines:
                violations.append((str(rel), pattern.pattern, lines))
    assert not violations, (
        "Bypass: PostmarkClient/postmarker only allowed in notification_orchestrator.py and email_service.py. "
        "Violations: " + ", ".join(f"{f} ({p}): {ln}" for f, p, ln in violations)
    )


def test_no_twilio_client_outside_allowed():
    """Only notification_orchestrator and sms_service may use twilio.rest.Client."""
    violations = []
    for path in _collect_py_files():
        if path in ALLOWED_TWILIO:
            continue
        if path.suffix != ".py":
            continue
        try:
            rel = path.relative_to(BACKEND_ROOT)
        except ValueError:
            continue
        lines = _file_contains(path, PATTERN_TWILIO_CLIENT)
        if lines:
            violations.append((str(rel), lines))
    assert not violations, (
        "Bypass: twilio.rest.Client only allowed in notification_orchestrator.py and sms_service.py. "
        "Violations: " + ", ".join(f"{f}:{ln}" for f, ln in violations)
    )


def test_no_direct_emails_send_outside_allowed():
    """No .emails.send( except in notification_orchestrator and email_service."""
    violations = []
    for path in _collect_py_files():
        if path in ALLOWED_POSTMARK:
            continue
        if path.suffix != ".py":
            continue
        try:
            rel = path.relative_to(BACKEND_ROOT)
        except ValueError:
            continue
        lines = _file_contains(path, PATTERN_EMails_SEND)
        if lines:
            violations.append((str(rel), lines))
    assert not violations, (
        "Bypass: .emails.send( only allowed in notification_orchestrator.py and email_service.py. "
        "Violations: " + ", ".join(f"{f}:{ln}" for f, ln in violations)
    )
