from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

# Compound unique idempotency indexes: sparse does not exclude explicit null values when
# client_id is always present — index only rows with a string idempotency_key.
_IDEM_COMPOUND_PARTIAL = {"idempotency_key": {"$type": "string"}}

class Database:
    client: AsyncIOMotorClient = None
    db = None
    
    async def connect(self):
        try:
            mongo_url = os.environ['MONGO_URL']
            # Bounded timeouts: avoid hanging deploy/health when Mongo is unreachable (e.g. wrong IP allowlist).
            self.client = AsyncIOMotorClient(
                mongo_url,
                serverSelectionTimeoutMS=10_000,
                connectTimeoutMS=10_000,
            )
            self.db = self.client[os.environ['DB_NAME']]
            # Verify connection
            await self.db.command("ping")
            logger.info(f"Connected to MongoDB: {os.environ['DB_NAME']}")
            
            # Create indexes for efficient search and lookups
            await self._create_indexes()
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def close(self):
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
    
    def get_db(self):
        return self.db

    async def _ensure_compound_idempotency_index(self, collection, *, label: str) -> None:
        """Unique (client_id, idempotency_key) only when idempotency_key is a non-null string."""
        name = "client_id_1_idempotency_key_1"
        keys = [("client_id", 1), ("idempotency_key", 1)]

        async def _create() -> None:
            await collection.create_index(
                keys,
                unique=True,
                name=name,
                partialFilterExpression=_IDEM_COMPOUND_PARTIAL,
            )

        try:
            await _create()
        except Exception as e:
            err = str(e).lower()
            if "indexoptionsconflict" in err or "indexkeyspecsconflict" in err:
                try:
                    await collection.drop_index(name)
                    await _create()
                    logger.info("%s idempotency index rebuilt with partial filter", label)
                    return
                except Exception as rebuild_err:
                    logger.warning("%s idempotency index rebuild failed: %s", label, rebuild_err)
                    return
            logger.warning("%s idempotency index: %s", label, e)
    
    async def _create_indexes(self):
        """Create MongoDB indexes for efficient queries."""
        try:
            # Client indexes - CRN (customer_reference) is critical for search
            # Use sparse=True to allow multiple null values
            try:
                await self.db.clients.create_index("customer_reference", unique=True, sparse=True)
            except Exception:
                pass  # Index may already exist with different options
            
            # Unique on ``email`` is case-sensitive at the BSON layer. Application code stores
            # canonical (trim + lower) addresses so the index matches the case-insensitive business rule.
            try:
                await self.db.clients.create_index("email", unique=True)
            except Exception as e:
                logger.warning(
                    "clients create_index on email (unique) did not apply; duplicates may be possible until resolved: %s",
                    e,
                )
            
            await self.db.clients.create_index("client_id", unique=True)
            await self.db.clients.create_index("full_name")  # For name search
            await self.db.clients.create_index("billing_plan")  # Plan filter (admin clients list)
            await self.db.clients.create_index("subscription_status")  # Status filter (admin clients list)
            try:
                await self.db.clients.create_index("client_lifecycle_status")
                await self.db.clients.create_index("is_deleted")
                await self.db.clients.create_index("purge_eligible")
                await self.db.clients.create_index("is_test_like")
            except Exception:
                pass
            
            # Property indexes - for postcode search
            await self.db.properties.create_index("postcode")
            await self.db.properties.create_index("client_id")
            await self.db.properties.create_index("property_id", unique=True)
            await self.db.properties.create_index("compliance_status")
            try:
                await self.db.properties.create_index(
                    [("client_id", 1), ("compliance_score", 1)],
                    name="idx_properties_client_compliance_score",
                )
                await self.db.properties.create_index(
                    [("client_id", 1), ("compliance_score_pending", 1)],
                    name="idx_properties_client_compliance_pending",
                )
            except Exception as e:
                logger.warning("properties compliance score indexes: %s", e)

            # Documents - pending verification admin list (status + uploaded_at; client_id filter)
            await self.db.documents.create_index([("status", 1), ("uploaded_at", 1)])
            await self.db.documents.create_index([("client_id", 1), ("status", 1), ("uploaded_at", 1)])
            await self.db.documents.create_index([("client_id", 1), ("uploaded_at", -1)])

            try:
                await self.db.evidence_review_events.create_index([("document_id", 1), ("created_at", -1)])
                await self.db.evidence_review_events.create_index("correlation_id")
                await self.db.evidence_review_events.create_index([("reviewer_id", 1), ("created_at", -1)])
            except Exception:
                pass
            
            # Portal user indexes
            try:
                await self.db.portal_users.create_index("auth_email", unique=True)
            except Exception:
                pass
            
            await self.db.portal_users.create_index("client_id")
            await self.db.portal_users.create_index("portal_user_id", unique=True)
            try:
                await self.db.portal_users.create_index("is_deleted")
                await self.db.portal_users.create_index("is_test_like")
            except Exception:
                pass

            # Evidence pack jobs (client exports)
            try:
                await self.db.compliance_evidence_pack_jobs.create_index(
                    [("client_id", 1), ("created_at", -1)]
                )
            except Exception:
                pass
            # Product analytics (first-party funnel events)
            try:
                await self.db.product_analytics_events.create_index(
                    [("client_id", 1), ("created_at", -1)]
                )
                await self.db.product_analytics_events.create_index(
                    [("event", 1), ("created_at", -1)]
                )
            except Exception:
                pass
            # Client read API keys (integrations; secret stored as hash only)
            try:
                await self.db.client_read_api_keys.create_index("token_hash", unique=True)
                await self.db.client_read_api_keys.create_index(
                    [("client_id", 1), ("revoked_at", 1)]
                )
            except Exception:
                pass
            
            # Audit log indexes - for timeline queries and email-delivery
            await self.db.audit_logs.create_index([("client_id", 1), ("timestamp", -1)])
            await self.db.audit_logs.create_index([("action", 1), ("timestamp", -1)])
            await self.db.audit_logs.create_index("timestamp")
            await self.db.audit_logs.create_index("action")
            
            # Message log indexes - for email-delivery admin view and orchestrator
            await self.db.message_logs.create_index([("created_at", -1)])
            await self.db.message_logs.create_index([("status", 1), ("created_at", -1)])
            await self.db.message_logs.create_index([("channel", 1), ("created_at", -1)])
            await self.db.message_logs.create_index([("template_alias", 1), ("created_at", -1)])
            await self.db.message_logs.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.message_logs.create_index([("template_key", 1), ("created_at", -1)])
            await self.db.message_logs.create_index("provider_message_id", sparse=True)
            try:
                await self.db.message_logs.create_index("idempotency_key", unique=True, sparse=True)
            except Exception:
                pass
            # Monthly digest delivery + snapshot comparison
            try:
                await self.db.digest_logs.create_index(
                    [("client_id", 1), ("report_month_key", 1), ("delivery_status", 1)],
                    name="idx_digest_client_month_status",
                )
            except Exception:
                pass
            try:
                await self.db.digest_logs.create_index("digest_id", unique=True, sparse=True)
            except Exception:
                pass
            try:
                await self.db.monthly_compliance_snapshots.create_index(
                    [("client_id", 1), ("report_month_key", 1)],
                    unique=True,
                    name="idx_monthly_snapshot_client_month",
                )
            except Exception:
                pass
            # Reminder item-level state + evaluation audit (truth-checked suppression/cooldown)
            try:
                await self.db.reminder_item_state.create_index(
                    [("client_id", 1), ("property_id", 1), ("requirement_code", 1), ("target_ref", 1), ("reminder_type", 1)],
                    unique=True,
                )
            except Exception:
                pass
            await self.db.reminder_item_state.create_index([("client_id", 1), ("reminder_type", 1), ("updated_at", -1)])
            await self.db.reminder_item_state.create_index([("suppression_reason", 1), ("updated_at", -1)])
            await self.db.reminder_evaluation_log.create_index([("created_at", -1)])
            await self.db.reminder_evaluation_log.create_index([("reminder_type", 1), ("decision", 1), ("created_at", -1)])
            await self.db.reminder_evaluation_log.create_index([("client_id", 1), ("property_id", 1), ("created_at", -1)])
            # Notification templates (template_key -> gating + email alias)
            await self.db.notification_templates.create_index("template_key", unique=True)
            # Notification retry queue (outbox pattern)
            await self.db.notification_retry_queue.create_index([("status", 1), ("next_run_at", 1)])
            await self.db.notification_retry_queue.create_index("message_id")
            try:
                await self.db.failed_notifications.create_index([("created_at", -1)])
                await self.db.failed_notifications.create_index("message_id")
                await self.db.failed_notifications.create_index("template_name")
            except Exception:
                pass
            # Onboarding email sequence queue (per-client, send_at)
            await self.db.onboarding_email_queue.create_index([("status", 1), ("send_at", 1)])
            await self.db.onboarding_email_queue.create_index([("client_id", 1), ("event_id", 1)], unique=True)
            await self._seed_notification_templates()
            await self._seed_communication_collections()
            # Compliance score history indexes - for trend queries
            await self.db.compliance_score_history.create_index([("client_id", 1), ("date_key", -1)])
            try:
                await self.db.compliance_score_history.create_index(
                    [("client_id", 1), ("date_key", 1)], 
                    unique=True
                )
            except Exception:
                pass  # Index may already exist
            # Property-level score history (event-driven)
            await self.db.property_compliance_score_history.create_index([("property_id", 1), ("created_at", -1)])
            await self.db.property_compliance_score_history.create_index([("client_id", 1), ("created_at", -1)])
            # Property daily score snapshots (score trend 90-day chart per property)
            await self.db.property_score_daily.create_index([("client_id", 1), ("property_id", 1), ("date", 1)], unique=True)
            await self.db.property_score_daily.create_index([("client_id", 1), ("date", -1)])
            await self.db.property_score_daily.create_index([("property_id", 1), ("date", -1)])
            # Async compliance recalc queue (Option B)
            try:
                await self.db.compliance_recalc_queue.create_index(
                    [("property_id", 1), ("correlation_id", 1)],
                    unique=True
                )
            except Exception:
                pass
            await self.db.compliance_recalc_queue.create_index([("status", 1), ("next_run_at", 1)])
            await self.db.compliance_recalc_queue.create_index([("status", 1), ("updated_at", 1)])
            await self.db.compliance_recalc_queue.create_index([("property_id", 1), ("status", 1)])
            # Risk signal regeneration queue (debounced; one PENDING row per property)
            try:
                await self.db.risk_signal_regen_queue.create_index([("status", 1), ("next_run_at", 1)])
            except Exception:
                pass
            try:
                await self.db.risk_signal_regen_queue.create_index(
                    [("property_id", 1)],
                    unique=True,
                    partialFilterExpression={"status": "PENDING"},
                    name="risk_regen_one_pending_per_property",
                )
            except Exception:
                pass
            try:
                await self.db.operational_issue_suggestions.create_index(
                    [("client_id", 1), ("property_id", 1), ("status", 1)]
                )
                await self.db.operational_issue_suggestions.create_index(
                    [("property_id", 1), ("operational_root_key", 1), ("status", 1)]
                )
            except Exception:
                pass
            try:
                await self.db.operational_automation_suppress_audit.create_index("created_at")
            except Exception:
                pass
            try:
                await self.db.maintenance_issues.create_index(
                    [("property_id", 1), ("operational_root_key", 1), ("status", 1)],
                    sparse=True,
                )
            except Exception:
                pass
            # Governed compliance gaps (stable gap_key upserts + client dashboards)
            try:
                await self.db.compliance_gaps.create_index("gap_key", unique=True)
                await self.db.compliance_gaps.create_index([("client_id", 1), ("status", 1)])
                await self.db.compliance_gaps.create_index([("client_id", 1), ("property_id", 1), ("status", 1)])
                await self.db.compliance_gaps.create_index([("requirement_id", 1), ("status", 1)])
                await self.db.compliance_gaps.create_index(
                    [("client_id", 1), ("status", 1), ("critical_mandatory_breach", 1)],
                    name="idx_gap_client_status_critical_breach",
                )
                await self.db.compliance_gaps.create_index(
                    [("client_id", 1), ("status", 1), ("high_risk_gap", 1)],
                    name="idx_gap_client_status_high_risk",
                )
                await self.db.compliance_gaps.create_index(
                    [("client_id", 1), ("status", 1), ("policy_classification_version", 1)],
                    name="idx_gap_client_status_policy_version",
                )
            except Exception:
                pass
            try:
                await self.db.requirements.create_index(
                    [("client_id", 1), ("requirement_id", 1)],
                    name="idx_requirements_client_requirement_id",
                )
                await self.db.requirements.create_index(
                    [("client_id", 1), ("applicability_state", 1), ("is_mandatory", 1), ("policy_criticality", 1)],
                    name="idx_requirements_client_policy_fields",
                )
                await self.db.requirements.create_index(
                    [("client_id", 1), ("requirement_code_normalized", 1), ("property_id", 1)],
                    name="idx_requirements_client_code_property",
                )
                await self.db.requirements.create_index(
                    [("client_id", 1), ("policy_classification_version", 1)],
                    name="idx_requirements_client_policy_version",
                )
                await self.db.requirements.create_index(
                    [("client_id", 1), ("pipeline_applicability_state", 1)],
                    name="idx_requirements_client_pipeline_applicability",
                )
                await self.db.requirements.create_index(
                    [("client_id", 1), ("effective_applicability_state", 1)],
                    name="idx_requirements_client_effective_applicability",
                )
                await self.db.requirements.create_index(
                    [("client_id", 1), ("applicability_resolution_source", 1)],
                    name="idx_requirements_client_applicability_resolution_source",
                )
                await self.db.requirements.create_index(
                    [("client_id", 1), ("operator_override_active", 1)],
                    name="idx_requirements_client_operator_override_active",
                )
                await self.db.requirements.create_index(
                    [("client_id", 1), ("pipeline_applicability_state", 1), ("requirement_id", 1)],
                    name="idx_requirements_client_pipeline_req_id",
                )
            except Exception:
                pass
            try:
                await self.db.compliance_policy_backfill_checkpoints.create_index(
                    [("job_name", 1), ("client_id", 1)],
                    unique=True,
                    name="idx_policy_backfill_checkpoint_job_client",
                )
                await self.db.compliance_policy_backfill_checkpoints.create_index(
                    [("status", 1), ("updated_at", -1)],
                    name="idx_policy_backfill_checkpoint_status_updated",
                )
                await self.db.compliance_policy_backfill_dead_letters.create_index(
                    [("job_name", 1), ("client_id", 1), ("created_at", -1)],
                    name="idx_policy_backfill_dlq_job_client_created",
                )
                await self.db.compliance_policy_backfill_dead_letters.create_index(
                    [("client_id", 1), ("requirement_id", 1), ("created_at", -1)],
                    name="idx_policy_backfill_dlq_client_requirement_created",
                )
            except Exception:
                pass
            try:
                await self.db.portfolio_risk_override_latches.create_index(
                    "client_id",
                    unique=True,
                    name="idx_portfolio_risk_override_latch_client",
                )
            except Exception:
                pass
            try:
                await self.db.applicability_resolution_audit.create_index(
                    [("client_id", 1), ("created_at", -1)],
                    name="idx_applicability_resolution_audit_client_created",
                )
                await self.db.applicability_resolution_audit.create_index(
                    [("client_id", 1), ("requirement_id", 1), ("created_at", -1)],
                    name="idx_applicability_resolution_audit_client_req_created",
                )
                await self.db.applicability_resolution_audit.create_index(
                    [("client_id", 1), ("property_id", 1), ("created_at", -1)],
                    name="idx_applicability_resolution_audit_client_prop_created",
                    sparse=True,
                )
            except Exception:
                pass
            try:
                await self.db.tenant_delivery_proofs.create_index("delivery_id", unique=True)
                await self.db.tenant_delivery_proofs.create_index([("client_id", 1), ("property_id", 1), ("created_at", -1)])
                await self.db.tenant_delivery_proofs.create_index([("tenant_portal_user_id", 1), ("created_at", -1)])
                await self.db.tenant_delivery_proofs.create_index("provider_message_id", sparse=True)
                await self.db.compliance_audit_packs.create_index("pack_id", unique=True)
                await self.db.compliance_audit_packs.create_index([("client_id", 1), ("property_id", 1), ("generated_at", -1)])
            except Exception:
                pass
            # Compliance recalc SLA alerts (dedupe by property + alert type)
            try:
                await self.db.compliance_sla_alerts.create_index(
                    [("property_id", 1), ("alert_type", 1)],
                    unique=True
                )
            except Exception:
                pass
            await self.db.compliance_sla_alerts.create_index([("active", 1), ("last_detected_at", -1)])
            await self.db.compliance_sla_alerts.create_index([("severity", 1)])
            # Score events - audit-grade log for score trend and "What Changed" (client dashboard)
            await self.db.score_events.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.score_events.create_index([("client_id", 1), ("event_type", 1), ("created_at", -1)])
            # Action -> Outcome activity log (client timeline + admin visibility)
            await self.db.compliance_activity_log.create_index([("client_id", 1), ("property_id", 1), ("created_at", -1)])
            await self.db.compliance_activity_log.create_index([("client_id", 1), ("created_at", -1)])
            try:
                await self.db.compliance_activity_log.create_index("dedupe_key", unique=True)
            except Exception:
                pass
            # Score ledger - enterprise statement-of-account for score changes (before/after, drivers, trigger)
            await self.db.score_ledger_events.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.score_ledger_events.create_index([("client_id", 1), ("property_id", 1), ("created_at", -1)])
            await self.db.score_ledger_events.create_index([("client_id", 1), ("trigger_type", 1), ("created_at", -1)])
            # Job runs - observability: every automation execution (for SLA watchdog and admin dashboard)
            await self.db.job_runs.create_index([("job_name", 1), ("created_at", -1)])
            await self.db.job_runs.create_index([("job_name", 1), ("started_at", -1)])
            await self.db.job_runs.create_index([("status", 1), ("created_at", -1)])
            await self.db.job_runs.create_index("created_at")
            await self.db.job_runs.create_index([("correlation_id", 1), ("created_at", -1)])
            # Operational Evidence Platform — append-only correlation index (not authoritative)
            try:
                await self.db.operational_evidence_events.create_index([("occurred_at", -1), ("event_id", -1)])
                await self.db.operational_evidence_events.create_index("event_id", unique=True)
                await self.db.operational_evidence_events.create_index([("correlation_id", 1), ("occurred_at", 1)])
                await self.db.operational_evidence_events.create_index([("root_execution_id", 1), ("execution.execution_sequence", 1)])
                await self.db.operational_evidence_events.create_index([("execution_id", 1), ("occurred_at", 1)])
                await self.db.operational_evidence_events.create_index([("category", 1), ("occurred_at", -1)])
                await self.db.operational_evidence_events.create_index([("event_type", 1), ("occurred_at", -1)])
                await self.db.operational_evidence_events.create_index([("client_id", 1), ("occurred_at", -1)])
                await self.db.operational_evidence_events.create_index([("property_id", 1), ("occurred_at", -1)])
                await self.db.operational_evidence_events.create_index([("requirement_id", 1), ("occurred_at", -1)])
                await self.db.operational_evidence_events.create_index([("job_run_id", 1), ("occurred_at", -1)])
                await self.db.operational_evidence_events.create_index([("incident_id", 1), ("occurred_at", -1)])
                await self.db.operational_evidence_events.create_index([("notification_id", 1), ("occurred_at", -1)])
                await self.db.operational_evidence_events.create_index([("severity", 1), ("occurred_at", -1)])
                await self.db.operational_evidence_events.create_index([("status", 1), ("occurred_at", -1)])
                await self.db.operational_evidence_events.create_index([("environment", 1), ("occurred_at", -1)])
                await self.db.operational_evidence_events.create_index([("customer_impact.classification", 1), ("occurred_at", -1)])
                await self.db.operational_evidence_events.create_index([("relationships.parent_event_id", 1)])
                await self.db.operational_evidence_events.create_index([("relationships.caused_by_event_id", 1)])
                await self.db.operational_evidence_executions.create_index("root_execution_id", unique=True)
                await self.db.operational_evidence_executions.create_index([("correlation_id", 1), ("started_at", -1)])
                await self.db.operational_evidence_events.create_index([("retention.tier", 1), ("occurred_at", -1)])
                await self.db.operational_evidence_annotations.create_index([("event_id", 1), ("created_at", -1)])
                await self.db.operational_evidence_annotations.create_index([("root_execution_id", 1), ("created_at", -1)])
                await self.db.operational_evidence_annotations.create_index([("correlation_id", 1), ("created_at", -1)])
            except Exception as e:
                logger.warning("operational_evidence indexes: %s", e)
            # Compliance Evidence Graph — decision foundation (Phase 1)
            try:
                await self.db.compliance_decisions.create_index("decision_id", unique=True)
                await self.db.compliance_decisions.create_index("dedupe_key", unique=True)
                await self.db.compliance_decisions.create_index([("client_id", 1), ("decision_timestamp", -1)])
                await self.db.compliance_decisions.create_index([("property_id", 1), ("decision_timestamp", -1)])
                await self.db.compliance_decisions.create_index([("requirement_id", 1), ("decision_timestamp", -1)])
                await self.db.compliance_decisions.create_index([("decision_type", 1), ("decision_timestamp", -1)])
                await self.db.compliance_decisions.create_index("previous_decision_id")
                await self.db.compliance_decisions.create_index("operational_correlation_id")
                await self.db.compliance_decisions.create_index("snapshot_id", unique=True)
                await self.db.compliance_decision_snapshots.create_index("snapshot_id", unique=True)
                await self.db.compliance_decision_snapshots.create_index("decision_id", unique=True)
                await self.db.compliance_decision_snapshots.create_index([("client_id", 1), ("snapshot_timestamp", -1)])
                await self.db.compliance_decision_snapshots.create_index([("property_id", 1), ("snapshot_timestamp", -1)])
                await self.db.compliance_decision_snapshots.create_index("snapshot_hash")
                await self.db.compliance_evidence_nodes.create_index("node_id", unique=True)
                await self.db.compliance_evidence_nodes.create_index("dedupe_key", unique=True)
                await self.db.compliance_evidence_nodes.create_index([("client_id", 1), ("occurred_at", -1)])
                await self.db.compliance_evidence_nodes.create_index([("property_id", 1), ("occurred_at", -1)])
                await self.db.compliance_evidence_nodes.create_index([("requirement_id", 1), ("occurred_at", -1)])
                await self.db.compliance_evidence_nodes.create_index([("decision_id", 1), ("occurred_at", 1)])
                await self.db.compliance_evidence_nodes.create_index([("node_type", 1), ("occurred_at", -1)])
                await self.db.compliance_evidence_nodes.create_index([("correlation_id", 1), ("occurred_at", 1)])
                await self.db.compliance_evidence_nodes.create_index(
                    [("source.collection", 1), ("source.id", 1), ("node_type", 1)]
                )
                await self.db.compliance_evidence_edges.create_index("edge_id", unique=True)
                await self.db.compliance_evidence_edges.create_index("dedupe_key", unique=True)
                await self.db.compliance_evidence_edges.create_index([("from_node_id", 1), ("edge_type", 1)])
                await self.db.compliance_evidence_edges.create_index([("to_node_id", 1), ("edge_type", 1)])
                await self.db.compliance_evidence_edges.create_index(
                    [("provenance.decision_id", 1), ("recorded_at", -1)]
                )
                await self.db.compliance_evidence_edges.create_index(
                    [("provenance.correlation_id", 1), ("recorded_at", 1)]
                )
                await self.db.compliance_evidence_edges.create_index(
                    [("provenance.is_active", 1), ("edge_type", 1)]
                )
            except Exception as e:
                logger.warning("compliance_evidence_graph indexes: %s", e)
            # Compliance AI narrations — intelligence audit trail (Phase 5)
            try:
                await self.db.compliance_ai_narrations.create_index("narration_id", unique=True)
                await self.db.compliance_ai_narrations.create_index([("client_id", 1), ("created_at", -1)])
                await self.db.compliance_ai_narrations.create_index("graph_service_response_hash")
                await self.db.compliance_ai_narrations.create_index([("decision_id", 1), ("created_at", -1)])
            except Exception as e:
                logger.warning("compliance_ai_narrations indexes: %s", e)
            try:
                await self.db.compliance_intelligence_artefacts.create_index("artefact_id", unique=True)
                await self.db.compliance_intelligence_artefacts.create_index(
                    [("client_id", 1), ("artefact_type", 1), ("lifecycle_state", 1)]
                )
                await self.db.compliance_intelligence_artefacts.create_index(
                    [("client_id", 1), ("generated_at", -1)]
                )
                await self.db.compliance_intelligence_artefacts.create_index("inputs_hash")
                await self.db.compliance_intelligence_artefacts.create_index("dedupe_key", sparse=True)
            except Exception as e:
                logger.warning("compliance_intelligence_artefacts indexes: %s", e)
            try:
                await self.db.compliance_intelligence_transitions.create_index("transition_id", unique=True)
                await self.db.compliance_intelligence_transitions.create_index(
                    [("artefact_id", 1), ("transitioned_at", -1)]
                )
                await self.db.compliance_intelligence_transitions.create_index(
                    [("client_id", 1), ("transitioned_at", -1)]
                )
            except Exception as e:
                logger.warning("compliance_intelligence_transitions indexes: %s", e)
            try:
                await self.db.compliance_intelligence_provenance.create_index("provenance_id", unique=True)
                await self.db.compliance_intelligence_provenance.create_index("artefact_id", unique=True)
                await self.db.compliance_intelligence_provenance.create_index(
                    [("client_id", 1), ("generated_at", -1)]
                )
                await self.db.compliance_intelligence_provenance.create_index("inputs_hash")
                await self.db.compliance_intelligence_provenance.create_index("generation_decision_id", sparse=True)
            except Exception as e:
                logger.warning("compliance_intelligence_provenance indexes: %s", e)
            try:
                await self.db.compliance_intelligence_strategy_registry.create_index("strategy_id", unique=True)
                await self.db.compliance_intelligence_strategy_registry.create_index(
                    [("strategy_family", 1), ("semantic_version", -1)]
                )
            except Exception as e:
                logger.warning("compliance_intelligence_strategy_registry indexes: %s", e)
            try:
                await self.db.compliance_intelligence_weight_registry.create_index("weight_set_id", unique=True)
            except Exception as e:
                logger.warning("compliance_intelligence_weight_registry indexes: %s", e)
            try:
                await self.db.compliance_intelligence_constraint_registry.create_index(
                    "constraint_set_id", unique=True
                )
            except Exception as e:
                logger.warning("compliance_intelligence_constraint_registry indexes: %s", e)
            await self.db.incidents.create_index([("status", 1), ("created_at", -1)])
            await self.db.incidents.create_index([("severity", 1), ("status", 1)])
            await self.db.incidents.create_index("created_at")
            await self.db.incidents.create_index("incident_fingerprint")
            await self.db.incidents.create_index([("lifecycle_state", 1), ("status", 1)])
            await self.db.incidents.create_index([("related_job_name", 1), ("status", 1)])
            # Security monitoring collections (events, incidents, auto-response locks/blocks)
            await self.db.security_incidents.create_index([("status", 1), ("timestamp", -1)])
            await self.db.security_incidents.create_index([("severity", 1), ("status", 1)])
            await self.db.security_incidents.create_index([("type", 1), ("timestamp", -1)])
            await self.db.security_incidents.create_index("incident_key", unique=True)
            await self.db.security_events.create_index("event_id", unique=True)
            await self.db.security_events.create_index([("event_type", 1), ("timestamp", -1)])
            await self.db.security_events.create_index([("ip", 1), ("timestamp", -1)])
            await self.db.security_events.create_index([("user_id", 1), ("timestamp", -1)])
            await self.db.security_locks.create_index([("lock_type", 1), ("principal", 1)], unique=True)
            await self.db.security_locks.create_index("expires_at")
            await self.db.security_blocks.create_index("ip", unique=True)
            await self.db.security_blocks.create_index("expires_at")
            # Admin login MFA challenges (email OTP fallback for staff login hardening)
            await self.db.admin_login_challenges.create_index("challenge_id", unique=True)
            await self.db.admin_login_challenges.create_index([("portal_user_id", 1), ("created_at", -1)])
            await self.db.admin_login_challenges.create_index("expires_at")
            # Operations & Compliance: module feature flags per client
            await self.db.client_feature_flags.create_index([("client_id", 1), ("flag_key", 1)], unique=True)
            await self.db.client_feature_flags.create_index("client_id")
            # CVP subscription checkout PDF receipts (portal billing)
            try:
                await self.db.stripe_checkout_invoices.create_index([("client_id", 1), ("created_at", -1)])
                await self.db.stripe_checkout_invoices.create_index([("client_id", 1), ("invoice_number", 1)])
            except Exception:
                pass
            # CVP subscription renewal / proration receipts (invoice.paid; _id = Stripe invoice id)
            try:
                await self.db.cvp_subscription_renewal_receipts.create_index([("client_id", 1), ("paid_at", -1)])
                await self.db.cvp_subscription_renewal_receipts.create_index([("client_id", 1), ("invoice_number", 1)])
            except Exception:
                pass
            # Provisioning status per property/module (compliance, maintenance)
            await self.db.provisioning_status.create_index([("client_id", 1), ("property_id", 1), ("module_name", 1)], unique=True)
            await self.db.provisioning_status.create_index([("client_id", 1), ("module_name", 1)])
            # Founding pilot invite codes and idempotent redemptions
            try:
                await self.db.pilot_invite_codes.create_index("code", unique=True)
                await self.db.pilot_invite_codes.create_index("invite_code_id", unique=True)
                await self.db.pilot_invite_redemptions.create_index("checkout_session_id", unique=True)
                await self.db.pilot_invite_validation_attempts.create_index([("code", 1), ("created_at", -1)])
                await self.db.pilot_invite_validation_attempts.create_index([("invite_code_id", 1), ("created_at", -1)])
                await self.db.pilot_invite_validation_attempts.create_index([("outcome", 1), ("created_at", -1)])
                await self.db.pilot_invite_redemptions.create_index(
                    [("invite_code_id", 1), ("redemption_email", 1)], sparse=True
                )
                await self.db.pilot_invite_redemptions.create_index(
                    [("invite_code_id", 1), ("stripe_payment_method_id", 1)], sparse=True
                )
                await self.db.pilot_invite_send_attempts.create_index([("invite_code", 1), ("sent_at", -1)])
                await self.db.pilot_invite_send_attempts.create_index([("recipient_email", 1), ("sent_at", -1)])
                await self.db.pilot_redeemed_campaign_snapshots.create_index("snapshot_id", unique=True)
                await self.db.pilot_redeemed_campaign_snapshots.create_index([("client_id", 1), ("redeemed_at", -1)])
                await self.db.pilot_redeemed_campaign_snapshots.create_index([("analytics_family", 1), ("redeemed_at", -1)])
                await self.db.pilot_account_overrides.create_index([("client_id", 1), ("created_at", -1)])
                await self.db.pilot_account_overrides.create_index([("override_type", 1), ("created_at", -1)])
                await self.db.pilot_redemption_eligibility_overrides.create_index("override_id", unique=True)
                await self.db.pilot_redemption_eligibility_overrides.create_index(
                    [("scope", 1), ("scope_value", 1), ("override_type", 1)]
                )
                await self.db.pilot_redemption_eligibility_overrides.create_index(
                    [("invite_code_id", 1), ("override_created_at", -1)]
                )
                await self.db.pilot_invite_redemptions.create_index([("client_id", 1), ("created_at", -1)])
                await self.db.pilot_invite_redemptions.create_index([("status", 1), ("created_at", -1)])
                await self.db.clients.create_index("pilot_invite_code", sparse=True)
                await self.db.clients.create_index("pilot_status", sparse=True)
                await self.db.pilot_lifecycle_audit.create_index([("client_id", 1), ("created_at", -1)])
                await self.db.pilot_lifecycle_audit.create_index("idempotency_key", unique=True, sparse=True)
                await self.db.pilot_lifecycle_audit.create_index([("action_type", 1), ("created_at", -1)])
                await self.db.pilot_operational_anomalies.create_index("anomaly_id", unique=True)
                await self.db.pilot_operational_anomalies.create_index(
                    [("client_id", 1), ("resolved_at", 1), ("detected_at", -1)]
                )
                await self.db.pilot_operational_anomalies.create_index("idempotency_key", unique=True, sparse=True)
                await self.db.pilot_operational_notification_log.create_index(
                    [("client_id", 1), ("created_at", -1)]
                )
                await self.db.clients.create_index("pilot_governance_status", sparse=True)
                await self.db.clients.create_index("pilot_health_band", sparse=True)
            except Exception:
                pass
            # Contractors (Ops: client-scoped or system-wide)
            await self.db.contractors.create_index("contractor_id", unique=True)
            await self.db.contractors.create_index("client_id")
            await self.db.contractors.create_index([("vetted", 1), ("client_id", 1)])
            await self.db.contractors.create_index("source_type")
            await self.db.contractors.create_index("status")
            await self.db.contractors.create_index("portal_access_status")
            await self.db.contractors.create_index([("portal_access_status", 1), ("updated_at", -1)])
            try:
                await self.db.contractors.create_index("email_normalized", sparse=True)
            except Exception:
                pass
            # Contractor ratings (landlord/client rates contractor after job)
            await self.db.contractor_ratings.create_index("rating_id", unique=True)
            await self.db.contractor_ratings.create_index("contractor_id")
            await self.db.contractor_ratings.create_index([("contractor_id", 1), ("created_at", -1)])
            await self.db.contractor_ratings.create_index("work_order_id", sparse=True)
            # Contractor performance (updated on work order completion)
            await self.db.contractor_performance.create_index([("contractor_id", 1), ("client_id", 1)], unique=True)
            await self.db.contractor_performance.create_index("contractor_id")
            # Work orders (maintenance workflows: tenant/client report → assign contractor → SLA)
            await self.db.work_orders.create_index("work_order_id", unique=True)
            await self.db.work_orders.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.work_orders.create_index([("client_id", 1), ("status", 1)])
            await self.db.work_orders.create_index([("property_id", 1), ("created_at", -1)])
            await self.db.work_orders.create_index("contractor_id", sparse=True)
            try:
                await self.db.work_orders.create_index("work_order_kind", sparse=True)
            except Exception:
                pass
            try:
                await self.db.work_orders.create_index(
                    [("client_id", 1), ("work_order_kind", 1), ("requirement_code", 1)],
                    sparse=True,
                )
            except Exception:
                pass
            await self.db.work_orders.create_index("issue_id", sparse=True)
            await self.db.work_orders.create_index("asset_id", sparse=True)
            try:
                await self.db.work_orders.create_index(
                    [("property_id", 1), ("operational_root_key", 1), ("status", 1)],
                    sparse=True,
                )
            except Exception:
                pass
            try:
                await self.db.work_orders.create_index(
                    [
                        ("assignment_routing_state", 1),
                        ("client_confirmation_deadline_at", 1),
                    ],
                    sparse=True,
                )
            except Exception:
                pass
            try:
                await self.db.work_orders.create_index(
                    [("schedule_status", 1), ("reminder_sent", 1), ("scheduled_at", 1)],
                    sparse=True,
                )
            except Exception:
                pass
            # Contractor assignments (history when work order is assigned; current assignment remains on work_order)
            await self.db.contractor_assignments.create_index([("work_order_id", 1), ("assigned_at", -1)])
            await self.db.contractor_assignments.create_index("work_order_id")
            await self.db.contractor_assignments.create_index("contractor_id")
            # Contractor job access tokens (secure link per work order assignment; no login required)
            await self.db.contractor_job_tokens.create_index("token_hash", unique=True)
            await self.db.contractor_job_tokens.create_index([("work_order_id", 1), ("contractor_id", 1)])
            await self.db.contractor_job_tokens.create_index("expires_at")
            await self.db.contractor_job_tokens.create_index("revoked_at")
            # Maintenance issues (issue → triage → work order flow)
            await self.db.maintenance_issues.create_index("issue_id", unique=True)
            await self.db.maintenance_issues.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.maintenance_issues.create_index([("client_id", 1), ("status", 1)])
            await self.db.maintenance_issues.create_index([("property_id", 1), ("created_at", -1)])
            # Property assets + maintenance events (predictive maintenance)
            await self.db.property_assets.create_index([("property_id", 1), ("asset_id", 1)], unique=True)
            await self.db.property_assets.create_index("property_id")
            await self.db.property_assets.create_index([("property_id", 1), ("asset_type", 1)])
            await self.db.maintenance_events.create_index("event_id", unique=True)
            await self.db.maintenance_events.create_index([("property_id", 1), ("occurred_at", -1)])
            await self.db.maintenance_events.create_index([("client_id", 1), ("occurred_at", -1)])
            # Asset events (per-asset history: issue_created, repair_completed, document_linked, etc.)
            await self.db.asset_events.create_index([("asset_id", 1), ("timestamp", -1)])
            await self.db.asset_events.create_index([("property_id", 1), ("timestamp", -1)])
            await self.db.asset_events.create_index([("client_id", 1), ("related_issue_id", 1)], sparse=True)
            await self.db.asset_events.create_index("event_id", unique=True)
            # Predictive insights cache (scheduled job writes; API can read when fresh)
            await self.db.predictive_insights_cache.create_index("client_id", unique=True)
            await self.db.predictive_insights_cache.create_index("updated_at")
            # Risk signals (stored, explainable risk intelligence per property)
            await self.db.risk_signals.create_index("signal_id", unique=True)
            await self.db.risk_signals.create_index([("client_id", 1), ("property_id", 1), ("status", 1)])
            await self.db.risk_signals.create_index([("client_id", 1), ("generated_at", -1)])
            await self.db.risk_signals.create_index([("property_id", 1), ("status", 1)])
            await self.db.risk_signals.create_index([("property_id", 1), ("signal_category", 1)])
            # Rent Operations (operational rent tracking — not accounting)
            await self.db.rent_ledger_periods.create_index("ledger_id", unique=True)
            await self.db.rent_ledger_periods.create_index([("client_id", 1), ("property_id", 1), ("due_date", -1)])
            await self.db.rent_ledger_periods.create_index([("client_id", 1), ("status", 1), ("due_date", 1)])
            # Tenancy-authority materialisation uses schedule_id+period_key; legacy unique on property+period_key blocks new schedules.
            legacy_period_idx = "client_id_1_property_id_1_period_key_1"
            try:
                await self.db.rent_ledger_periods.drop_index(legacy_period_idx)
            except Exception:
                pass
            await self.db.rent_ledger_periods.create_index(
                [("client_id", 1), ("property_id", 1), ("period_key", 1)]
            )
            await self.db.rent_payments.create_index("payment_id", unique=True)
            await self.db.rent_payments.create_index([("ledger_id", 1), ("payment_date", -1)])
            await self.db.rent_payments.create_index([("client_id", 1), ("payment_date", -1)])
            await self.db.rent_payments.create_index([("client_id", 1), ("property_id", 1), ("payment_date", -1)])
            await self.db.rent_ledger_periods.create_index([("client_id", 1), ("is_overdue", 1), ("due_date", -1)], sparse=True)
            await self.db.rent_reminder_events.create_index("reminder_key", unique=True)
            await self.db.rent_reminder_events.create_index([("client_id", 1), ("ledger_id", 1)])
            await self.db.rent_schedules.create_index("schedule_id", unique=True)
            await self.db.rent_schedules.create_index([("client_id", 1), ("property_id", 1), ("is_active", 1)])
            try:
                await self._ensure_compound_idempotency_index(self.db.rent_schedules, label="rent_schedules")
            except Exception as e:
                logger.warning("rent_schedules idempotency index: %s", e)
            await self.db.rent_schedules.create_index(
                [("client_id", 1), ("property_id", 1), ("tenancy_id", 1), ("rent_type", 1), ("is_active", 1)]
            )
            await self.db.rent_ledger_periods.create_index(
                [("client_id", 1), ("schedule_id", 1), ("period_key", 1)], unique=True, sparse=True
            )
            try:
                await self._ensure_compound_idempotency_index(self.db.rent_payments, label="rent_payments")
            except Exception as e:
                logger.warning("rent_payments idempotency index: %s", e)
            await self.db.rent_payments.create_index([("client_id", 1), ("tenancy_id", 1), ("payment_date", -1)], sparse=True)
            await self.db.property_tenancies.create_index("tenancy_id", unique=True)
            await self.db.property_tenancies.create_index(
                [("client_id", 1), ("property_id", 1), ("status", 1)]
            )
            await self.db.rent_unallocated_payments.create_index("unallocated_id", unique=True)
            await self.db.rent_unallocated_payments.create_index(
                [("client_id", 1), ("property_id", 1), ("tenancy_id", 1)], sparse=True
            )
            await self.db.property_expenses.create_index("expense_id", unique=True)
            await self.db.property_expenses.create_index([("client_id", 1), ("property_id", 1), ("expense_date", -1)])
            await self.db.property_expenses.create_index([("client_id", 1), ("category", 1), ("expense_date", -1)])
            await self.db.property_expenses.create_index(
                [("client_id", 1), ("compliance_related", 1), ("expense_date", -1)], sparse=True
            )
            # Invoices & invoice approvals (Operations → Approvals; gated by INVOICING)
            await self.db.invoices.create_index("invoice_id", unique=True)
            await self.db.invoices.create_index([("client_id", 1), ("status", 1)])
            await self.db.invoices.create_index([("client_id", 1), ("submitted_at", -1)])
            await self.db.invoices.create_index("work_order_id", sparse=True)
            await self.db.invoices.create_index("contractor_id", sparse=True)
            await self.db.invoices.create_index("property_id")
            await self.db.invoice_approvals.create_index("approval_id", unique=True)
            await self.db.invoice_approvals.create_index("invoice_id")
            await self.db.invoice_approvals.create_index([("invoice_id", 1), ("created_at", -1)])
            # Orders (intake → payment → workflow): idempotency by Stripe session
            try:
                await self.db.orders.create_index("pricing.stripe_checkout_session_id", unique=True, sparse=True)
            except Exception:
                pass
            await self.db.orders.create_index("source_draft_id", unique=True)
            await self.db.orders.create_index([("status", 1), ("created_at", -1)])
            await self.db.orders.create_index("order_ref", unique=True)

            # Submissions: contact, talent, partnership (list/dedupe/audit)
            await self.db.contact_submissions.create_index("submission_id", unique=True)
            await self.db.contact_submissions.create_index([("email_normalized", 1), ("created_at", -1)])
            await self.db.contact_submissions.create_index([("dedupe_key", 1), ("created_at", -1)])
            await self.db.contact_submissions.create_index("created_at")
            await self.db.contact_submissions.create_index("status")
            await self.db.talent_pool.create_index("submission_id", unique=True)
            await self.db.talent_pool.create_index([("email_normalized", 1), ("created_at", -1)])
            await self.db.talent_pool.create_index([("dedupe_key", 1), ("created_at", -1)])
            await self.db.talent_pool.create_index("created_at")
            await self.db.talent_pool.create_index("status")
            await self.db.partnership_enquiries.create_index("enquiry_id", unique=True)
            await self.db.partnership_enquiries.create_index([("email_normalized", 1), ("created_at", -1)])
            await self.db.partnership_enquiries.create_index([("dedupe_key", 1), ("created_at", -1)])
            await self.db.partnership_enquiries.create_index("created_at")
            await self.db.partnership_enquiries.create_index("status")
            # Risk check leads (conversion demo; no client/provisioning)
            await self.db.risk_leads.create_index("lead_id", unique=True)
            await self.db.risk_leads.create_index("created_at")
            await self.db.risk_leads.create_index("email")
            await self.db.risk_leads.create_index("risk_band")
            await self.db.risk_leads.create_index("status")
            # Central leads (unified lead engine)
            await self.db.leads.create_index("lead_id", unique=True)
            await self.db.leads.create_index("email")
            await self.db.leads.create_index("created_at")
            await self.db.leads.create_index("last_activity_at")
            await self.db.leads.create_index([("status", 1), ("stage", 1)])
            await self.db.leads.create_index("source_platform")
            await self.db.leads.create_index("lead_score")
            await self.db.leads.create_index("converted_at")
            await self.db.leads.create_index("conversion_source")
            await self.db.lead_audit_logs.create_index("lead_id")
            await self.db.lead_audit_logs.create_index("created_at")
            # Lead events timeline (event-driven conversion automation)
            try:
                await self.db.lead_events.create_index("event_key", unique=True)
            except Exception:
                pass
            await self.db.lead_events.create_index([("lead_id", 1), ("occurred_at", -1)])
            await self.db.lead_events.create_index([("client_id", 1), ("occurred_at", -1)])
            await self.db.lead_events.create_index([("subject_type", 1), ("subject_key", 1), ("occurred_at", -1)])
            await self.db.lead_events.create_index([("event_type", 1), ("occurred_at", -1)])
            # Configurable automation rules
            try:
                await self.db.lead_automation_rules.create_index("rule_key", unique=True)
            except Exception:
                pass
            await self.db.lead_automation_rules.create_index([("enabled", 1), ("event_type", 1)])
            # Canonical sequence state and send history
            try:
                await self.db.lead_sequence_state.create_index("state_id", unique=True)
            except Exception:
                pass
            await self.db.lead_sequence_state.create_index([("status", 1), ("next_run_at", 1)])
            await self.db.lead_sequence_state.create_index([("lead_id", 1), ("updated_at", -1)])
            await self.db.lead_sequence_state.create_index([("client_id", 1), ("updated_at", -1)])
            await self.db.lead_sequence_state.create_index([("subject_type", 1), ("subject_key", 1), ("updated_at", -1)])
            await self.db.lead_sequence_sends.create_index([("lead_id", 1), ("created_at", -1)])
            await self.db.lead_sequence_sends.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.lead_sequence_sends.create_index([("state_id", 1), ("step", 1)])
            try:
                await self.db.lead_sequence_sends.create_index("send_id", unique=True)
            except Exception:
                pass
            # Tenant portal: messages and certificate requests (landlord notification flow)
            await self.db.tenant_messages.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.tenant_messages.create_index("message_id", unique=True)
            await self.db.tenant_requests.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.tenant_requests.create_index("request_id", unique=True)
            await self.db.tenant_requests.create_index([("client_id", 1), ("status", 1)])
            # Contractor portal accounts (contractor_id + email login)
            await self.db.contractor_portal_accounts.create_index("email", unique=True)
            await self.db.contractor_portal_accounts.create_index("contractor_id", unique=True)
            await self.db.contractor_portal_accounts.create_index("status")
            await self.db.password_tokens.create_index([("purpose", 1), ("metadata.contractor_id", 1), ("expires_at", -1)])
            await self.db.onboarding_continuation_tokens.create_index("token_hash", unique=True)
            await self.db.onboarding_continuation_tokens.create_index("continuation_token_id", unique=True)
            await self.db.onboarding_continuation_tokens.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.onboarding_recovery_audit.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.onboarding_recovery_audit.create_index("event_id", unique=True)
            await self.db.onboarding_recovery_audit.create_index("event_type")
            await self.db.onboarding_recovery_metrics.create_index("scope", unique=True)
            await self.db.commercial_entitlement_governance.create_index(
                [("client_id", 1), ("status", 1)]
            )
            await self.db.commercial_entitlement_governance.create_index("entitlement_expiry_at")
            await self.db.commercial_entitlement_governance.create_index("entitlement_review_at")
            try:
                await self.db.commercial_entitlement_governance.create_index(
                    "governance_id", unique=True
                )
            except Exception:
                pass
            await self.db.commercial_entitlement_audit.create_index(
                [("client_id", 1), ("created_at", -1)]
            )
            await self.db.commercial_entitlement_audit.create_index("event_id", unique=True)
            await self.db.commercial_entitlement_audit.create_index("event_type")
            await self.db.commercial_entitlement_metrics.create_index("scope", unique=True)

            # OTP codes - one active per (phone_hash, purpose); no raw phone stored.
            # Drop legacy unique index (phone_e164, purpose) if present; it causes DuplicateKeyError
            # when upserting by phone_hash only (doc has no phone_e164, so multiple docs look like duplicate null).
            try:
                async for idx in self.db.otp_codes.list_indexes():
                    if idx.get("name") == "phone_e164_1_purpose_1":
                        await self.db.otp_codes.drop_index("phone_e164_1_purpose_1")
                        break
            except Exception:
                pass
            try:
                await self.db.otp_codes.create_index(
                    [("phone_hash", 1), ("purpose", 1)],
                    unique=True,
                )
            except Exception:
                pass
            await self.db.otp_codes.create_index("expires_at")
            # Step-up tokens - one-time use; validate by token_hash + user_id
            await self.db.step_up_tokens.create_index("token_hash")
            await self.db.step_up_tokens.create_index([("user_id", 1), ("expires_at", 1)])
            await self.db.admin_confirmation_tokens.create_index("token_hash", unique=True)
            await self.db.admin_confirmation_tokens.create_index([("user_id", 1), ("expires_at", 1)])

            # Intake uploads - for migration and list by session
            await self.db.intake_uploads.create_index("intake_session_id")
            await self.db.intake_uploads.create_index([("intake_session_id", 1), ("status", 1)])
            # Stripe webhook idempotency - duplicate event_id must not process twice
            try:
                await self.db.stripe_events.create_index("event_id", unique=True)
            except Exception:
                pass
            # Security monitoring (structured events, incidents, auto-response state)
            await self.db.security_events.create_index([("timestamp", -1)])
            await self.db.security_events.create_index([("event_type", 1), ("timestamp", -1)])
            await self.db.security_events.create_index([("ip", 1), ("timestamp", -1)])
            try:
                await self.db.security_incidents.create_index("incident_key", unique=True)
            except Exception:
                pass
            await self.db.security_incidents.create_index([("status", 1), ("timestamp", -1)])
            await self.db.security_locks.create_index([("expires_at", 1)])
            await self.db.security_blocks.create_index([("expires_at", 1)])
            # Normalized payments (Revenue Analytics) - idempotency and date queries
            if hasattr(self.db, "payments"):
                try:
                    await self.db.payments.create_index("stripe_event_id", unique=True, sparse=True)
                except Exception:
                    pass
                await self.db.payments.create_index("created_at")
                await self.db.payments.create_index([("client_id", 1), ("created_at", -1)])
                await self.db.payments.create_index("stripe_charge_id", sparse=True)
                await self.db.payments.create_index("stripe_invoice_id", sparse=True)
            # Canonical subscription payment ledger (paid invoices; idempotent by stripe_invoice_id)
            try:
                await self.db.subscription_payment_ledger.create_index(
                    "stripe_invoice_id", unique=True, sparse=True
                )
            except Exception:
                pass
            try:
                await self.db.subscription_payment_ledger.create_index(
                    [("client_id", 1), ("paid_at", -1)]
                )
            except Exception:
                pass
            try:
                await self.db.subscription_payment_ledger.create_index("source_event_id", sparse=True)
            except Exception:
                pass
            # Subscription operational events (renewal ops visibility; deduplicated)
            if hasattr(self.db, "subscription_operational_events"):
                try:
                    await self.db.subscription_operational_events.create_index(
                        "dedupe_key", unique=True, sparse=True
                    )
                except Exception:
                    pass
                try:
                    await self.db.subscription_operational_events.create_index(
                        [("occurred_at", -1)]
                    )
                except Exception:
                    pass
                try:
                    await self.db.subscription_operational_events.create_index(
                        [("client_id", 1), ("occurred_at", -1)]
                    )
                except Exception:
                    pass
                try:
                    await self.db.subscription_operational_events.create_index("digest_date", sparse=True)
                except Exception:
                    pass
            # Account lifecycle platform events (ILP-9 authoritative catalogue)
            if hasattr(self.db, "account_lifecycle_events"):
                try:
                    await self.db.account_lifecycle_events.create_index(
                        "idempotency_key", unique=True, sparse=True
                    )
                except Exception:
                    pass
                try:
                    await self.db.account_lifecycle_events.create_index(
                        [("client_id", 1), ("occurred_at", -1)]
                    )
                except Exception:
                    pass
                try:
                    await self.db.account_lifecycle_events.create_index(
                        [("event_type", 1), ("occurred_at", -1)]
                    )
                except Exception:
                    pass
            # MRR snapshots for NRR (Executive Overview)
            if hasattr(self.db, "mrr_snapshots"):
                try:
                    await self.db.mrr_snapshots.create_index("period", unique=True)
                except Exception:
                    pass
            # Provisioning jobs - idempotency by checkout_session_id
            await self.db.provisioning_jobs.create_index("job_id", unique=True)
            try:
                await self.db.provisioning_jobs.create_index("checkout_session_id", unique=True)
            except Exception:
                pass
            await self.db.provisioning_jobs.create_index("client_id")
            await self.db.provisioning_jobs.create_index("status")
            # Analytics events - conversion funnel and operational metrics (passive logging)
            await self.db.analytics_events.create_index([("event", 1), ("ts", -1)])
            await self.db.analytics_events.create_index([("client_id", 1), ("ts", -1)])
            await self.db.analytics_events.create_index([("lead_id", 1), ("ts", -1)])
            await self.db.analytics_events.create_index("ts")
            try:
                await self.db.analytics_events.create_index("idempotency_key", unique=True, sparse=True)
            except Exception:
                pass
            # Requirements catalog (data-driven compliance definitions)
            await self.db.requirements_catalog.create_index("code", unique=True)
            await self.db.requirements_catalog.create_index("category")
            await self.db.requirements_catalog.create_index("criticality")
            # Requirements (instance state) - ensure efficient lookups
            await self.db.requirements.create_index([("client_id", 1), ("property_id", 1)])
            await self.db.requirements.create_index([("client_id", 1), ("status", 1)])
            await self.db.requirements.create_index([("property_id", 1), ("requirement_type", 1)])
            await self.db.automation_status.create_index("client_id", unique=True)
            # Assistant chat (Compliance Vault Assistant)
            await self.db.assistant_conversations.create_index([("client_id", 1), ("last_activity_at", -1)])
            await self.db.assistant_conversations.create_index("conversation_id", unique=True)
            await self.db.assistant_messages.create_index([("conversation_id", 1), ("created_at", 1)])
            await self.db.assistant_messages.create_index([("client_id", 1), ("created_at", -1)])
            # Help Assistant feedback (doc-grounded assistant)
            await self.db.assistant_feedback.create_index([("user_id", 1), ("created_at", -1)])
            await self.db.assistant_feedback.create_index("scope")
            # Admin compliance requirement registry drafts (Mongo only; planner unchanged)
            try:
                await self.db.compliance_requirement_registry_drafts.create_index("entry_id", unique=True)
            except Exception:
                pass
            try:
                await self.db.compliance_requirement_registry_drafts.create_index(
                    [("canonical_code", 1), ("scope_key", 1)],
                    unique=True,
                    name="idx_compliance_registry_code_scope",
                )
            except Exception:
                pass
            try:
                await self.db.compliance_requirement_registry_drafts.create_index([("updated_at", -1)])
            except Exception:
                pass
            # Registry publish queue + active published snapshot (planner overlay source)
            try:
                await self.db.compliance_registry_publish_queue.create_index("queue_id", unique=True)
            except Exception:
                pass
            try:
                await self.db.compliance_registry_publish_queue.create_index([("status", 1), ("updated_at", -1)])
            except Exception:
                pass
            try:
                await self.db.compliance_requirement_registry_published.create_index(
                    "singleton_key", unique=True, name="idx_compliance_registry_published_singleton"
                )
            except Exception:
                pass
            try:
                await self.db.compliance_requirement_registry_published_history.create_index(
                    "published_line_version", unique=True, name="idx_registry_published_history_line_version"
                )
            except Exception:
                pass
            try:
                await self.db.compliance_requirement_registry_published_history.create_index(
                    [("recorded_at", -1)],
                    name="idx_registry_published_history_recorded_at",
                )
            except Exception:
                pass
            # Agreement management (CVP service agreements; not legal_content)
            try:
                await self.db.agreement_templates.create_index("code", unique=True)
                await self.db.agreement_templates.create_index("template_id", unique=True)
            except Exception:
                pass
            try:
                await self.db.agreement_template_versions.create_index("version_id", unique=True)
                await self.db.agreement_template_versions.create_index([("template_id", 1), ("version_number", 1)])
            except Exception:
                pass
            try:
                await self.db.agreement_acceptances.create_index("acceptance_id", unique=True)
                await self.db.agreement_acceptances.create_index("client_id")
                await self.db.agreement_acceptances.create_index("stripe_checkout_session_id", sparse=True)
            except Exception:
                pass
            try:
                await self.db.issued_agreements.create_index("issued_id", unique=True)
                await self.db.issued_agreements.create_index("client_id")
                await self.db.issued_agreements.create_index("acceptance_id")
                await self.db.issued_agreements.create_index(
                    [("client_id", 1), ("stripe_event_id", 1)], name="idx_issued_agreements_client_event"
                )
            except Exception:
                pass
            try:
                await self.db.system_document_settings.create_index("settings_id", unique=True)
            except Exception:
                pass
            try:
                from services.agreement_seed import ensure_default_agreement_assets

                await ensure_default_agreement_assets()
            except Exception as seed_err:
                logger.warning("Agreement seed skipped or failed: %s", seed_err)

            try:
                from services.discovery.discovery_indexes import ensure_discovery_indexes

                await ensure_discovery_indexes(self.db)
            except Exception as disc_idx_err:
                logger.warning("Discovery index creation note: %s", disc_idx_err)

            await self._seed_requirements_catalog()
            logger.info("MongoDB indexes created/verified")
        except Exception as e:
            # Indexes may already exist, log but don't fail
            logger.warning(f"Index creation note: {e}")

    async def _seed_requirements_catalog(self):
        """Seed requirements_catalog for data-driven compliance (idempotent by code)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        items = [
            {"code": "gas_safety", "title": "Gas Safety (CP12)", "description": "Annual gas safety inspection", "category": "SAFETY", "criticality": "HIGH", "weight": 18, "expiry_type": "EXPIRING", "validity_days": 365, "expiring_windows_days": 30, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": {"all": [{"field": "has_gas_supply", "op": "==", "value": True}]}, "default_actions": [], "help_text": "Required for properties with gas.", "updated_at": now},
            {"code": "eicr", "title": "EICR", "description": "Electrical Installation Condition Report", "category": "ELECTRICAL", "criticality": "HIGH", "weight": 16, "expiry_type": "EXPIRING", "validity_days": 1825, "expiring_windows_days": 60, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Typically every 5 years.", "updated_at": now},
            {"code": "epc", "title": "EPC", "description": "Energy Performance Certificate", "category": "ENERGY", "criticality": "HIGH", "weight": 8, "expiry_type": "EXPIRING", "validity_days": 3650, "expiring_windows_days": 90, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Minimum E for rental.", "updated_at": now},
            {"code": "smoke_alarms", "title": "Smoke Alarms", "description": "Smoke alarms required", "category": "FIRE", "criticality": "HIGH", "weight": 8, "expiry_type": "NON_EXPIRING", "validity_days": None, "expiring_windows_days": None, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Smoke alarms on each storey.", "updated_at": now},
            {"code": "co_alarms", "title": "CO Alarms", "description": "Carbon monoxide alarms where solid fuel", "category": "FIRE", "criticality": "HIGH", "weight": 6, "expiry_type": "NON_EXPIRING", "validity_days": None, "expiring_windows_days": None, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Where applicable.", "updated_at": now},
            {"code": "deposit_pi", "title": "Deposit Protection", "description": "Deposit in approved scheme", "category": "TENANCY", "criticality": "HIGH", "weight": 10, "expiry_type": "EVENT_BASED", "validity_days": None, "expiring_windows_days": None, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Prescribed information to tenant.", "updated_at": now},
            {"code": "right_to_rent", "title": "Right to Rent", "description": "Right to rent checks", "category": "TENANCY", "criticality": "HIGH", "weight": 7, "expiry_type": "EVENT_BASED", "validity_days": None, "expiring_windows_days": None, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Check and retain copies.", "updated_at": now},
            {"code": "how_to_rent", "title": "How to Rent", "description": "How to Rent guide to tenant", "category": "TENANCY", "criticality": "MED", "weight": 5, "expiry_type": "EVENT_BASED", "validity_days": None, "expiring_windows_days": None, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Latest version.", "updated_at": now},
            {"code": "tenancy_agreement", "title": "Tenancy Agreement", "description": "Written tenancy agreement", "category": "TENANCY", "criticality": "MED", "weight": 6, "expiry_type": "EVENT_BASED", "validity_days": None, "expiring_windows_days": None, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Signed agreement.", "updated_at": now},
            {"code": "hmo_license", "title": "HMO Licence", "description": "HMO licence where required", "category": "REGULATORY", "criticality": "HIGH", "weight": 18, "expiry_type": "EXPIRING", "validity_days": 1825, "expiring_windows_days": 90, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": {"any": [{"field": "is_hmo", "op": "==", "value": True}, {"field": "licence_required", "op": "==", "value": "YES"}]}, "default_actions": [], "help_text": "Mandatory for licensable HMO.", "updated_at": now},
            {"code": "fire_risk_assessment", "title": "Fire Risk Assessment", "description": "Fire risk assessment (HMO)", "category": "FIRE", "criticality": "HIGH", "weight": 6, "expiry_type": "EXPIRING", "validity_days": 365, "expiring_windows_days": 30, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": {"field": "is_hmo", "op": "==", "value": True}, "default_actions": [], "help_text": "Required for HMO.", "updated_at": now},
            {"code": "legionella", "title": "Legionella Risk Assessment", "description": "Legionella risk assessment", "category": "HEALTH", "criticality": "LOW", "weight": 4, "expiry_type": "EXPIRING", "validity_days": 730, "expiring_windows_days": 60, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Water system risk.", "updated_at": now},
            {"code": "portable_appliance_test", "title": "Portable Appliance Testing (PAT)", "description": "Portable Appliance Testing (PAT)", "category": "ELECTRICAL", "criticality": "MED", "weight": 5, "expiry_type": "EXPIRING", "validity_days": 365, "expiring_windows_days": 30, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "PAT certificate where applicable.", "updated_at": now},
            {"code": "fire_alarm", "title": "Fire Alarm Inspection", "description": "Fire Alarm Inspection", "category": "FIRE", "criticality": "HIGH", "weight": 8, "expiry_type": "EXPIRING", "validity_days": 365, "expiring_windows_days": 30, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Annual fire alarm inspection.", "updated_at": now},
            {"code": "fire_detection", "title": "Fire Detection Systems", "description": "Fire detection / alarm system inspection (canonical)", "category": "FIRE", "criticality": "HIGH", "weight": 8, "expiry_type": "EXPIRING", "validity_days": 365, "expiring_windows_days": 30, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Aligned with contractor capability routing (fire_detection).", "updated_at": now},
        ]
        for item in items:
            await self.db.requirements_catalog.update_one(
                {"code": item["code"]},
                {"$set": item},
                upsert=True,
            )
        logger.info("Requirements catalog seeded/updated")

    async def _seed_notification_templates(self):
        """Seed notification_templates for orchestrator (idempotent upsert by template_key)."""
        from datetime import datetime, timezone

        from notification_template_seed_definitions import notification_template_seed_rows_with_timestamps

        now = datetime.now(timezone.utc)
        templates = notification_template_seed_rows_with_timestamps(now)
        for t in templates:
            await self.db.notification_templates.update_one(
                {"template_key": t["template_key"]},
                {"$set": t},
                upsert=True,
            )
        logger.info("Notification templates seeded/updated")

    async def _seed_communication_collections(self):
        """Indexes + notification rows + default admin communication templates (idempotent)."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        try:
            await self.db.communication_messages.create_index("communication_id", unique=True)
            await self.db.communication_messages.create_index([("created_at", -1)])
            await self.db.communication_messages.create_index([("message_type", 1), ("created_at", -1)])
            await self.db.communication_messages.create_index([("sent_by_portal_user_id", 1), ("created_at", -1)])
            await self.db.communication_messages.create_index([("status", 1), ("created_at", -1)])
            await self.db.communication_messages.create_index([("status", 1), ("scheduled_at", 1)])
            await self.db.communication_deliveries.create_index("delivery_id", unique=True)
            await self.db.communication_deliveries.create_index([("communication_id", 1), ("client_id", 1)])
            await self.db.communication_templates.create_index("template_id", unique=True)
            await self.db.system_banners.create_index("banner_id", unique=True)
            await self.db.system_banners.create_index([("active", 1), ("start_at", -1)])
            await self.db.system_banner_dismissals.create_index(
                [("portal_user_id", 1), ("banner_id", 1)], unique=True
            )
        except Exception as e:
            logger.warning("communication collections index create: %s", e)

        from notification_template_seed_definitions import (
            admin_client_communication_notification_seed_rows_with_timestamps,
        )

        admin_comm_templates = admin_client_communication_notification_seed_rows_with_timestamps(now)
        for t in admin_comm_templates:
            await self.db.notification_templates.update_one(
                {"template_key": t["template_key"]},
                {"$set": t},
                upsert=True,
            )

        support = os.getenv("EMAIL_REPLY_TO") or os.getenv("SUPPORT_EMAIL") or "support@pleerityenterprise.co.uk"
        defaults = [
            {
                "template_id": "TPL-SERVICE-DISRUPTION",
                "name": "Service disruption notice",
                "description": "Client-facing notice when impact is confirmed.",
                "default_message_type": "INCIDENT",
                "subject_template": "Service disruption — {{incident_title}}",
                "body_template": "<p>Hello,</p><p>We are experiencing a service disruption affecting Compliance Vault Pro. {{incident_title}}</p><p>Our team is working to restore normal service. We will update you as we learn more.</p><p>If you need urgent help, contact us at {{support_email}}.</p>",
                "in_app_title_template": "Service disruption",
                "in_app_body_template": "We are investigating a service issue. Details have been emailed to you.",
                "banner_text_template": "Service disruption — we are working on a fix.",
                "is_system_seed": True,
                "updated_at": now,
            },
            {
                "template_id": "TPL-INVESTIGATING",
                "name": "We are investigating an issue",
                "description": "Early incident comms before root cause is known.",
                "default_message_type": "INCIDENT",
                "subject_template": "We are investigating an issue",
                "body_template": "<p>Hello,</p><p>We have detected an issue that may affect your access to Compliance Vault Pro. Our engineering team is investigating.</p><p>You do not need to take any action right now. We will email you again when we have more information.</p><p>Questions: {{support_email}}</p>",
                "in_app_title_template": "Issue under investigation",
                "in_app_body_template": "We are investigating a potential service issue. Check your email for details.",
                "banner_text_template": "We are investigating a service issue — updates to follow.",
                "is_system_seed": True,
                "updated_at": now,
            },
            {
                "template_id": "TPL-ISSUE-RESOLVED",
                "name": "Issue resolved",
                "description": "Resolution notice after an incident.",
                "default_message_type": "SERVICE_UPDATE",
                "subject_template": "Resolved: {{incident_title}}",
                "body_template": "<p>Hello,</p><p>The issue we reported earlier (<strong>{{incident_title}}</strong>) is now resolved. Service should be operating normally.</p><p>If you still see problems, please reply to this email or contact {{support_email}}.</p>",
                "in_app_title_template": "Issue resolved",
                "in_app_body_template": "The reported service issue is resolved.",
                "banner_text_template": "",
                "is_system_seed": True,
                "updated_at": now,
            },
            {
                "template_id": "TPL-PLANNED-MAINTENANCE",
                "name": "Planned maintenance",
                "description": "Scheduled maintenance window.",
                "default_message_type": "MAINTENANCE_NOTICE",
                "subject_template": "Planned maintenance — {{incident_title}}",
                "body_template": "<p>Hello,</p><p>We will perform planned maintenance: <strong>{{incident_title}}</strong>.</p><p>During the window you may experience brief interruptions. We aim to complete work as quickly as possible.</p><p>Contact: {{support_email}}</p>",
                "in_app_title_template": "Planned maintenance",
                "in_app_body_template": "Scheduled maintenance may briefly affect the portal. See email for times and scope.",
                "banner_text_template": "Planned maintenance in progress — short interruptions possible.",
                "is_system_seed": True,
                "updated_at": now,
            },
            {
                "template_id": "TPL-ACCOUNT-SUPPORT",
                "name": "Account-specific support message",
                "description": "Direct message regarding a single client account.",
                "default_message_type": "DIRECT_SUPPORT_MESSAGE",
                "subject_template": "Regarding your account ({{customer_reference}})",
                "body_template": "<p>Hello {{client_name}},</p><p>We are writing regarding your Compliance Vault Pro account.</p><p>[Describe the situation and any actions required.]</p><p>If anything is unclear, reply to this email or contact {{support_email}}.</p>",
                "in_app_title_template": "Account update",
                "in_app_body_template": "We sent you an important account message by email.",
                "banner_text_template": "",
                "is_system_seed": True,
                "updated_at": now,
            },
        ]
        for doc in defaults:
            doc.setdefault(
                "variables_hint",
                ["client_name", "plan_name", "incident_title", "support_email", "portal_link", "customer_reference"],
            )
            doc["support_email_placeholder"] = support
            insert_doc = {**doc, "created_at": now, "updated_at": now}
            await self.db.communication_templates.update_one(
                {"template_id": doc["template_id"]},
                {"$setOnInsert": insert_doc},
                upsert=True,
            )
        logger.info("Communication collections / templates seeded")

# Global database instance
database = Database()

@asynccontextmanager
async def get_db_context():
    """Context manager for standalone scripts to access the database.
    
    Usage in scripts:
        async with get_db_context() as db:
            # db is now connected and ready to use
            await db.clients.find_one(...)
    """
    client = None
    try:
        mongo_url = os.environ['MONGO_URL']
        db_name = os.environ['DB_NAME']
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        # Verify connection
        await db.command("ping")
        logger.info(f"Script connected to MongoDB: {db_name}")
        yield db
    finally:
        if client:
            client.close()
            logger.info("Script MongoDB connection closed")
