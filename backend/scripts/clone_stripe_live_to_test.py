#!/usr/bin/env python3
"""
Clone Stripe products/prices from LIVE to TEST for Pleerity services intake (non-CVP).

- Reads only from Live; creates only in Test. Never deletes or modifies Live.
- Processes products whose metadata.service_code or metadata.addon_code is on the allowlist
  (AI automation, market research, compliance audits, document packs, pack add-ons).
- Skips CVP / subscription catalogue products (not on allowlist).

Env:
  STRIPE_LIVE_SECRET_KEY  (sk_live_...)
  STRIPE_TEST_SECRET_KEY  (sk_test_...)

Usage:
  python scripts/clone_stripe_live_to_test.py --dry-run
  python scripts/clone_stripe_live_to_test.py

Output:
  backend/seed/stripe_live_to_test_map.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)

import stripe

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Non-CVP service catalogue codes (must match live product metadata.service_code where set).
ALLOW_SERVICE_CODES = frozenset(
    {
        "AI_WF_BLUEPRINT",
        "AI_PROC_MAP",
        "AI_TOOL_REPORT",
        "MR_BASIC",
        "MR_ADV",
        "HMO_AUDIT",
        "FULL_AUDIT",
        "MOVE_CHECKLIST",
        "DOC_PACK_ESSENTIAL",
        "DOC_PACK_PLUS",
        "DOC_PACK_PRO",
    }
)
ALLOW_ADDON_CODES = frozenset({"FAST_TRACK", "PRINTED_COPY"})

# Explicit CVP hints — never clone even if mis-tagged.
DENY_METADATA_SNIPPETS = (
    "vault_pro",
    "cvp_subscription",
)


def _metadata_dict(md: Any) -> Dict[str, str]:
    if not md:
        return {}
    return {str(k): str(v) for k, v in dict(md).items() if v is not None and str(v) != ""}


def _clone_key(product: Any) -> Optional[str]:
    md = _metadata_dict(getattr(product, "metadata", None))
    sc = md.get("service_code")
    ac = md.get("addon_code")
    if ac and ac in ALLOW_ADDON_CODES:
        return f"addon:{ac}"
    if sc and sc in ALLOW_SERVICE_CODES:
        return f"service:{sc}"
    return None


def _should_skip_cvp(product: Any) -> bool:
    md = _metadata_dict(getattr(product, "metadata", None))
    blob = json.dumps(md, default=str).lower()
    for s in DENY_METADATA_SNIPPETS:
        if s in blob:
            return True
    name = (getattr(product, "name", None) or "").lower()
    if "compliance vault pro" in name and "pack" not in name:
        return True
    return False


def _set_stripe_key(key: str) -> None:
    stripe.api_key = key


def _price_signature(price: Any) -> Tuple:
    cur = (getattr(price, "currency", None) or "").lower()
    ua = getattr(price, "unit_amount", None)
    typ = getattr(price, "type", None) or "one_time"
    rec = getattr(price, "recurring", None)
    if rec:
        interval = getattr(rec, "interval", None) or (rec.get("interval") if isinstance(rec, dict) else None)
        interval_count = getattr(rec, "interval_count", None) or (
            rec.get("interval_count", 1) if isinstance(rec, dict) else 1
        )
        return (typ, cur, ua, "recurring", interval, interval_count)
    return (typ, cur, ua, "one_time", None, None)


def _find_matching_test_price(test_prices: List[Any], live_price: Any) -> Optional[Any]:
    sig = _price_signature(live_price)
    for tp in test_prices:
        if _price_signature(tp) == sig and getattr(tp, "active", True):
            return tp
    return None


def _list_all_prices_for_product(product_id: str) -> List[Any]:
    out: List[Any] = []
    params: Dict[str, Any] = {"product": product_id, "limit": 100}
    while True:
        page = stripe.Price.list(**params)
        data = getattr(page, "data", []) or []
        out.extend(data)
        if not getattr(page, "has_more", False):
            break
        params["starting_after"] = data[-1].id
    return out


def _index_test_products_by_clone_key() -> Dict[str, Any]:
    _set_stripe_key(os.environ["STRIPE_TEST_SECRET_KEY"])
    index: Dict[str, Any] = {}
    for p in stripe.Product.list(active=True, limit=100).auto_paging_iter():
        if _should_skip_cvp(p):
            continue
        key = _clone_key(p)
        if key and key not in index:
            index[key] = p
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description="Clone Stripe Live products/prices to Test (non-CVP services).")
    parser.add_argument("--dry-run", action="store_true", help="Log actions only; do not create in Test.")
    args = parser.parse_args()

    live_key = (os.environ.get("STRIPE_LIVE_SECRET_KEY") or "").strip()
    test_key = (os.environ.get("STRIPE_TEST_SECRET_KEY") or "").strip()

    if not live_key or not live_key.startswith("sk_live_"):
        logger.error("STRIPE_LIVE_SECRET_KEY must be set to a Live secret key (sk_live_...).")
        return 1
    if not test_key or not test_key.startswith("sk_test_"):
        logger.error("STRIPE_TEST_SECRET_KEY must be set to a Test secret key (sk_test_...).")
        return 1

    product_map: Dict[str, str] = {}
    price_map: Dict[str, str] = {}
    skipped: List[str] = []

    _set_stripe_key(live_key)
    live_products = list(stripe.Product.list(active=True, limit=100).auto_paging_iter())

    if not args.dry_run:
        test_by_key = _index_test_products_by_clone_key()
    else:
        test_by_key = {}

    for live_product in live_products:
        pid = live_product.id
        pname = live_product.name or pid

        if _should_skip_cvp(live_product):
            skipped.append(f"{pid} ({pname}): skipped (CVP-related heuristics)")
            continue

        ck = _clone_key(live_product)
        if not ck:
            skipped.append(f"{pid} ({pname}): not on service/addon allowlist (set metadata service_code or addon_code)")
            continue

        md = _metadata_dict(live_product.metadata)
        desc = getattr(live_product, "description", None) or ""

        if args.dry_run:
            logger.info("[DRY-RUN] Would ensure product %s (%s) key=%s", pid, pname, ck)
            test_product_id = "<test_product_id>"
        else:
            _set_stripe_key(test_key)
            existing = test_by_key.get(ck)
            if existing:
                test_product = existing
                logger.info("SKIP product (exists in test) %s -> %s [%s]", pid, test_product.id, ck)
            else:
                test_product = stripe.Product.create(
                    name=live_product.name,
                    description=desc[:5000] if desc else None,
                    metadata=md,
                    active=True,
                )
                test_by_key[ck] = test_product
                logger.info("LIVE_PRODUCT_ID -> TEST_PRODUCT_ID %s -> %s [%s]", pid, test_product.id, pname)

            test_product_id = test_product.id
            product_map[pid] = test_product_id

            _set_stripe_key(live_key)
            live_prices = _list_all_prices_for_product(pid)
            _set_stripe_key(test_key)
            test_prices = _list_all_prices_for_product(test_product_id)

            for lp in live_prices:
                if not getattr(lp, "active", True):
                    continue
                match = _find_matching_test_price(test_prices, lp)
                if match:
                    logger.info("SKIP price (match in test) %s -> %s", lp.id, match.id)
                    price_map[lp.id] = match.id
                    continue

                create_kw: Dict[str, Any] = {
                    "product": test_product_id,
                    "currency": lp.currency,
                    "metadata": _metadata_dict(lp.metadata),
                }
                if lp.unit_amount is not None:
                    create_kw["unit_amount"] = lp.unit_amount
                elif lp.unit_amount_decimal:
                    create_kw["unit_amount_decimal"] = lp.unit_amount_decimal
                else:
                    logger.warning("Skip price %s: no unit_amount (custom/unitary pricing not supported)", lp.id)
                    continue

                rec = getattr(lp, "recurring", None)
                if rec:
                    create_kw["recurring"] = {
                        "interval": getattr(rec, "interval", None) or rec["interval"],
                        "interval_count": getattr(rec, "interval_count", None) or rec.get("interval_count") or 1,
                    }

                np = stripe.Price.create(**create_kw)
                test_prices.append(np)
                price_map[lp.id] = np.id
                logger.info("LIVE_PRICE_ID -> TEST_PRICE_ID %s -> %s", lp.id, np.id)

        if args.dry_run:
            _set_stripe_key(live_key)
            live_prices = _list_all_prices_for_product(pid)
            for lp in live_prices:
                if getattr(lp, "active", True):
                    logger.info("[DRY-RUN] Would sync price %s (amount=%s %s)", lp.id, lp.unit_amount, lp.currency)

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "seed",
        "stripe_live_to_test_map.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "product_id_map": product_map,
        "price_id_map": price_map,
        "skipped_live_products": skipped,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    logger.info("Wrote %s", out_path)

    for s in skipped[:30]:
        logger.info("SKIPPED: %s", s)
    if len(skipped) > 30:
        logger.info("... and %d more skipped (see map file)", len(skipped) - 30)

    return 0


if __name__ == "__main__":
    sys.exit(main())
