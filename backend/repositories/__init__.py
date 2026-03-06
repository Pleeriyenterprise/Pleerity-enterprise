# Typed repositories for the four services (Motor + Pydantic schemas).
# Collections: service_catalogue_v2, intake_drafts, orders, prompt_templates,
# generation_runs, document_pack_items, generated_documents, document_pack_definitions,
# workflow_events, deliveries, audit_logs.

from repositories.services_repositories import (
    service_repository,
    intake_draft_repository,
    order_repository,
    prompt_template_repository,
    generation_run_repository,
    document_pack_item_repository,
    generated_document_repository,
    document_pack_definition_repository,
    workflow_event_repository,
    delivery_repository,
    audit_log_repository,
)

__all__ = [
    "service_repository",
    "intake_draft_repository",
    "order_repository",
    "prompt_template_repository",
    "generation_run_repository",
    "document_pack_item_repository",
    "generated_document_repository",
    "document_pack_definition_repository",
    "workflow_event_repository",
    "delivery_repository",
    "audit_log_repository",
]
