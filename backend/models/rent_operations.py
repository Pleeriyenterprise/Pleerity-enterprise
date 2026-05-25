"""Rent Operations Phase 1 — operational rent tracking and property expenses (not accounting)."""
from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


DEFAULT_CURRENCY = "GBP"
RENT_SEVERELY_OVERDUE_DAYS = 14
FUTURE_PERIODS_MONTHS_AHEAD = 6


def _coerce_iso_date(value) -> str:
    if isinstance(value, date):
        return value.isoformat()
    s = str(value).strip()[:10]
    date.fromisoformat(s)
    return s


class RentFrequency(str, Enum):
    MONTHLY = "monthly"
    WEEKLY = "weekly"


class RentLedgerStatus(str, Enum):
    UPCOMING = "UPCOMING"
    DUE_TODAY = "DUE_TODAY"
    PAID = "PAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    OVERDUE = "OVERDUE"
    SEVERELY_OVERDUE = "SEVERELY_OVERDUE"
    WAIVED = "WAIVED"
    DISPUTED = "DISPUTED"


class RentReminderType(str, Enum):
    DUE_SOON = "due_soon"
    DUE_TODAY = "due_today"
    OVERDUE_3D = "overdue_3d"
    OVERDUE_7D = "overdue_7d"
    OVERDUE_14D = "overdue_14d"


class ReminderDeliveryStatus(str, Enum):
    MANUAL = "manual"
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class ExpenseCategory(str, Enum):
    REPAIRS = "REPAIRS"
    MAINTENANCE = "MAINTENANCE"
    COMPLIANCE_CERTIFICATE = "COMPLIANCE_CERTIFICATE"
    INSURANCE = "INSURANCE"
    UTILITIES = "UTILITIES"
    MANAGEMENT = "MANAGEMENT"
    CONTRACTOR = "CONTRACTOR"
    CLEANING = "CLEANING"
    OTHER = "OTHER"


class CreateRentScheduleBody(BaseModel):
    property_id: str
    tenant_name: Optional[str] = None
    expected_amount_minor: int = Field(..., gt=0)
    currency: str = Field(default=DEFAULT_CURRENCY, min_length=3, max_length=3)
    rent_frequency: RentFrequency = RentFrequency.MONTHLY
    due_day: int = Field(default=1, ge=1, le=28, description="Day of month for monthly rent")
    start_date: date
    end_date: Optional[date] = None
    tenancy_id: Optional[str] = None
    is_external_payer: bool = False
    external_payer_name: Optional[str] = None
    idempotency_key: Optional[str] = Field(None, max_length=128)
    rent_type: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def validate_schedule_dates(cls, v):
        if v is None:
            return v
        return _coerce_iso_date(v)


class UpdateRentLedgerBody(BaseModel):
    expected_amount_minor: Optional[int] = Field(None, gt=0)
    due_date: Optional[date] = None
    tenant_name: Optional[str] = None
    notes: Optional[str] = None
    waived: Optional[bool] = None
    disputed: Optional[bool] = None
    dispute_note: Optional[str] = None

    @field_validator("due_date", mode="before")
    @classmethod
    def validate_due_date(cls, v):
        if v is None:
            return v
        return _coerce_iso_date(v)


class RentSchedulePreviewBody(BaseModel):
    property_id: str
    expected_amount_minor: int = Field(..., gt=0)
    rent_frequency: RentFrequency = RentFrequency.MONTHLY
    due_day: int = Field(default=1, ge=1, le=28)
    start_date: date
    end_date: Optional[date] = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def validate_preview_dates(cls, v):
        if v is None:
            return v
        return _coerce_iso_date(v)


class CreatePropertyTenancyBody(BaseModel):
    property_id: str
    tenant_display_name: Optional[str] = None
    tenant_ids: Optional[list[str]] = None
    rent_tracking_enabled: bool = False
    lineage_parent_tenancy_id: Optional[str] = Field(
        None,
        description="Prior tenancy when creating a replacement lineage after move-out",
    )


class ClosePropertyTenancyBody(BaseModel):
    status: str = Field(default="moved_out", pattern="^(moved_out|archived|ending_soon)$")


class RecordPaymentBody(BaseModel):
    amount_minor: int = Field(..., gt=0)
    payment_date: date
    payment_method: Optional[str] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    document_id: Optional[str] = None
    idempotency_key: Optional[str] = Field(None, max_length=128)
    ledger_id: Optional[str] = Field(
        None,
        description="Explicit allocation target; required for operational payment authority",
    )
    property_id: Optional[str] = Field(
        None,
        description="Required with tenancy_id when not using ledger_id",
    )
    tenancy_id: Optional[str] = Field(
        None,
        description="Required with property_id when not using ledger_id",
    )

    @field_validator("payment_date", mode="before")
    @classmethod
    def validate_payment_date(cls, v):
        return _coerce_iso_date(v)


class MarkReminderSentBody(BaseModel):
    reminder_type: RentReminderType
    channel: str = "manual"
    message_preview: Optional[str] = None


class CreateExpenseBody(BaseModel):
    property_id: str
    category: ExpenseCategory
    amount_minor: int = Field(..., gt=0)
    currency: str = Field(default=DEFAULT_CURRENCY, min_length=3, max_length=3)
    expense_date: date
    vendor_name: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    compliance_related: bool = False
    job_id: Optional[str] = None
    work_order_id: Optional[str] = None
    contractor_id: Optional[str] = None
    requirement_id: Optional[str] = None
    document_id: Optional[str] = None

    @field_validator("expense_date", mode="before")
    @classmethod
    def validate_expense_date(cls, v):
        return _coerce_iso_date(v)


class UpdateExpenseBody(BaseModel):
    category: Optional[ExpenseCategory] = None
    amount_minor: Optional[int] = Field(None, gt=0)
    expense_date: Optional[date] = None
    vendor_name: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    compliance_related: Optional[bool] = None
    job_id: Optional[str] = None
    work_order_id: Optional[str] = None
    contractor_id: Optional[str] = None
    requirement_id: Optional[str] = None
    document_id: Optional[str] = None

    @field_validator("expense_date", mode="before")
    @classmethod
    def validate_expense_date(cls, v):
        if v is None:
            return v
        return _coerce_iso_date(v)
