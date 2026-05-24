"""
Commit-safe artifact emission for VERIFY-02 bundles.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .constants import EXECUTION_STATUS_NOT_EXECUTED, PROGRAMME_ID, PROGRAMME_REV
from .schemas import to_json_dict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArtifactWriter:
    def __init__(self, bundle_dir: Path, *, dry_run: bool = True) -> None:
        self.bundle_dir = Path(bundle_dir)
        self.dry_run = dry_run
        self.bundle_dir.mkdir(parents=True, exist_ok=True)

    def write_json(self, name: str, data: Any) -> Path:
        path = self.bundle_dir / name
        payload = to_json_dict(data) if not isinstance(data, (dict, list)) else data
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return path

    def write_not_executed_classification(
        self,
        *,
        family: str,
        slug: str,
        shared_deps: Optional[list] = None,
    ) -> Path:
        body = {
            "programme": PROGRAMME_ID,
            "programme_rev": PROGRAMME_REV,
            "family": family,
            "authoritative_verification_owner": family,
            "execution_status": EXECUTION_STATUS_NOT_EXECUTED,
            "classification": EXECUTION_STATUS_NOT_EXECUTED,
            "proof_mode": None,
            "generated_at": utc_now_iso(),
            "pilot_slug": slug,
            "shared_dependency_bundle_ids": shared_deps or [],
            "secondary_classifications": [],
            "note": "Framework scaffold only — no runtime verification executed.",
        }
        self.write_json("07_classification.json", body)
        self.write_json("classifications.json", {"classifications": [body]})
        return self.bundle_dir / "07_classification.json"

    def write_report_md(self, content: str) -> Path:
        path = self.bundle_dir / "REPORT.md"
        path.write_text(content, encoding="utf-8")
        return path

    def scaffold_readme(self, title: str) -> Path:
        text = f"# {title}\n\n**Status:** `NOT_EXECUTED`\n\nBundle populated by framework only. No runtime verification results.\n"
        return self.write_report_md(text)
