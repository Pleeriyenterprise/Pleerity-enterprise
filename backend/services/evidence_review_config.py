"""Feature flag: FEATURE_EVIDENCE_REVIEW_V2."""

from __future__ import annotations

import os


def is_feature_evidence_review_v2() -> bool:
    return os.getenv("FEATURE_EVIDENCE_REVIEW_V2", "").strip().lower() in ("1", "true", "yes")
