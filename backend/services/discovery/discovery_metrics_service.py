"""
Discovery metrics and ROI foundations — Stage S.

Operational analytics from prospects and audit history only.
No CRM, LeadService, provider integrations, routes, or UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from services.discovery.discovery_models import (
    DiscoveryDuplicateStatus,
    DiscoveryErasureStatus,
    DiscoveryProviderId,
    DiscoveryReviewStatus,
)

DEFAULT_CURRENCY = "GBP"

REVIEW_TERMINAL_APPROVED = frozenset(
    {
        DiscoveryReviewStatus.APPROVED.value,
        DiscoveryReviewStatus.IMPORTED.value,
    }
)

COMPLIANCE_BLOCK_EVENTS = frozenset(
    {
        "SUPPRESSION_MATCH",
        "CONSENT_VALIDATION_FAILED",
        "LIA_VALIDATION_FAILED",
    }
)


@dataclass(frozen=True)
class MetricsCostInputs:
    campaign_cost: float = 0.0
    provider_cost: float = 0.0
    manual_review_cost: float = 0.0
    currency: str = DEFAULT_CURRENCY

    @property
    def total_cost(self) -> float:
        return self.campaign_cost + self.provider_cost + self.manual_review_cost


@dataclass
class CampaignFunnelMetrics:
    prospects_created: int = 0
    needs_review: int = 0
    approved: int = 0
    imported: int = 0
    lead_created: int = 0
    conversion_to_needs_review_pct: float = 0.0
    conversion_to_approved_pct: float = 0.0
    conversion_to_imported_pct: float = 0.0
    conversion_to_lead_created_pct: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prospects_created": self.prospects_created,
            "needs_review": self.needs_review,
            "approved": self.approved,
            "imported": self.imported,
            "lead_created": self.lead_created,
            "conversion_to_needs_review_pct": self.conversion_to_needs_review_pct,
            "conversion_to_approved_pct": self.conversion_to_approved_pct,
            "conversion_to_imported_pct": self.conversion_to_imported_pct,
            "conversion_to_lead_created_pct": self.conversion_to_lead_created_pct,
        }


@dataclass
class CampaignMetrics:
    campaign_id: str
    prospects_created: int = 0
    approved: int = 0
    rejected: int = 0
    imported: int = 0
    duplicate_rate: float = 0.0
    average_quality_score: float = 0.0
    funnel: CampaignFunnelMetrics = field(default_factory=CampaignFunnelMetrics)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "prospects_created": self.prospects_created,
            "approved": self.approved,
            "rejected": self.rejected,
            "imported": self.imported,
            "duplicate_rate": self.duplicate_rate,
            "average_quality_score": self.average_quality_score,
            "funnel": self.funnel.to_dict(),
        }


@dataclass
class ProviderMetrics:
    provider: str
    prospects_discovered: int = 0
    prospects_accepted: int = 0
    prospects_rejected: int = 0
    prospects_approved: int = 0
    prospects_imported: int = 0
    duplicate_rate: float = 0.0
    average_quality_score: float = 0.0
    average_review_priority: float = 0.0
    suppression_rate: float = 0.0
    import_success_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "prospects_discovered": self.prospects_discovered,
            "prospects_accepted": self.prospects_accepted,
            "prospects_rejected": self.prospects_rejected,
            "prospects_approved": self.prospects_approved,
            "prospects_imported": self.prospects_imported,
            "duplicate_rate": self.duplicate_rate,
            "average_quality_score": self.average_quality_score,
            "average_review_priority": self.average_review_priority,
            "suppression_rate": self.suppression_rate,
            "import_success_rate": self.import_success_rate,
        }


@dataclass
class ReviewerPerformanceMetrics:
    reviewer_id: str
    approvals: int = 0
    rejections: int = 0
    request_changes: int = 0
    duplicate_overrides: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reviewer_id": self.reviewer_id,
            "approvals": self.approvals,
            "rejections": self.rejections,
            "request_changes": self.request_changes,
            "duplicate_overrides": self.duplicate_overrides,
        }


@dataclass
class ReviewMetrics:
    average_review_time_hours: float = 0.0
    approval_rate: float = 0.0
    rejection_rate: float = 0.0
    request_changes_rate: float = 0.0
    duplicate_override_rate: float = 0.0
    reviewer_performance: List[ReviewerPerformanceMetrics] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "average_review_time_hours": self.average_review_time_hours,
            "approval_rate": self.approval_rate,
            "rejection_rate": self.rejection_rate,
            "request_changes_rate": self.request_changes_rate,
            "duplicate_override_rate": self.duplicate_override_rate,
            "reviewer_performance": [r.to_dict() for r in self.reviewer_performance],
        }


@dataclass
class ImportMetrics:
    import_attempts: int = 0
    import_success: int = 0
    import_blocked: int = 0
    import_failed: int = 0
    duplicate_blocked: int = 0
    suppression_blocked: int = 0
    compliance_blocked: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "import_attempts": self.import_attempts,
            "import_success": self.import_success,
            "import_blocked": self.import_blocked,
            "import_failed": self.import_failed,
            "duplicate_blocked": self.duplicate_blocked,
            "suppression_blocked": self.suppression_blocked,
            "compliance_blocked": self.compliance_blocked,
        }


@dataclass
class CampaignRoiMetrics:
    campaign_id: str
    campaign_cost: float
    imported_leads_count: int
    cost_per_imported_lead: Optional[float]
    currency: str = DEFAULT_CURRENCY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "campaign_cost": self.campaign_cost,
            "imported_leads_count": self.imported_leads_count,
            "cost_per_imported_lead": self.cost_per_imported_lead,
            "currency": self.currency,
        }


@dataclass
class CostEfficiencyMetrics:
    cost_per_prospect: Optional[float] = None
    cost_per_approved: Optional[float] = None
    cost_per_imported: Optional[float] = None
    currency: str = DEFAULT_CURRENCY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cost_per_prospect": self.cost_per_prospect,
            "cost_per_approved": self.cost_per_approved,
            "cost_per_imported": self.cost_per_imported,
            "currency": self.currency,
        }


class DiscoveryMetricsValidationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class DiscoveryMetricsService:
    """Provider-neutral discovery measurement and ROI foundations."""

    @staticmethod
    def validate_metrics_inputs(
        *,
        prospects: Sequence[Mapping[str, Any]],
        audit_logs: Sequence[Mapping[str, Any]],
        costs: Optional[MetricsCostInputs] = None,
    ) -> List[str]:
        errors: List[str] = []
        for idx, prospect in enumerate(prospects):
            if not prospect.get("prospect_id"):
                errors.append(f"prospect[{idx}] missing prospect_id")
            if not prospect.get("provider"):
                errors.append(f"prospect[{idx}] missing provider")
        for idx, audit in enumerate(audit_logs):
            if not audit.get("event_type"):
                errors.append(f"audit[{idx}] missing event_type")
        if costs is not None:
            for name, value in (
                ("campaign_cost", costs.campaign_cost),
                ("provider_cost", costs.provider_cost),
                ("manual_review_cost", costs.manual_review_cost),
            ):
                if value < 0:
                    errors.append(f"{name} must be non-negative")
        return errors

    @staticmethod
    def _filter_prospects(
        prospects: Sequence[Mapping[str, Any]],
        *,
        campaign_id: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> List[Mapping[str, Any]]:
        out: List[Mapping[str, Any]] = []
        for prospect in prospects:
            if campaign_id and prospect.get("campaign_id") != campaign_id:
                continue
            if provider and str(prospect.get("provider")) != provider:
                continue
            out.append(prospect)
        return out

    @staticmethod
    def _pct(numerator: int, denominator: int, *, precision: int = 2) -> float:
        if denominator <= 0:
            return 0.0
        return round((numerator / denominator) * 100.0, precision)

    @staticmethod
    def _avg(values: Iterable[float]) -> float:
        items = list(values)
        if not items:
            return 0.0
        return round(sum(items) / len(items), 2)

    @staticmethod
    def _cost_ratio(total_cost: float, count: int) -> Optional[float]:
        if count <= 0:
            return None
        return round(total_cost / count, 4)

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            dt = value
        else:
            text = str(value).replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(text)
            except ValueError:
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _audit_action(audit: Mapping[str, Any]) -> Optional[str]:
        details = audit.get("details") or {}
        if not isinstance(details, dict):
            return None
        ctx = details.get("audit_context") or {}
        if isinstance(ctx, dict) and ctx.get("action"):
            return str(ctx.get("action"))
        action = details.get("action")
        return str(action) if action else None

    @staticmethod
    def _is_suppressed_prospect(prospect: Mapping[str, Any]) -> bool:
        if prospect.get("erasure_status") == DiscoveryErasureStatus.ERASED.value:
            return True
        flags = prospect.get("risk_flags") or []
        return any("suppression" in str(flag).lower() for flag in flags)

    @staticmethod
    def calculate_campaign_funnel(
        prospects: Sequence[Mapping[str, Any]],
        *,
        campaign_id: Optional[str] = None,
    ) -> CampaignFunnelMetrics:
        rows = DiscoveryMetricsService._filter_prospects(
            prospects, campaign_id=campaign_id
        )
        created = len(rows)
        needs_review = sum(
            1
            for p in rows
            if p.get("review_status")
            in (
                DiscoveryReviewStatus.NEEDS_REVIEW.value,
                DiscoveryReviewStatus.DUPLICATE_DETECTED.value,
                DiscoveryReviewStatus.DISCOVERED.value,
            )
        )
        approved = sum(
            1 for p in rows if p.get("review_status") in REVIEW_TERMINAL_APPROVED
        )
        imported = sum(
            1
            for p in rows
            if p.get("review_status") == DiscoveryReviewStatus.IMPORTED.value
            or bool(p.get("imported_lead_id"))
        )
        lead_created = imported

        return CampaignFunnelMetrics(
            prospects_created=created,
            needs_review=needs_review,
            approved=approved,
            imported=imported,
            lead_created=lead_created,
            conversion_to_needs_review_pct=DiscoveryMetricsService._pct(
                needs_review, created
            ),
            conversion_to_approved_pct=DiscoveryMetricsService._pct(approved, created),
            conversion_to_imported_pct=DiscoveryMetricsService._pct(imported, created),
            conversion_to_lead_created_pct=DiscoveryMetricsService._pct(
                lead_created, created
            ),
        )

    @staticmethod
    def calculate_campaign_metrics(
        prospects: Sequence[Mapping[str, Any]],
        *,
        campaign_id: str,
    ) -> CampaignMetrics:
        rows = DiscoveryMetricsService._filter_prospects(
            prospects, campaign_id=campaign_id
        )
        created = len(rows)
        rejected = sum(
            1
            for p in rows
            if p.get("review_status") == DiscoveryReviewStatus.REJECTED.value
        )
        approved = sum(
            1 for p in rows if p.get("review_status") in REVIEW_TERMINAL_APPROVED
        )
        imported = sum(
            1
            for p in rows
            if p.get("review_status") == DiscoveryReviewStatus.IMPORTED.value
            or bool(p.get("imported_lead_id"))
        )
        duplicate_count = sum(
            1
            for p in rows
            if p.get("duplicate_status")
            in (
                DiscoveryDuplicateStatus.CONFIRMED.value,
                DiscoveryDuplicateStatus.POSSIBLE.value,
            )
            or p.get("review_status")
            == DiscoveryReviewStatus.DUPLICATE_DETECTED.value
        )
        quality_scores = [
            float(p.get("platform_quality_score") or 0) for p in rows if rows
        ]

        return CampaignMetrics(
            campaign_id=campaign_id,
            prospects_created=created,
            approved=approved,
            rejected=rejected,
            imported=imported,
            duplicate_rate=DiscoveryMetricsService._pct(duplicate_count, created),
            average_quality_score=DiscoveryMetricsService._avg(quality_scores),
            funnel=DiscoveryMetricsService.calculate_campaign_funnel(
                prospects, campaign_id=campaign_id
            ),
        )

    @staticmethod
    def calculate_campaign_roi(
        *,
        campaign_id: str,
        campaign_cost: float,
        imported_leads_count: int,
        currency: str = DEFAULT_CURRENCY,
    ) -> CampaignRoiMetrics:
        cost_per = DiscoveryMetricsService._cost_ratio(
            campaign_cost, imported_leads_count
        )
        return CampaignRoiMetrics(
            campaign_id=campaign_id,
            campaign_cost=round(campaign_cost, 4),
            imported_leads_count=imported_leads_count,
            cost_per_imported_lead=cost_per,
            currency=currency,
        )

    @staticmethod
    def calculate_provider_metrics(
        prospects: Sequence[Mapping[str, Any]],
        audit_logs: Sequence[Mapping[str, Any]],
        *,
        provider: str,
    ) -> ProviderMetrics:
        rows = DiscoveryMetricsService._filter_prospects(prospects, provider=provider)
        discovered = len(rows)
        rejected = sum(
            1
            for p in rows
            if p.get("review_status") == DiscoveryReviewStatus.REJECTED.value
        )
        archived = sum(
            1
            for p in rows
            if p.get("review_status") == DiscoveryReviewStatus.ARCHIVED.value
        )
        accepted = max(0, discovered - rejected - archived)
        approved = sum(
            1 for p in rows if p.get("review_status") in REVIEW_TERMINAL_APPROVED
        )
        imported = sum(
            1
            for p in rows
            if p.get("review_status") == DiscoveryReviewStatus.IMPORTED.value
            or bool(p.get("imported_lead_id"))
        )
        duplicate_count = sum(
            1
            for p in rows
            if p.get("duplicate_status")
            in (
                DiscoveryDuplicateStatus.CONFIRMED.value,
                DiscoveryDuplicateStatus.POSSIBLE.value,
            )
            or p.get("review_status")
            == DiscoveryReviewStatus.DUPLICATE_DETECTED.value
        )
        suppressed = sum(
            1 for p in rows if DiscoveryMetricsService._is_suppressed_prospect(p)
        )
        prospect_ids = {p.get("prospect_id") for p in rows}
        attempts = sum(
            1
            for a in audit_logs
            if a.get("event_type") == "IMPORT_REQUESTED"
            and a.get("prospect_id") in prospect_ids
        )
        successes = sum(
            1
            for a in audit_logs
            if a.get("event_type") == "PROSPECT_IMPORTED"
            and a.get("prospect_id") in prospect_ids
        )

        return ProviderMetrics(
            provider=provider,
            prospects_discovered=discovered,
            prospects_accepted=accepted,
            prospects_rejected=rejected,
            prospects_approved=approved,
            prospects_imported=imported,
            duplicate_rate=DiscoveryMetricsService._pct(duplicate_count, discovered),
            average_quality_score=DiscoveryMetricsService._avg(
                float(p.get("platform_quality_score") or 0) for p in rows
            ),
            average_review_priority=DiscoveryMetricsService._avg(
                float(p.get("review_priority") or 0) for p in rows
            ),
            suppression_rate=DiscoveryMetricsService._pct(suppressed, discovered),
            import_success_rate=DiscoveryMetricsService._pct(successes, attempts),
        )

    @staticmethod
    def calculate_provider_quality(
        provider_metrics: ProviderMetrics,
    ) -> float:
        """Deterministic provider-neutral composite score (0–100)."""
        approval_denominator = max(
            1,
            provider_metrics.prospects_approved + provider_metrics.prospects_rejected,
        )
        approval_rate = provider_metrics.prospects_approved / approval_denominator
        components = (
            provider_metrics.average_quality_score * 0.4,
            (100.0 - provider_metrics.duplicate_rate) * 0.2,
            approval_rate * 100.0 * 0.2,
            provider_metrics.import_success_rate * 0.2,
        )
        return round(sum(components), 2)

    @staticmethod
    def calculate_provider_cost_efficiency(
        provider_metrics: ProviderMetrics,
        costs: MetricsCostInputs,
    ) -> CostEfficiencyMetrics:
        total = costs.total_cost
        return CostEfficiencyMetrics(
            cost_per_prospect=DiscoveryMetricsService._cost_ratio(
                total, provider_metrics.prospects_discovered
            ),
            cost_per_approved=DiscoveryMetricsService._cost_ratio(
                total, provider_metrics.prospects_approved
            ),
            cost_per_imported=DiscoveryMetricsService._cost_ratio(
                total, provider_metrics.prospects_imported
            ),
            currency=costs.currency,
        )

    @staticmethod
    def calculate_review_metrics(
        prospects: Sequence[Mapping[str, Any]],
        audit_logs: Sequence[Mapping[str, Any]],
    ) -> ReviewMetrics:
        approvals = 0
        rejections = 0
        request_changes = 0
        duplicate_overrides = 0
        reviewer_map: Dict[str, ReviewerPerformanceMetrics] = {}

        created_by_prospect: Dict[str, datetime] = {}
        for prospect in prospects:
            pid = prospect.get("prospect_id")
            created = DiscoveryMetricsService._parse_timestamp(
                prospect.get("created_at")
            )
            if pid and created:
                created_by_prospect[str(pid)] = created

        review_durations_hours: List[float] = []

        for audit in audit_logs:
            event_type = str(audit.get("event_type") or "")
            actor_id = str(audit.get("actor_id") or "unknown")
            if actor_id not in reviewer_map:
                reviewer_map[actor_id] = ReviewerPerformanceMetrics(
                    reviewer_id=actor_id
                )

            if event_type == "PROSPECT_APPROVED":
                approvals += 1
                reviewer_map[actor_id].approvals += 1
                pid = str(audit.get("prospect_id") or "")
                approved_at = DiscoveryMetricsService._parse_timestamp(
                    audit.get("created_at")
                )
                created_at = created_by_prospect.get(pid)
                if approved_at and created_at:
                    delta = (approved_at - created_at).total_seconds() / 3600.0
                    if delta >= 0:
                        review_durations_hours.append(delta)
            elif event_type == "PROSPECT_REJECTED":
                rejections += 1
                reviewer_map[actor_id].rejections += 1
            elif event_type == "PROSPECT_REVIEWED":
                if DiscoveryMetricsService._audit_action(audit) == "request_changes":
                    request_changes += 1
                    reviewer_map[actor_id].request_changes += 1
            elif event_type == "DUPLICATE_OVERRIDDEN":
                duplicate_overrides += 1
                reviewer_map[actor_id].duplicate_overrides += 1

        decisions = approvals + rejections + request_changes
        return ReviewMetrics(
            average_review_time_hours=DiscoveryMetricsService._avg(
                review_durations_hours
            ),
            approval_rate=DiscoveryMetricsService._pct(approvals, decisions),
            rejection_rate=DiscoveryMetricsService._pct(rejections, decisions),
            request_changes_rate=DiscoveryMetricsService._pct(
                request_changes, decisions
            ),
            duplicate_override_rate=DiscoveryMetricsService._pct(
                duplicate_overrides, len(prospects)
            ),
            reviewer_performance=sorted(
                reviewer_map.values(), key=lambda r: r.reviewer_id
            ),
        )

    @staticmethod
    def calculate_review_cycle_time(
        prospects: Sequence[Mapping[str, Any]],
        audit_logs: Sequence[Mapping[str, Any]],
    ) -> float:
        return DiscoveryMetricsService.calculate_review_metrics(
            prospects, audit_logs
        ).average_review_time_hours

    @staticmethod
    def calculate_reviewer_performance(
        audit_logs: Sequence[Mapping[str, Any]],
    ) -> List[ReviewerPerformanceMetrics]:
        return DiscoveryMetricsService.calculate_review_metrics(
            [], audit_logs
        ).reviewer_performance

    @staticmethod
    def calculate_import_metrics(
        audit_logs: Sequence[Mapping[str, Any]],
    ) -> ImportMetrics:
        attempts = 0
        success = 0
        blocked = 0
        failed = 0
        duplicate_blocked = 0
        suppression_blocked = 0
        compliance_blocked = 0

        for audit in audit_logs:
            event_type = str(audit.get("event_type") or "")
            details = audit.get("details") or {}

            if event_type == "IMPORT_REQUESTED":
                attempts += 1
            elif event_type == "PROSPECT_IMPORTED":
                success += 1
            elif event_type == "IMPORT_BLOCKED":
                blocked += 1
                failure_code = str(details.get("failure_code") or "")
                if failure_code == "CRM_DUPLICATE":
                    duplicate_blocked += 1
                elif failure_code == "ELIGIBILITY_FAILED":
                    blocking = details.get("blocking_reasons") or []
                    if any("suppression" in str(r).lower() for r in blocking):
                        suppression_blocked += 1
                    if any(
                        "lia_" in str(r).lower() or "marketing_consent" in str(r).lower()
                        for r in blocking
                    ):
                        compliance_blocked += 1
            elif event_type == "IMPORT_FAILED":
                failed += 1
            elif event_type == "SUPPRESSION_MATCH":
                suppression_blocked += 1
            elif event_type in COMPLIANCE_BLOCK_EVENTS:
                compliance_blocked += 1

        return ImportMetrics(
            import_attempts=attempts,
            import_success=success,
            import_blocked=blocked,
            import_failed=failed,
            duplicate_blocked=duplicate_blocked,
            suppression_blocked=suppression_blocked,
            compliance_blocked=compliance_blocked,
        )

    @staticmethod
    def calculate_import_conversion(
        import_metrics: ImportMetrics,
    ) -> float:
        return DiscoveryMetricsService._pct(
            import_metrics.import_success, import_metrics.import_attempts
        )

    @staticmethod
    def build_metrics_snapshot(
        *,
        prospects: Sequence[Mapping[str, Any]],
        audit_logs: Sequence[Mapping[str, Any]],
        campaign_id: Optional[str] = None,
        costs: Optional[MetricsCostInputs] = None,
        generated_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        errors = DiscoveryMetricsService.validate_metrics_inputs(
            prospects=prospects, audit_logs=audit_logs, costs=costs
        )
        if errors:
            raise DiscoveryMetricsValidationError(
                "INVALID_METRICS_INPUTS", "; ".join(errors)
            )

        when = generated_at or datetime.now(timezone.utc)

        providers_in_data = sorted(
            {str(p.get("provider")) for p in prospects if p.get("provider")}
        )
        all_providers = sorted({p.value for p in DiscoveryProviderId})
        provider_keys = sorted(set(providers_in_data) | set(all_providers))

        provider_metrics: Dict[str, Any] = {}
        provider_quality: Dict[str, float] = {}
        provider_costs: Dict[str, Any] = {}
        for provider in provider_keys:
            metrics = DiscoveryMetricsService.calculate_provider_metrics(
                prospects, audit_logs, provider=provider
            )
            provider_metrics[provider] = metrics.to_dict()
            provider_quality[provider] = (
                DiscoveryMetricsService.calculate_provider_quality(metrics)
            )
            if costs is not None:
                provider_costs[provider] = (
                    DiscoveryMetricsService.calculate_provider_cost_efficiency(
                        metrics, costs
                    ).to_dict()
                )

        campaign_metrics: Optional[Dict[str, Any]] = None
        campaign_roi: Optional[Dict[str, Any]] = None
        if campaign_id:
            cm = DiscoveryMetricsService.calculate_campaign_metrics(
                prospects, campaign_id=campaign_id
            )
            campaign_metrics = cm.to_dict()
            if costs is not None:
                campaign_roi = DiscoveryMetricsService.calculate_campaign_roi(
                    campaign_id=campaign_id,
                    campaign_cost=costs.total_cost,
                    imported_leads_count=cm.imported,
                    currency=costs.currency,
                ).to_dict()

        review_metrics = DiscoveryMetricsService.calculate_review_metrics(
            prospects, audit_logs
        ).to_dict()
        import_metrics = DiscoveryMetricsService.calculate_import_metrics(
            audit_logs
        ).to_dict()

        snapshot: Dict[str, Any] = {
            "generated_at": when.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "campaign_id": campaign_id,
            "provider_metrics": provider_metrics,
            "provider_quality_scores": provider_quality,
            "campaign_metrics": campaign_metrics,
            "campaign_roi": campaign_roi,
            "review_metrics": review_metrics,
            "import_metrics": import_metrics,
        }
        if provider_costs:
            snapshot["provider_cost_efficiency"] = provider_costs
        return snapshot

    @staticmethod
    def build_metrics_summary(
        snapshot: Mapping[str, Any],
        *,
        provider: Optional[str] = None,
    ) -> str:
        """Template-driven summary — no AI output."""
        provider = provider or "all"
        provider_metrics = snapshot.get("provider_metrics") or {}
        selected = provider_metrics.get(provider) if provider != "all" else None

        if selected is None and provider != "all":
            selected = {
                "prospects_discovered": 0,
                "prospects_approved": 0,
                "prospects_imported": 0,
                "duplicate_rate": 0.0,
                "average_quality_score": 0.0,
            }

        if provider == "all":
            discovered = sum(int(v.get("prospects_discovered", 0)) for v in provider_metrics.values())
            approved = sum(int(v.get("prospects_approved", 0)) for v in provider_metrics.values())
            imported = sum(int(v.get("prospects_imported", 0)) for v in provider_metrics.values())
            duplicate_rate = DiscoveryMetricsService._pct(
                sum(
                    1
                    for v in provider_metrics.values()
                    if float(v.get("duplicate_rate") or 0) > 0
                ),
                max(1, len(provider_metrics)),
            )
            avg_quality = DiscoveryMetricsService._avg(
                float(v.get("average_quality_score") or 0)
                for v in provider_metrics.values()
            )
        else:
            discovered = int(selected.get("prospects_discovered", 0))
            approved = int(selected.get("prospects_approved", 0))
            imported = int(selected.get("prospects_imported", 0))
            duplicate_rate = float(selected.get("duplicate_rate") or 0.0)
            avg_quality = float(selected.get("average_quality_score") or 0.0)

        cost_per_import = None
        roi = snapshot.get("campaign_roi") or {}
        if roi.get("cost_per_imported_lead") is not None:
            cost_per_import = roi["cost_per_imported_lead"]
        elif snapshot.get("provider_cost_efficiency"):
            eff = (snapshot.get("provider_cost_efficiency") or {}).get(provider)
            if eff:
                cost_per_import = eff.get("cost_per_imported")

        currency = (roi.get("currency") or DEFAULT_CURRENCY)
        cost_line = (
            f"{currency} {cost_per_import:.2f}"
            if cost_per_import is not None
            else "N/A"
        )

        label = provider.upper() if provider != "all" else "ALL PROVIDERS"
        return (
            f"Provider: {label}\n\n"
            f"Prospects:\n{discovered}\n\n"
            f"Approved:\n{approved}\n\n"
            f"Imported:\n{imported}\n\n"
            f"Duplicate Rate:\n{duplicate_rate}%\n\n"
            f"Average Quality:\n{avg_quality}\n\n"
            f"Cost Per Import:\n{cost_line}"
        )
