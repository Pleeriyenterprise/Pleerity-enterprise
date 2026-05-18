"""
Canonical Stripe mode governance — single authority for live vs test billing.

Set STRIPE_MODE=live|test explicitly. Keys and webhook secrets are selected by mode only:
  STRIPE_SECRET_KEY_LIVE / STRIPE_SECRET_KEY_TEST
  STRIPE_WEBHOOK_SECRET_LIVE / STRIPE_WEBHOOK_SECRET_TEST
  REACT_APP_STRIPE_PUBLISHABLE_KEY_LIVE / REACT_APP_STRIPE_PUBLISHABLE_KEY_TEST (frontend build)

Legacy STRIPE_SECRET_KEY / STRIPE_API_KEY / STRIPE_WEBHOOK_SECRET are supported only when
their prefix matches the active STRIPE_MODE (no cross-mode fallback).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

VALID_MODES = frozenset({"live", "test"})


class StripeModeConfigurationError(RuntimeError):
    """Stripe mode or env configuration is invalid or incomplete."""

    def __init__(self, message: str, *, code: str = "STRIPE_MODE_CONFIG", details: Optional[List[str]] = None):
        super().__init__(message)
        self.code = code
        self.details = details or []


class StripeObjectModeMismatchError(StripeModeConfigurationError):
    """Stripe API object belongs to the opposite mode (live vs test)."""

    def __init__(self, message: str, *, object_type: str = "object", expected_mode: str = "", actual_livemode: Optional[bool] = None):
        super().__init__(message, code="STRIPE_OBJECT_MODE_MISMATCH")
        self.object_type = object_type
        self.expected_mode = expected_mode
        self.actual_livemode = actual_livemode


def _strip(val: Optional[str]) -> str:
    return (val or "").strip()


def _legacy_secret_key() -> str:
    return _strip(os.getenv("STRIPE_SECRET_KEY") or os.getenv("STRIPE_API_KEY"))


def _secret_key_for_mode_var(mode: str) -> str:
    if mode == "live":
        return _strip(os.getenv("STRIPE_SECRET_KEY_LIVE"))
    return _strip(os.getenv("STRIPE_SECRET_KEY_TEST"))


def _publishable_key_for_mode_var(mode: str) -> str:
    if mode == "live":
        return _strip(os.getenv("REACT_APP_STRIPE_PUBLISHABLE_KEY_LIVE"))
    return _strip(os.getenv("REACT_APP_STRIPE_PUBLISHABLE_KEY_TEST"))


def _legacy_publishable_key() -> str:
    return _strip(os.getenv("REACT_APP_STRIPE_PUBLISHABLE_KEY"))


def key_prefix_mode(secret_key: str) -> Optional[str]:
    if secret_key.startswith("sk_test_"):
        return "test"
    if secret_key.startswith("sk_live_"):
        return "live"
    return None


def publishable_prefix_mode(publishable_key: str) -> Optional[str]:
    if publishable_key.startswith("pk_test_"):
        return "test"
    if publishable_key.startswith("pk_live_"):
        return "live"
    return None


def assert_secret_key_matches_mode(secret_key: str, mode: str) -> None:
    prefix_mode = key_prefix_mode(secret_key)
    if prefix_mode is None:
        raise StripeModeConfigurationError(
            f"Stripe secret key must start with sk_test_ or sk_live_ (STRIPE_MODE={mode}).",
            code="STRIPE_KEY_PREFIX_INVALID",
        )
    if prefix_mode != mode:
        raise StripeModeConfigurationError(
            f"Stripe secret key is {prefix_mode} mode but STRIPE_MODE is {mode}. "
            f"Use STRIPE_SECRET_KEY_{mode.upper()} or align STRIPE_MODE.",
            code="STRIPE_SECRET_MODE_MISMATCH",
        )


def assert_publishable_key_matches_mode(publishable_key: str, mode: str) -> None:
    prefix_mode = publishable_prefix_mode(publishable_key)
    if prefix_mode is None:
        raise StripeModeConfigurationError(
            f"Stripe publishable key must start with pk_test_ or pk_live_ (STRIPE_MODE={mode}).",
            code="STRIPE_PUBLISHABLE_PREFIX_INVALID",
        )
    if prefix_mode != mode:
        raise StripeModeConfigurationError(
            f"Stripe publishable key is {prefix_mode} mode but STRIPE_MODE is {mode}.",
            code="STRIPE_PUBLISHABLE_MODE_MISMATCH",
        )


def get_stripe_mode(*, strict: bool = False) -> str:
    """
    Return authoritative Stripe mode: 'live' or 'test'.

    When STRIPE_MODE is unset, infers from legacy secret key prefix (deprecated).
    If strict=True and STRIPE_MODE is unset, raises StripeModeConfigurationError.
    """
    explicit = _strip(os.getenv("STRIPE_MODE")).lower()
    if explicit:
        if explicit not in VALID_MODES:
            raise StripeModeConfigurationError(
                f"STRIPE_MODE must be 'live' or 'test', got {explicit!r}.",
                code="STRIPE_MODE_INVALID",
            )
        return explicit

    if strict:
        raise StripeModeConfigurationError(
            "STRIPE_MODE is not set. Set STRIPE_MODE=live or STRIPE_MODE=test.",
            code="STRIPE_MODE_MISSING",
        )

    legacy = _legacy_secret_key()
    if not legacy:
        raise StripeModeConfigurationError(
            "STRIPE_MODE is not set and no Stripe secret key is configured.",
            code="STRIPE_MODE_MISSING",
        )
    inferred = key_prefix_mode(legacy)
    if inferred is None:
        raise StripeModeConfigurationError(
            "STRIPE_MODE is not set and legacy secret key has an unrecognized prefix.",
            code="STRIPE_KEY_PREFIX_INVALID",
        )
    logger.warning(
        "STRIPE_MODE not set; inferring %s from legacy secret key prefix. "
        "Set STRIPE_MODE explicitly for production deployments.",
        inferred,
    )
    return inferred


def resolve_stripe_secret_key(*, mode: Optional[str] = None) -> str:
    """Select secret API key for the active mode. No cross-mode fallback."""
    mode = mode or get_stripe_mode()
    key = _secret_key_for_mode_var(mode)
    if key:
        assert_secret_key_matches_mode(key, mode)
        return key

    legacy = _legacy_secret_key()
    if legacy:
        assert_secret_key_matches_mode(legacy, mode)
        logger.warning(
            "Using legacy STRIPE_SECRET_KEY/STRIPE_API_KEY for %s mode. "
            "Prefer STRIPE_SECRET_KEY_%s.",
            mode,
            mode.upper(),
        )
        return legacy

    raise StripeModeConfigurationError(
        f"No Stripe secret key configured for {mode} mode. "
        f"Set STRIPE_SECRET_KEY_{mode.upper()} (or legacy key matching {mode} mode).",
        code="STRIPE_SECRET_MISSING",
    )


def resolve_webhook_secret(*, mode: Optional[str] = None) -> str:
    """Webhook signing secret for active mode only."""
    mode = mode or get_stripe_mode()
    if mode == "live":
        secret = _strip(os.getenv("STRIPE_WEBHOOK_SECRET_LIVE"))
    else:
        secret = _strip(os.getenv("STRIPE_WEBHOOK_SECRET_TEST"))

    if secret:
        return secret

    legacy = _strip(os.getenv("STRIPE_WEBHOOK_SECRET"))
    if legacy:
        logger.warning(
            "Using legacy STRIPE_WEBHOOK_SECRET for %s mode. Prefer STRIPE_WEBHOOK_SECRET_%s.",
            mode,
            mode.upper(),
        )
        return legacy

    return ""


def resolve_publishable_key(*, mode: Optional[str] = None) -> str:
    """Expected frontend publishable key for active mode (build-time env)."""
    mode = mode or get_stripe_mode()
    key = _publishable_key_for_mode_var(mode)
    if key:
        assert_publishable_key_matches_mode(key, mode)
        return key

    legacy = _legacy_publishable_key()
    if legacy:
        assert_publishable_key_matches_mode(legacy, mode)
        logger.warning(
            "Using legacy REACT_APP_STRIPE_PUBLISHABLE_KEY for %s mode. "
            "Prefer REACT_APP_STRIPE_PUBLISHABLE_KEY_%s.",
            mode,
            mode.upper(),
        )
        return legacy

    return ""


def configure_stripe_sdk(*, mode: Optional[str] = None) -> str:
    """Set global stripe.api_key from mode authority. Returns the secret key used."""
    import stripe

    key = resolve_stripe_secret_key(mode=mode)
    stripe.api_key = key
    return key


def object_livemode_to_mode(livemode: Optional[bool]) -> Optional[str]:
    if livemode is None:
        return None
    return "live" if livemode else "test"


def normalize_stripe_mode(mode: Optional[str], *, source: str = "platform") -> str:
    """
    Validate and return canonical Stripe mode ('live' | 'test').

    Use source in error messages when mode is supplied by a caller (not env).
    """
    if mode is None or not str(mode).strip():
        return get_stripe_mode()
    normalized = str(mode).strip().lower()
    if normalized not in VALID_MODES:
        logger.error(
            "Invalid Stripe mode %r from %s (expected live or test)",
            mode,
            source,
        )
        raise StripeModeConfigurationError(
            f"Invalid Stripe mode {normalized!r} from {source}; expected 'live' or 'test'.",
            code="STRIPE_MODE_INVALID",
        )
    return normalized


def assert_stripe_object_mode(
    obj: Dict[str, Any],
    *,
    expected_mode: Optional[str] = None,
    object_type: str = "object",
) -> None:
    """Reject Stripe objects from the opposite mode (coupon, price, event, etc.)."""
    platform_mode = normalize_stripe_mode(expected_mode, source="platform STRIPE_MODE")
    livemode = obj.get("livemode")
    if livemode is None:
        return
    actual = object_livemode_to_mode(bool(livemode))
    if actual and actual != platform_mode:
        raise StripeObjectModeMismatchError(
            f"Stripe {object_type} is {actual} mode but platform STRIPE_MODE is {platform_mode}.",
            object_type=object_type,
            expected_mode=platform_mode,
            actual_livemode=bool(livemode),
        )


def enhance_stripe_not_found_error(exc: Exception, *, mode: str, object_type: str) -> str:
    """Operator-safe hint when object may exist only in the opposite Stripe mode."""
    msg = getattr(exc, "user_message", None) or str(exc)
    opposite = "live" if mode == "test" else "test"
    if "No such" in msg or "resource_missing" in msg.lower():
        return (
            f"{object_type} not found in {mode} mode. "
            f"It may exist only in {opposite} mode — verify STRIPE_MODE and Dashboard mode."
        )
    return msg


def _detect_mixed_configuration(mode: str) -> Tuple[List[str], List[str]]:
    """Return (warnings, errors) for cross-mode env presence."""
    warnings: List[str] = []
    errors: List[str] = []

    live_sk = _strip(os.getenv("STRIPE_SECRET_KEY_LIVE"))
    test_sk = _strip(os.getenv("STRIPE_SECRET_KEY_TEST"))
    legacy_sk = _legacy_secret_key()

    if legacy_sk:
        legacy_mode = key_prefix_mode(legacy_sk)
        if legacy_mode and legacy_mode != mode:
            errors.append(
                f"Legacy STRIPE_SECRET_KEY is {legacy_mode} mode but STRIPE_MODE is {mode}."
            )

    active_sk = _secret_key_for_mode_var(mode) or (legacy_sk if legacy_sk and key_prefix_mode(legacy_sk) == mode else "")
    if active_sk:
        assert_mode = key_prefix_mode(active_sk)
        if assert_mode and assert_mode != mode:
            errors.append(f"Active secret key prefix ({assert_mode}) does not match STRIPE_MODE ({mode}).")

    # Opposite-mode key present is OK (staging may load both); warn if opposite key mismatches STRIPE_MODE prefix
    for label, key, m in (("LIVE", live_sk, "live"), ("TEST", test_sk, "test")):
        if not key:
            continue
        km = key_prefix_mode(key)
        if km and km != m:
            errors.append(f"STRIPE_SECRET_KEY_{label} has {km} prefix (expected sk_{m}_).")

    live_pk = _strip(os.getenv("REACT_APP_STRIPE_PUBLISHABLE_KEY_LIVE"))
    test_pk = _strip(os.getenv("REACT_APP_STRIPE_PUBLISHABLE_KEY_TEST"))
    legacy_pk = _legacy_publishable_key()

    for label, pk, m in (("LIVE", live_pk, "live"), ("TEST", test_pk, "test")):
        if not pk:
            continue
        pm = publishable_prefix_mode(pk)
        if pm and pm != m:
            errors.append(f"REACT_APP_STRIPE_PUBLISHABLE_KEY_{label} has {pm} prefix (expected pk_{m}_).")

    if legacy_pk:
        pm = publishable_prefix_mode(legacy_pk)
        if pm and pm != mode:
            warnings.append(
                f"Legacy REACT_APP_STRIPE_PUBLISHABLE_KEY is {pm} mode; active STRIPE_MODE is {mode}."
            )

    explicit_wh = _strip(os.getenv("STRIPE_WEBHOOK_SECRET"))
    if explicit_wh and not (_strip(os.getenv("STRIPE_WEBHOOK_SECRET_LIVE")) or _strip(os.getenv("STRIPE_WEBHOOK_SECRET_TEST"))):
        warnings.append(
            "STRIPE_WEBHOOK_SECRET is set without mode-specific secrets — prefer "
            "STRIPE_WEBHOOK_SECRET_LIVE and STRIPE_WEBHOOK_SECRET_TEST."
        )

    if mode == "live" and test_sk and not live_sk and not (legacy_sk and key_prefix_mode(legacy_sk) == "live"):
        warnings.append("STRIPE_MODE=live but only test secret key vars appear configured.")

    if mode == "test" and live_sk and not test_sk and not (legacy_sk and key_prefix_mode(legacy_sk) == "test"):
        warnings.append("STRIPE_MODE=test but only live secret key vars appear configured.")

    if not _strip(os.getenv("STRIPE_MODE")):
        warnings.append("STRIPE_MODE is not set — mode is inferred from legacy keys (not recommended for production).")

    return warnings, errors


def build_frontend_alignment_status(mode: str) -> Dict[str, Any]:
    pk = resolve_publishable_key(mode=mode) if _publishable_key_for_mode_var(mode) or _legacy_publishable_key() else ""
    expected_var = f"REACT_APP_STRIPE_PUBLISHABLE_KEY_{mode.upper()}"
    if pk:
        try:
            assert_publishable_key_matches_mode(pk, mode)
            status = "aligned"
        except StripeModeConfigurationError:
            status = "misaligned"
    else:
        status = "missing"
    return {
        "status": status,
        "expected_env_var": expected_var,
        "configured": bool(pk),
        "mode": mode,
    }


def build_stripe_operational_config() -> Dict[str, Any]:
    """Safe operational snapshot for admin UI — never includes secret values."""
    try:
        mode = get_stripe_mode()
        mode_authoritative = bool(_strip(os.getenv("STRIPE_MODE")))
    except StripeModeConfigurationError as e:
        return {
            "stripe_mode": "unknown",
            "mode_badge": "UNKNOWN",
            "mode_authoritative": False,
            "requirements": [],
            "warnings": [],
            "errors": [str(e)],
            "frontend_alignment": {"status": "unknown", "configured": False},
            "mixed_config_detected": True,
        }

    warnings, errors = _detect_mixed_configuration(mode)

    sk_configured = False
    try:
        resolve_stripe_secret_key(mode=mode)
        sk_configured = True
    except StripeModeConfigurationError:
        errors.append(f"Stripe secret key not configured for {mode} mode.")

    wh = resolve_webhook_secret(mode=mode)
    wh_mode_var = f"STRIPE_WEBHOOK_SECRET_{mode.upper()}"
    pk_var = f"REACT_APP_STRIPE_PUBLISHABLE_KEY_{mode.upper()}"
    sk_var = f"STRIPE_SECRET_KEY_{mode.upper()}"

    if mode == "live" and not wh:
        warnings.append("STRIPE_MODE=live but webhook signing secret is missing (STRIPE_WEBHOOK_SECRET_LIVE).")

    frontend_alignment = build_frontend_alignment_status(mode)
    if frontend_alignment["status"] == "misaligned":
        errors.append("Frontend publishable key mode does not match STRIPE_MODE.")
    elif frontend_alignment["status"] == "missing":
        warnings.append(f"{pk_var} is not set (hosted checkout may still work; alignment cannot be verified).")

    badge = "LIVE MODE" if mode == "live" else "TEST MODE"

    return {
        "stripe_mode": mode,
        "mode_badge": badge,
        "mode_authoritative": mode_authoritative,
        "requirements": [
            {"key": "STRIPE_MODE", "label": "Stripe mode (live|test)", "configured": mode_authoritative},
            {"key": sk_var, "label": f"Stripe secret API key ({mode})", "configured": sk_configured},
            {"key": wh_mode_var, "label": f"Stripe webhook signing secret ({mode})", "configured": bool(wh)},
            {
                "key": pk_var,
                "label": f"Stripe publishable key ({mode}, frontend build)",
                "configured": frontend_alignment["configured"],
                "scope": "frontend",
            },
        ],
        "warnings": warnings,
        "errors": errors,
        "mixed_config_detected": bool(errors) or any("mismatch" in w.lower() for w in warnings),
        "frontend_alignment": frontend_alignment,
        "webhook_paths": ["/api/webhook/stripe", "/api/webhooks/stripe"],
        "testing_guidance": {
            "test_mode": "Use STRIPE_MODE=test with test keys, test prices, and test webhooks in staging/dev.",
            "live_mode_coupons": "In live mode, validate discounts using 100% pilot coupons — never mix test coupons.",
            "mode_switch": "Change STRIPE_MODE and redeploy both backend and frontend with matching publishable keys.",
        },
    }


def log_startup_stripe_health() -> None:
    """Log Stripe mode and price IDs at startup; emit errors for dangerous config."""
    cfg = build_stripe_operational_config()
    mode = cfg.get("stripe_mode", "unknown")
    if mode in VALID_MODES:
        logger.info("STRIPE_MODE=%s (%s)", mode, cfg.get("mode_badge"))
    else:
        logger.error("Stripe mode unknown — billing may fail.")

    for err in cfg.get("errors") or []:
        logger.error("Stripe config: %s", err)
    for warn in cfg.get("warnings") or []:
        logger.warning("Stripe config: %s", warn)

    try:
        configure_stripe_sdk(mode=mode if mode in VALID_MODES else None)
    except StripeModeConfigurationError as e:
        logger.error("Stripe SDK not configured: %s", e)
        return

    if mode in VALID_MODES:
        from services.plan_registry import PlanCode, get_stripe_price_mappings, StripeModeMismatchError

        try:
            price_cfg = get_stripe_price_mappings(mode)
            for plan in PlanCode:
                prices = price_cfg["mappings"].get(plan.value, {})
                logger.info(
                    "Stripe price IDs plan=%s mode=%s subscription=%s onboarding=%s",
                    plan.value,
                    mode,
                    prices.get("subscription_price_id") or "(missing)",
                    prices.get("onboarding_price_id") or "(none)",
                )
        except StripeModeMismatchError as e:
            logger.error("Stripe price config for mode %s: %s", mode, e)

    env = _strip(os.getenv("ENV") or os.getenv("ENVIRONMENT")).upper()
    if mode == "test" and "PROD" in env:
        logger.warning("STRIPE_MODE=test but ENV suggests production — verify deployment target.")
