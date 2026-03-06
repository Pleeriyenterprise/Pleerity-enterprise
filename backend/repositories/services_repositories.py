"""
Typed repositories for the four services collections (Motor + Pydantic schemas).

Usage: from repositories.services_repositories import order_repository, workflow_events_repository
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import database

from models.services_models import (
    AuditLogSchema,
    DeliverySchema,
    DocumentPackDefinitionSchema,
    DocumentPackItemSchema,
    DraftStatus,
    GeneratedDocumentSchema,
    GenerationRunSchema,
    IntakeDraftSchema,
    OrderSchema,
    OrderStatus,
    PackBundleSchema,
    PromptTemplateSchema,
    ServiceSchema,
    WorkflowEventSchema,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _omit_id(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if k != "_id"}


# =============================================================================
# Services (service_catalogue_v2)
# =============================================================================

class ServiceRepository:
    COLLECTION = "service_catalogue_v2"

    def _db(self):
        return database.get_db()[self.COLLECTION]

    async def get_by_code(self, service_code: str) -> Optional[Dict[str, Any]]:
        doc = await self._db().find_one(
            {"service_code": service_code, "deleted_at": None},
            {"_id": 0}
        )
        return doc

    async def get_active_by_code(self, service_code: str) -> Optional[Dict[str, Any]]:
        doc = await self._db().find_one(
            {"service_code": service_code, "active": True, "deleted_at": None},
            {"_id": 0}
        )
        return doc

    async def list_active(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        q = {"active": True, "deleted_at": None}
        if category:
            q["category"] = category
        cursor = self._db().find(q, {"_id": 0}).sort("display_order", 1)
        return await cursor.to_list(length=None)

    async def insert(self, service: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a service (e.g. seed/catalogue). Sets timestamps and excludes soft-deleted by default."""
        service.setdefault("created_at", _now())
        service.setdefault("updated_at", _now())
        await self._db().insert_one(service)
        return _omit_id(service)


# =============================================================================
# Intake drafts (intake_drafts)
# =============================================================================

class IntakeDraftRepository:
    COLLECTION = "intake_drafts"

    def _db(self):
        return database.get_db()[self.COLLECTION]

    async def get_by_id(self, draft_id: str) -> Optional[Dict[str, Any]]:
        doc = await self._db().find_one({"draft_id": draft_id}, {"_id": 0})
        return _omit_id(doc) if doc else None

    async def get_by_ref(self, draft_ref: str) -> Optional[Dict[str, Any]]:
        doc = await self._db().find_one({"draft_ref": draft_ref}, {"_id": 0})
        return _omit_id(doc) if doc else None

    async def insert(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        draft.setdefault("created_at", _now())
        draft.setdefault("updated_at", _now())
        await self._db().insert_one(draft)
        return _omit_id(draft)

    async def update_status(
        self,
        draft_id: str,
        status: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> bool:
        update = {"$set": {"status": status, "updated_at": _now(), **(extra or {})}}
        r = await self._db().update_one({"draft_id": draft_id}, update)
        return r.modified_count > 0


# =============================================================================
# Orders (orders) — immutable, no hard delete
# =============================================================================

class OrderRepository:
    COLLECTION = "orders"

    def _db(self):
        return database.get_db()[self.COLLECTION]

    async def get_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        doc = await self._db().find_one({"order_id": order_id}, {"_id": 0})
        return _omit_id(doc) if doc else None

    async def get_by_ref(self, order_ref: str) -> Optional[Dict[str, Any]]:
        doc = await self._db().find_one({"order_ref": order_ref}, {"_id": 0})
        return _omit_id(doc) if doc else None

    async def get_by_source_draft_id(self, draft_id: str) -> Optional[Dict[str, Any]]:
        doc = await self._db().find_one({"source_draft_id": draft_id}, {"_id": 0})
        return _omit_id(doc) if doc else None

    async def get_by_stripe_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        doc = await self._db().find_one(
            {"pricing.stripe_checkout_session_id": session_id},
            {"_id": 0}
        )
        return _omit_id(doc) if doc else None

    async def insert(self, order: Dict[str, Any]) -> Dict[str, Any]:
        order.setdefault("created_at", _now())
        order.setdefault("updated_at", _now())
        await self._db().insert_one(order)
        return _omit_id(order)

    async def update_status(
        self,
        order_id: str,
        status: str,
        workflow_state: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> bool:
        set_fields = {"status": status, "updated_at": _now()}
        if workflow_state is not None:
            set_fields["workflow_state"] = workflow_state
        if extra:
            set_fields.update(extra)
        r = await self._db().update_one({"order_id": order_id}, {"$set": set_fields})
        return r.modified_count > 0

    async def list(
        self,
        filter_query: Optional[Dict[str, Any]] = None,
        sort: Optional[List[tuple]] = None,
        skip: int = 0,
        limit: int = 100,
        projection: Optional[Dict[str, int]] = None,
    ) -> List[Dict[str, Any]]:
        """List orders with optional filter, sort, pagination. No delete — orders are immutable."""
        q = filter_query or {}
        proj = projection if projection is not None else {"_id": 0}
        cursor = self._db().find(q, proj)
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count(self, filter_query: Optional[Dict[str, Any]] = None) -> int:
        """Count orders matching filter."""
        q = filter_query or {}
        return await self._db().count_documents(q)


# =============================================================================
# Prompt templates (prompt_templates)
# =============================================================================

class PromptTemplateRepository:
    COLLECTION = "prompt_templates"

    def _db(self):
        return database.get_db()[self.COLLECTION]

    async def get_by_id(self, template_id: str) -> Optional[Dict[str, Any]]:
        doc = await self._db().find_one({"template_id": template_id, "deleted_at": None}, {"_id": 0})
        return _omit_id(doc) if doc else None

    async def list_by_service(self, service_code: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        q = {"service_code": service_code, "deleted_at": None}
        if status:
            q["status"] = status
        cursor = self._db().find(q, {"_id": 0}).sort([("doc_type", 1), ("version", -1)])
        return await cursor.to_list(length=None)


# =============================================================================
# Generation runs (generation_runs)
# =============================================================================

class GenerationRunRepository:
    COLLECTION = "generation_runs"

    def _db(self):
        return database.get_db()[self.COLLECTION]

    async def insert(self, run: Dict[str, Any]) -> Dict[str, Any]:
        run.setdefault("run_id", run.get("run_id") or str(uuid.uuid4()))
        run.setdefault("created_at", _now())
        run.setdefault("updated_at", _now())
        await self._db().insert_one(run)
        return _omit_id(run)

    async def get_by_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        doc = await self._db().find_one({"run_id": run_id}, {"_id": 0})
        return _omit_id(doc) if doc else None

    async def list_by_order(self, order_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self._db().find({"order_id": order_id}, {"_id": 0}).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def update_status(
        self,
        run_id: str,
        status: str,
        completed_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        set_fields = {"status": status, "updated_at": _now()}
        if completed_at is not None:
            set_fields["completed_at"] = completed_at
        if error_message is not None:
            set_fields["error_message"] = error_message
        r = await self._db().update_one({"run_id": run_id}, {"$set": set_fields})
        return r.modified_count > 0


# =============================================================================
# Document pack items (document_pack_items) — versioned
# =============================================================================

class DocumentPackItemRepository:
    COLLECTION = "document_pack_items"

    def _db(self):
        return database.get_db()[self.COLLECTION]

    async def insert(self, item: Dict[str, Any]) -> Dict[str, Any]:
        item.setdefault("created_at", _now())
        item.setdefault("updated_at", _now())
        await self._db().insert_one(item)
        return _omit_id(item)

    async def get_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        doc = await self._db().find_one({"item_id": item_id}, {"_id": 0})
        return _omit_id(doc) if doc else None

    async def list_by_order(self, order_id: str) -> List[Dict[str, Any]]:
        cursor = self._db().find({"order_id": order_id}, {"_id": 0}).sort("canonical_index", 1)
        return await cursor.to_list(length=None)

    async def update_status(self, item_id: str, status: str, extra: Optional[Dict[str, Any]] = None) -> bool:
        set_fields = {"status": status, "updated_at": _now(), **(extra or {})}
        r = await self._db().update_one({"item_id": item_id}, {"$set": set_fields})
        return r.modified_count > 0


# =============================================================================
# Generated documents (generated_documents) — versioned, never overwrite
# =============================================================================

class GeneratedDocumentRepository:
    COLLECTION = "generated_documents"

    def _db(self):
        return database.get_db()[self.COLLECTION]

    async def insert(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        doc.setdefault("created_at", _now())
        doc.setdefault("updated_at", _now())
        await self._db().insert_one(doc)
        return _omit_id(doc)

    async def get_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        d = await self._db().find_one({"document_id": document_id}, {"_id": 0})
        return _omit_id(d) if d else None

    async def list_by_order(self, order_id: str) -> List[Dict[str, Any]]:
        cursor = self._db().find({"order_id": order_id}, {"_id": 0}).sort("version", 1)
        return await cursor.to_list(length=None)


# =============================================================================
# Document pack definitions (document_pack_definitions)
# =============================================================================

class DocumentPackDefinitionRepository:
    COLLECTION = "document_pack_definitions"

    def _db(self):
        return database.get_db()[self.COLLECTION]

    async def get_by_key(self, doc_key: str) -> Optional[Dict[str, Any]]:
        doc = await self._db().find_one({"doc_key": doc_key, "deleted_at": None}, {"_id": 0})
        return _omit_id(doc) if doc else None

    async def list_by_tier(self, pack_tier: str) -> List[Dict[str, Any]]:
        cursor = self._db().find(
            {"pack_tier": pack_tier, "deleted_at": None},
            {"_id": 0}
        ).sort("canonical_index", 1)
        return await cursor.to_list(length=None)

    async def insert(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        definition.setdefault("created_at", _now())
        definition.setdefault("updated_at", _now())
        await self._db().insert_one(definition)
        return _omit_id(definition)


# =============================================================================
# Pack bundles (pack_bundles)
# =============================================================================

class PackBundleRepository:
    COLLECTION = "pack_bundles"

    def _db(self):
        return database.get_db()[self.COLLECTION]

    async def insert(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        bundle.setdefault("created_at", _now())
        await self._db().insert_one(bundle)
        return _omit_id(bundle)

    async def get_by_id(self, bundle_id: str) -> Optional[Dict[str, Any]]:
        doc = await self._db().find_one({"bundle_id": bundle_id}, {"_id": 0})
        return _omit_id(doc) if doc else None

    async def get_latest_by_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        doc = await self._db().find_one(
            {"order_id": order_id},
            {"_id": 0},
            sort=[("bundle_version", -1)],
        )
        return _omit_id(doc) if doc else None

    async def list_by_order(self, order_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        cursor = self._db().find({"order_id": order_id}, {"_id": 0}).sort("bundle_version", -1).limit(limit)
        return await cursor.to_list(length=limit)


# =============================================================================
# Workflow events (workflow_events) — every state change
# =============================================================================

class WorkflowEventRepository:
    COLLECTION = "workflow_events"

    def _db(self):
        return database.get_db()[self.COLLECTION]

    async def insert(self, event: Dict[str, Any]) -> Dict[str, Any]:
        event.setdefault("event_id", event.get("event_id") or str(uuid.uuid4()))
        event.setdefault("created_at", _now())
        await self._db().insert_one(event)
        return _omit_id(event)

    async def list_by_order(self, order_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        cursor = self._db().find({"order_id": order_id}, {"_id": 0}).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)


# =============================================================================
# Deliveries (deliveries)
# =============================================================================

class DeliveryRepository:
    COLLECTION = "deliveries"

    def _db(self):
        return database.get_db()[self.COLLECTION]

    async def insert(self, delivery: Dict[str, Any]) -> Dict[str, Any]:
        delivery.setdefault("delivery_id", delivery.get("delivery_id") or str(uuid.uuid4()))
        delivery.setdefault("created_at", _now())
        await self._db().insert_one(delivery)
        return _omit_id(delivery)

    async def get_by_id(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        doc = await self._db().find_one({"delivery_id": delivery_id}, {"_id": 0})
        return _omit_id(doc) if doc else None

    async def list_by_order(self, order_id: str) -> List[Dict[str, Any]]:
        cursor = self._db().find({"order_id": order_id}, {"_id": 0}).sort("created_at", -1)
        return await cursor.to_list(length=None)

    async def update_status(self, delivery_id: str, status: str, completed_at: Optional[datetime] = None) -> bool:
        set_fields = {"status": status}
        if completed_at is not None:
            set_fields["completed_at"] = completed_at
        r = await self._db().update_one({"delivery_id": delivery_id}, {"$set": set_fields})
        return r.modified_count > 0

    async def find_by_postmark_message_id(self, postmark_message_id: str) -> Optional[Dict[str, Any]]:
        """Find delivery record by Postmark MessageID (for webhook handling)."""
        doc = await self._db().find_one(
            {"$or": [{"postmark_message_id": postmark_message_id}, {"provider_message_id": postmark_message_id}]},
            {"_id": 0},
        )
        return _omit_id(doc) if doc else None

    async def update_delivery_status(
        self,
        delivery_id: str,
        status: str,
        delivered_at: Optional[datetime] = None,
        bounced_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update delivery record with webhook status (DELIVERED, BOUNCED)."""
        set_fields = {"status": status}
        if delivered_at is not None:
            set_fields["delivered_at"] = delivered_at
            set_fields["completed_at"] = delivered_at
        if bounced_at is not None:
            set_fields["bounced_at"] = bounced_at
            set_fields["completed_at"] = bounced_at
        if error_message is not None:
            set_fields["error_message"] = error_message
        r = await self._db().update_one({"delivery_id": delivery_id}, {"$set": set_fields})
        return r.modified_count > 0


# =============================================================================
# Audit logs (audit_logs) — existing; read + insert only
# =============================================================================

class AuditLogRepository:
    COLLECTION = "audit_logs"

    def _db(self):
        return database.get_db()[self.COLLECTION]

    async def insert(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        entry.setdefault("timestamp", _now())
        await self._db().insert_one(entry)
        return _omit_id(entry)

    async def list_by_client(self, client_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self._db().find({"client_id": client_id}, {"_id": 0}).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def list_by_resource(self, resource_type: str, resource_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self._db().find(
            {"resource_type": resource_type, "resource_id": resource_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)


# =============================================================================
# Singleton instances
# =============================================================================

service_repository = ServiceRepository()
intake_draft_repository = IntakeDraftRepository()
order_repository = OrderRepository()
prompt_template_repository = PromptTemplateRepository()
generation_run_repository = GenerationRunRepository()
document_pack_item_repository = DocumentPackItemRepository()
generated_document_repository = GeneratedDocumentRepository()
document_pack_definition_repository = DocumentPackDefinitionRepository()
pack_bundle_repository = PackBundleRepository()
workflow_event_repository = WorkflowEventRepository()
delivery_repository = DeliveryRepository()
audit_log_repository = AuditLogRepository()
