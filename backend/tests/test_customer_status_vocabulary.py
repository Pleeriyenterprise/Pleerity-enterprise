"""PR-1A — customer status vocabulary mirror parity with CUSTOMER_STATUS_VOCABULARY.json."""
from __future__ import annotations

import json
from pathlib import Path

from services import customer_status_vocabulary as csv

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VOCAB_JSON = _REPO_ROOT / "docs" / "governance" / "CUSTOMER_STATUS_VOCABULARY.json"


def _load_vocab_json() -> dict:
    with _VOCAB_JSON.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_vocab_json_exists():
    assert _VOCAB_JSON.is_file()


def test_version_and_effective_date_match_json():
    data = _load_vocab_json()
    assert csv.VOCABULARY_VERSION == data["version"]
    assert csv.VOCABULARY_EFFECTIVE_DATE == data["effective_date"]


def test_primary_status_keys_match_json():
    data = _load_vocab_json()
    json_keys = [s["key"] for s in data["primary_statuses"]]
    assert list(csv.CUSTOMER_STATUS_KEYS) == json_keys


def test_labels_match_json():
    data = _load_vocab_json()
    expected = {s["key"]: s["label"] for s in data["primary_statuses"]}
    assert csv.CUSTOMER_STATUS_LABEL_BY_KEY == expected


def test_lifecycle_class_a_matches_json():
    data = _load_vocab_json()
    assert list(csv.CLASS_A_LIFECYCLE_STATES) == data["lifecycle"]["class_a"]["states"]


def test_lifecycle_class_b_matches_json():
    data = _load_vocab_json()
    assert list(csv.CLASS_B_LIFECYCLE_STATES) == data["lifecycle"]["class_b"]["states"]


def test_lifecycle_class_c_matches_json():
    data = _load_vocab_json()
    assert list(csv.CLASS_C_LIFECYCLE_STATES) == data["lifecycle"]["class_c"]["states"]


def test_retired_phrases_match_json():
    data = _load_vocab_json()
    assert list(csv.RETIRED_REVIEW_PHRASES) == data["retired_phrases"]


def test_canonical_ladder_matches_json():
    data = _load_vocab_json()
    assert list(csv.CANONICAL_OBLIGATION_STATUS_LADDER) == data["canonical_obligation_status_ladder"]


def test_overlay_precedence_matches_json():
    data = _load_vocab_json()
    assert list(csv.OVERLAY_PRECEDENCE) == data["overlay_precedence"]


def test_presentation_stage_mapping_matches_json():
    data = _load_vocab_json()
    assert csv.PRESENTATION_STAGE_TO_STATUS_KEY == data["presentation_stage_mapping"]


def test_review_policy_model_matches_json():
    data = _load_vocab_json()
    assert csv.REVIEW_POLICY_MODEL == data["review_policy"]["model"]


def test_implementation_sequence_rule():
    data = _load_vocab_json()
    assert csv.IMPLEMENTATION_SEQUENCE_RULE == data["implementation_sequence"]["rule"]


def test_every_primary_key_has_label():
    for key in csv.CUSTOMER_STATUS_KEYS:
        assert key in csv.CUSTOMER_STATUS_LABEL_BY_KEY
        assert csv.CUSTOMER_STATUS_LABEL_BY_KEY[key].strip()


def test_retired_phrases_non_empty():
    assert len(csv.RETIRED_REVIEW_PHRASES) >= 10


def test_class_disjoint_forbidden_badges():
    for badge in csv.CLASS_A_FORBIDDEN_PRIMARY_BADGES:
        assert badge not in csv.CLASS_A_LIFECYCLE_STATES
    for badge in csv.CLASS_B_FORBIDDEN_PRIMARY_BADGES:
        assert badge not in csv.CLASS_B_LIFECYCLE_STATES
