#!/usr/bin/env python3
"""
Controlled staging verification for SUPPORT_GPT_FIRST_ENABLED (anonymous public chat).

Prerequisites (staging only — do not point at production for destructive checks):
  - Backend deployed with SUPPORT_GPT_FIRST_ENABLED=true and LLM_API_KEY set
  - Staging Mongo with USER KC articles indexed + site chunks if used
  - Public POST /api/support/chat reachable (no auth required for anonymous web channel)

Usage (from repo root or backend/):
  set SUPPORT_STAGING_BASE_URL=https://your-staging-api-host   # no trailing slash
  optional: set SUPPORT_VERIFY_INSECURE_TLS=1 for self-signed staging certs
  python -m scripts.verify_support_gpt_first_staging

Output: stdout transcript + timing; redacts obvious email patterns in printed text.
Exit code: 0 if all HTTP 200; 2 if base URL missing; 1 on first HTTP error.

Failure-mode check (unset LLM on staging replica or local):
  Temporarily remove LLM_API_KEY from that environment, re-run; expect 200 and
  fallback behaviour (no crash). Restore key after.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")


def _redact(s: str) -> str:
    return _EMAIL_RE.sub("[REDACTED_EMAIL]", s or "")


def _base_url() -> str:
    raw = (os.environ.get("SUPPORT_STAGING_BASE_URL") or "").strip().rstrip("/")
    return raw


def _post_chat(base: str, message: str, conversation_id: Optional[str], ctx: Optional[Dict]) -> Tuple[int, float, Dict[str, Any]]:
    url = f"{base}/api/support/chat"
    body: Dict[str, Any] = {"message": message, "channel": "web"}
    if conversation_id:
        body["conversation_id"] = conversation_id
    if ctx is not None:
        body["conversation_context"] = ctx
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    insecure = (os.environ.get("SUPPORT_VERIFY_INSECURE_TLS") or "").strip() in ("1", "true", "yes")
    if insecure:
        import ssl

        ctx_ssl = ssl.create_default_context()
        ctx_ssl.check_hostname = False
        ctx_ssl.verify_mode = ssl.CERT_NONE
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx_ssl))
        t0 = time.perf_counter()
        with opener.open(req, timeout=120) as resp:
            elapsed = time.perf_counter() - t0
            payload = json.loads(resp.read().decode("utf-8"))
            return resp.status, elapsed, payload
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
        elapsed = time.perf_counter() - t0
        payload = json.loads(resp.read().decode("utf-8"))
        return resp.getcode() or 200, elapsed, payload


def _print_case(name: str, status: int, elapsed: float, payload: Dict[str, Any]) -> None:
    meta = payload.get("metadata") or {}
    actions = payload.get("actions")
    print("\n" + "=" * 72)
    print(f"CASE: {name}")
    print(f"HTTP {status}  latency_s={elapsed:.3f}")
    print("--- response (redacted) ---")
    print(_redact((payload.get("response") or "")[:4000]))
    print("--- metadata (subset) ---")
    subset = {
        "action": payload.get("action"),
        "legal_refusal": meta.get("legal_refusal"),
        "gpt_first": meta.get("gpt_first"),
        "gpt_first_shortcut": meta.get("gpt_first_shortcut"),
        "small_talk": meta.get("small_talk"),
        "conversational_first": meta.get("conversational_first"),
        "account_clarify": meta.get("account_clarify"),
        "retrieval_path": meta.get("retrieval_path"),
        "sources_count": len(meta.get("sources") or []) if isinstance(meta.get("sources"), list) else 0,
        "should_show_actions": meta.get("should_show_actions"),
        "safety_boundary": meta.get("safety_boundary"),
        "intent_summary": meta.get("intent_summary"),
        "confidence": meta.get("confidence"),
    }
    print(json.dumps(subset, indent=2, default=str))
    if actions:
        print("--- actions ---")
        print(json.dumps(actions, indent=2, default=str))
    print(f"conversation_id: {payload.get('conversation_id')}")


SCENARIOS: List[Tuple[str, str, Optional[str], Optional[Dict]]] = [
    ("1_legal_compliance_green", "Am I legally compliant if my score is green?", None, None),
    ("2_password", "I forgot my password", None, None),
    ("3_human_handoff", "I need to talk to a human", None, None),
    ("4a_crn_no_verify", "What is my subscription status?", None, None),
    (
        "4b_crn_with_verify",
        "My CRN is PLE-CVP-2026-TEST01 and my email is nobody@example.com — what is my status?",
        None,
        None,
    ),
    ("5_hello", "Hello", None, None),
    ("6_how_are_you", "How are you?", None, None),
    ("7_who_are_you", "Who are you?", None, None),
    ("8_need_help", "I need help", None, None),
    ("9_account_vague", "I have problems with my account", None, None),
    ("10_compliance_score_info", "How do I understand my compliance score?", None, None),
    ("11_upload_evidence", "Tell me about uploading evidence", None, None),
    ("12_cvp_pricing", "How much does Compliance Vault Pro cost?", None, None),
    ("13_what_does_pleerity_do", "What does Pleerity do?", None, None),
]


def main() -> int:
    base = _base_url()
    if not base:
        print(
            "ERROR: Set SUPPORT_STAGING_BASE_URL to your staging API origin, e.g.\n"
            "  set SUPPORT_STAGING_BASE_URL=https://api-staging.example.com",
            file=sys.stderr,
        )
        return 2

    print(f"Target: {base}")
    print("Ensure staging has SUPPORT_GPT_FIRST_ENABLED=true and LLM_API_KEY for full GPT-first path.")
    print("Each scenario uses a new conversation (no prior thread).")
    for name, msg, _, _ in SCENARIOS:
        try:
            status, elapsed, payload = _post_chat(base, msg, None, None)
        except urllib.error.HTTPError as e:
            print(f"\nHTTPError {e.code} for {name}: {e.read()[:500]!r}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"\nRequest failed for {name}: {e}", file=sys.stderr)
            return 1
        if status != 200:
            print(f"\nNon-200 for {name}: {status}", file=sys.stderr)
            return 1
        _print_case(name, status, elapsed, payload)
    print("\n" + "=" * 72)
    print("Done. Review responses for legal refusal, shortcuts, grounding, and tone.")
    print("For LLM-off failure mode: repeat on an env without LLM_API_KEY; expect 200 + fallback copy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
