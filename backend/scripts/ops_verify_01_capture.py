"""
OPS-VERIFY-01 read-only staging capture (baseline / post-submit / convergence).

Observational only — does not mutate authority, workflow, recalc, or fanout systems.

  python -m scripts.ops_verify_01_capture --init-bundle --slug-suffix 6fd5ac4c_d35a58ae
  python -m scripts.ops_verify_01_capture --phase baseline --requirement-id RID ...
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ops_verify_01_manifest import (  # noqa: E402
    DEFAULT_CLIENT_ID,
    DEFAULT_PROPERTY_ID,
    DEFAULT_SLUG,
    assess_bundle_completeness,
    bundle_dir,
    bundle_paths,
    init_bundle,
    read_json_if_exists,
    write_json,
)
from scripts.ops_verify_01_snapshot import (  # noqa: E402
    capture_baseline,
    capture_convergence,
    capture_post_action,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="OPS-VERIFY-01 read-only capture")
    p.add_argument("--slug-suffix", default=DEFAULT_SLUG)
    p.add_argument("--out-dir", default="docs/audit")
    p.add_argument("--client-id", default=DEFAULT_CLIENT_ID)
    p.add_argument("--property-id", default=DEFAULT_PROPERTY_ID)
    p.add_argument("--requirement-id", default="")
    p.add_argument("--correlation-id", default="")
    p.add_argument("--phase", choices=("baseline", "post-submit", "convergence", "all"), default="baseline")
    p.add_argument("--init-bundle", action="store_true", help="Create manifest + ui_notes template only")
    p.add_argument("--verifier", default="")
    p.add_argument("--overwrite-init", action="store_true")
    return p.parse_args()


async def _get_db():
    from database import database

    if database.db is None:
        await database.connect()
    return database.get_db()


async def _run_capture(args: argparse.Namespace) -> Dict[str, Any]:
    audit_root = Path(args.out_dir)
    if not audit_root.is_absolute():
        audit_root = ROOT / audit_root
    slug = args.slug_suffix.strip()
    bundle = bundle_dir(audit_root, slug)
    paths = bundle_paths(bundle, slug)

    if args.init_bundle:
        init_bundle(
            audit_root,
            slug=slug,
            client_id=args.client_id,
            property_id=args.property_id,
            verifier=args.verifier,
            overwrite=args.overwrite_init,
        )
        completeness = assess_bundle_completeness(bundle, slug)
        return {"init_bundle": str(bundle), "completeness": completeness}

    rid = (args.requirement_id or "").strip()
    if not rid:
        raise SystemExit("--requirement-id is required for capture phases (not --init-bundle)")

    db = await _get_db()
    cid, pid = args.client_id, args.property_id
    bundle.mkdir(parents=True, exist_ok=True)
    if not paths["manifest"].is_file():
        init_bundle(audit_root, slug=slug, client_id=cid, property_id=pid, verifier=args.verifier)

    manifest = read_json_if_exists(paths["manifest"]) or {}
    rids = list(manifest.get("requirement_ids") or [])
    if rid not in rids:
        rids.append(rid)
    manifest["requirement_ids"] = rids
    manifest["client_id"] = cid
    manifest["property_id"] = pid
    manifest["slug"] = slug
    write_json(paths["manifest"], manifest)

    baseline_existing = read_json_if_exists(paths["baseline"])
    post_existing = read_json_if_exists(paths["post_submit"])
    correlation = (args.correlation_id or "").strip() or None

    outputs: Dict[str, Any] = {"bundle": str(bundle), "phase": args.phase}

    if args.phase in ("baseline", "all"):
        snap = await capture_baseline(db, client_id=cid, property_id=pid, requirement_id=rid)
        write_json(paths["baseline"], snap)
        outputs["baseline"] = str(paths["baseline"])
        baseline_existing = snap

    if args.phase in ("post-submit", "all"):
        snap = await capture_post_action(
            db,
            client_id=cid,
            property_id=pid,
            requirement_id=rid,
            baseline=baseline_existing,
            correlation_id=correlation,
        )
        write_json(paths["post_submit"], snap)
        outputs["post_submit"] = str(paths["post_submit"])
        post_existing = snap

    if args.phase in ("convergence", "all"):
        snap = await capture_convergence(
            db,
            client_id=cid,
            property_id=pid,
            requirement_id=rid,
            baseline=baseline_existing,
            post_submit=post_existing,
            correlation_id=correlation,
        )
        write_json(paths["convergence"], snap)
        outputs["convergence"] = str(paths["convergence"])

    outputs["completeness"] = assess_bundle_completeness(bundle, slug)
    return outputs


def main() -> None:
    args = _parse_args()
    if args.init_bundle and args.phase != "baseline":
        pass
    if not args.init_bundle and not os.environ.get("MONGO_URL") and not os.environ.get("DATABASE_URL"):
        print(
            "WARN: MONGO_URL/DATABASE_URL not set; capture may fail unless env is loaded.",
            file=sys.stderr,
        )
    result = asyncio.run(_run_capture(args))
    import json

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
