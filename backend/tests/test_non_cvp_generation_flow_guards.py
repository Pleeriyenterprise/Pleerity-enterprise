import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)


def test_prompt_bridge_uses_deterministic_legacy_fallback_for_aliased_service():
    from services.gpt_prompt_registry import PromptDefinition, PromptType
    from services.prompt_manager_bridge import PromptManagerBridge

    bridge = PromptManagerBridge()
    legacy_prompt = PromptDefinition(
        prompt_id="AI_TOOLS_MASTER",
        prompt_type=PromptType.MASTER,
        service_code="AI_TOOLS",
        name="AI Tools",
        description="legacy",
        system_prompt="sys",
        user_prompt_template="tmpl",
        output_schema={"summary": "string"},
    )

    mock_db = MagicMock()
    prompts_collection = MagicMock()
    prompts_collection.count_documents = AsyncMock(return_value=0)
    prompts_collection.find_one = AsyncMock(return_value=None)
    mock_db.__getitem__.return_value = prompts_collection

    with (
        patch("services.prompt_manager_bridge.database.get_db", return_value=mock_db),
        patch("services.prompt_manager_bridge.get_prompt_for_service") as mock_legacy_lookup,
    ):
        # No prompt for original/alias; only mapped legacy key resolves.
        mock_legacy_lookup.side_effect = lambda code: legacy_prompt if code == "AI_TOOLS" else None
        prompt_def, prompt_info = asyncio.run(
            bridge.get_prompt_for_service(service_code="AI_TOOL_REPORT", doc_type="AI_TOOL_REPORT")
        )

    assert prompt_def is legacy_prompt
    assert prompt_info is not None
    assert prompt_info.source == "legacy_registry"
    assert prompt_info.service_code == "AI_TOOLS"
    assert any(call.args[0] == "AI_TOOLS" for call in mock_legacy_lookup.call_args_list)


def test_orchestration_generate_uses_persisted_intake_not_request_payload():
    from routes.orchestration import GenerateDocumentRequest, generate_documents
    from services.document_orchestrator import OrchestrationStatus

    canonical_intake = {"business_description": "from-db"}
    request_payload = {"business_description": "from-request"}

    result_obj = SimpleNamespace(
        success=True,
        order_id="ord-1",
        service_code="AI_WF_BLUEPRINT",
        version=1,
        status=OrchestrationStatus.REVIEW_PENDING,
        structured_output={"summary": "ok"},
        rendered_documents={"docx": {"filename": "a.docx"}, "pdf": {"filename": "a.pdf"}},
        validation_issues=[],
        data_gaps=[],
        execution_time_ms=10,
        prompt_tokens=1,
        completion_tokens=2,
    )

    request = GenerateDocumentRequest(order_id="ord-1", intake_data=request_payload, force=False)

    with (
        patch("routes.orchestration._load_order_intake_payload", new_callable=AsyncMock, return_value=canonical_intake),
        patch("routes.orchestration.document_orchestrator.execute_full_pipeline", new_callable=AsyncMock, return_value=result_obj) as mock_exec,
    ):
        response = asyncio.run(generate_documents(request=request, current_user={"email": "admin@test.com"}))

    assert response["success"] is True
    assert mock_exec.await_count == 1
    kwargs = mock_exec.await_args.kwargs
    assert kwargs["intake_data"] == canonical_intake
    assert kwargs["intake_data"] != request_payload


def test_template_context_does_not_include_raw_intake_fields():
    from services.template_renderer import RenderStatus, TemplateRenderer

    renderer = TemplateRenderer()
    ctx = renderer._build_template_context(
        order={"order_id": "ord-1", "order_ref": "ORD-1", "service_code": "AI_WF_BLUEPRINT", "service_name": "WF"},
        structured_output={"summary": "llm-only"},
        intake_snapshot={"secret_field": "should-not-render", "_snapshot_created_at": "x"},
        version=1,
        status=RenderStatus.DRAFT,
        regeneration_notes=None,
    )

    assert ctx.get("summary") == "llm-only"
    assert "output" in ctx and ctx["output"].get("summary") == "llm-only"
    assert "secret_field" not in ctx
    assert "intake" not in ctx


def test_admin_manual_generate_uses_orchestrator_and_canonical_intake():
    from routes.admin_orders import trigger_document_generation
    from services.document_orchestrator import OrchestrationStatus

    order_id = "ord-manual-1"
    order = {
        "order_id": order_id,
        "service_code": "AI_WF_BLUEPRINT",
        "intake_snapshot": {"intake_payload": {"business_description": "canonical-db"}},
        "parameters": {"business_description": "legacy-fallback"},
    }
    result_obj = SimpleNamespace(
        success=True,
        version=2,
        status=OrchestrationStatus.REVIEW_PENDING,
        rendered_documents={"docx": {"filename": "v2.docx"}, "pdf": {"filename": "v2.pdf"}},
    )

    with (
        patch("routes.admin_orders.get_order", new_callable=AsyncMock, return_value=order),
        patch("services.order_service.get_current_regeneration_notes", new_callable=AsyncMock, return_value=None),
        patch(
            "services.document_orchestrator.document_orchestrator.execute_full_pipeline",
            new_callable=AsyncMock,
            return_value=result_obj,
        ) as mock_exec,
    ):
        response = asyncio.run(
            trigger_document_generation(order_id=order_id, current_user={"email": "admin@test.com"})
        )

    assert response["success"] is True
    assert response["version"] == 2
    kwargs = mock_exec.await_args.kwargs
    assert kwargs["order_id"] == order_id
    assert kwargs["intake_data"] == {"business_description": "canonical-db"}
    assert kwargs["regeneration"] is False
