"""Contractor PATCH status transitions (strict workflow)."""
import pytest

from services import maintenance_service as ms
from services.contractor_work_order_status_policy import validate_contractor_status_patch


@pytest.mark.parametrize(
    "current,new,ok",
    [
        (ms.STATUS_SCHEDULED, ms.STATUS_IN_PROGRESS, True),
        (ms.STATUS_SCHEDULED, ms.STATUS_AWAITING_PARTS, True),
        (ms.STATUS_SCHEDULED, ms.STATUS_COMPLETED, False),
        (ms.STATUS_IN_PROGRESS, ms.STATUS_COMPLETED, True),
        (ms.STATUS_IN_PROGRESS, ms.STATUS_AWAITING_PARTS, True),
        (ms.STATUS_IN_PROGRESS, ms.STATUS_SCHEDULED, False),
        (ms.STATUS_AWAITING_PARTS, ms.STATUS_IN_PROGRESS, True),
        (ms.STATUS_AWAITING_PARTS, ms.STATUS_COMPLETED, True),
        (ms.STATUS_OPEN, ms.STATUS_IN_PROGRESS, False),
        (ms.STATUS_ASSIGNED, ms.STATUS_SCHEDULED, False),
        (ms.STATUS_COMPLETED, ms.STATUS_IN_PROGRESS, False),
        (ms.STATUS_SCHEDULED, ms.STATUS_SCHEDULED, True),
    ],
)
def test_validate_contractor_status_patch(current, new, ok):
    passed, err = validate_contractor_status_patch(current, new)
    assert passed is ok
    if not ok:
        assert err and len(err) > 5


def test_no_new_status_skips_policy():
    assert validate_contractor_status_patch(ms.STATUS_OPEN, None) == (True, None)
    assert validate_contractor_status_patch(ms.STATUS_OPEN, "") == (True, None)
