"""
Ops-only workflow activation governance report CLI (Phase 5).

Generate frozen governance bundles, diff reports, or print deterministic summaries.
No routes, no customer UI, no scheduler, no DB writes from this tool.

Run from backend directory:

  python -m scripts.workflow_activation_governance_report generate --output bundle.json
  python -m scripts.workflow_activation_governance_report generate --output bundle.json --env staging --inputs-json inputs.json
  python -m scripts.workflow_activation_governance_report diff left.json right.json
  python -m scripts.workflow_activation_governance_report diff left.json right.json --summary
  python -m scripts.workflow_activation_governance_report summary bundle.json

Optional env PLEERITY_GOVERNANCE_ENV overrides default environment_label for generate.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Activation governance report (ops, read-only).")
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="Build report and write frozen governance bundle JSON")
    g.add_argument("--output", required=True, help="Output JSON path")
    g.add_argument("--env", dest="environment_label", default=None, help="environment_label metadata")
    g.add_argument(
        "--generated-at",
        dest="generated_at_iso",
        default=None,
        help="ISO8601 timestamp (default: UTC now)",
    )
    g.add_argument(
        "--inputs-json",
        dest="inputs_json",
        default=None,
        help="Optional JSON file with keys: convergence_snapshot, transition_traces, queue_visibility, observability_summary, reliability_snapshot, stabilization_planning, families",
    )

    d = sub.add_parser("diff", help="Diff two frozen bundle JSON files")
    d.add_argument("left", type=str, help="Left bundle path")
    d.add_argument("right", type=str, help="Right bundle path")
    d.add_argument("--summary", action="store_true", help="Print deterministic diff summary lines")

    s = sub.add_parser("summary", help="Print deterministic operator summary for one bundle")
    s.add_argument("path", type=str, help="Frozen bundle JSON path")

    return p.parse_args(argv)


def _load_json(path: str) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("expected_json_object")
    return data


def _cmd_generate(args: argparse.Namespace) -> int:
    from services.workflow_activation_governance_report import build_workflow_activation_governance_report
    from services.workflow_activation_governance_report_bundle import write_workflow_activation_governance_report

    inputs: Dict[str, Any] = {}
    if args.inputs_json:
        inputs = _load_json(args.inputs_json)
    gen_at = args.generated_at_iso or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    env = (
        args.environment_label
        or os.environ.get("PLEERITY_GOVERNANCE_ENV")
        or os.environ.get("ENVIRONMENT_LABEL")
        or "unspecified"
    )
    report = build_workflow_activation_governance_report(generated_at_iso=gen_at, **{k: v for k, v in inputs.items() if k in (
        "convergence_snapshot",
        "transition_traces",
        "queue_visibility",
        "observability_summary",
        "reliability_snapshot",
        "stabilization_planning",
        "families",
    )})
    write_workflow_activation_governance_report(
        args.output,
        report,
        environment_label=env,
        generated_at_iso=gen_at,
    )
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    from services.workflow_activation_governance_report_bundle import (
        diff_frozen_governance_bundles,
        format_governance_diff_operator_summary,
        load_workflow_activation_governance_report,
    )

    left = load_workflow_activation_governance_report(args.left)
    right = load_workflow_activation_governance_report(args.right)
    diff = diff_frozen_governance_bundles(left, right)
    if args.summary:
        sys.stdout.write(format_governance_diff_operator_summary(diff))
    else:
        sys.stdout.write(json.dumps(diff, sort_keys=True, indent=2, ensure_ascii=False) + "\n")
    return 0


def _cmd_summary(args: argparse.Namespace) -> int:
    from services.workflow_activation_governance_report_bundle import (
        format_governance_report_operator_summary,
        load_workflow_activation_governance_report,
    )

    bundle = load_workflow_activation_governance_report(args.path)
    sys.stdout.write(format_governance_report_operator_summary(bundle))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    if args.command == "generate":
        return _cmd_generate(args)
    if args.command == "diff":
        return _cmd_diff(args)
    if args.command == "summary":
        return _cmd_summary(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
