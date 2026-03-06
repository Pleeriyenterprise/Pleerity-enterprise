# Template Renderer – Codebase Audit vs Task Requirements

**Scope:** Four services (AI automation, Market research, Compliance services, Document packs).  
**Audit date:** 2025-02 (codebase state at audit).  
**Do not implement blindly:** This document compares task requirements to the existing implementation and calls out gaps and the safest options.

---

## 1. Task summary (requirements)

- **DOCX templates** stored server-side (per service/doc_type)
- **Use docxtemplater or similar** to inject fields
- **PDF** generated from DOCX **OR** from HTML via WeasyPrint equivalent (Node alternative: puppeteer)
- **Strong formatting:** headings, spacing, tables, charts/graphs where required (tool reports, comparisons), consistent fonts and branding
- **Store** DOCX as editable master; PDF as delivery artifact
- **In documents collection store:** storage keys, sha256 hash, prompt_template_id + version used, input_snapshot hash
- **Admin preview:** PDF preview in browser; download both DOCX and PDF

---

## 2. Current implementation overview

| Component | Technology | Location |
|-----------|------------|----------|
| DOCX generation | **python-docx** (programmatic: `Document()`, `add_paragraph`, `add_table`, styles) | `backend/services/template_renderer.py` |
| PDF generation | **ReportLab** (programmatic: `SimpleDocTemplate`, `Paragraph`, `Table`, etc.) | `backend/services/template_renderer.py` |
| Version/store | **document_versions_v2** (single-doc orders); **document_pack_items** (pack items) | Same file + `document_pack_orchestrator.py` |
| File storage | **GridFS** (bucket `order_files`) | `template_renderer.py` (after render) |
| Admin document API | `GET .../documents/{version}/preview?format=pdf|docx`, `.../view?format=...&token=...` | `backend/routes/admin_orders.py` |

There are **no server-side .docx template files** in the repo; no docxtemplater, WeasyPrint, or puppeteer. DOCX and PDF are both built **in code** from orchestrator JSON, with branching by `service_code` (and doc_type for pack).

---

## 3. Requirement-by-requirement

### 3.1 DOCX templates stored server-side (per service/doc_type)

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| DOCX templates stored server-side | ❌ No | No `.docx` template files are stored or loaded. Content is built **programmatically** in `template_renderer.py` via python-docx (`_render_docx` → `_add_docx_content` with service-specific branches: `_render_ai_service_content`, `_render_market_research_content`, `_render_compliance_content`, `_render_document_pack_content`, `_render_generic_content`). |
| Per service/doc_type | ⚠️ By code path, not by file | Service/doc_type is handled by **branching in code** (e.g. `if service_code.startswith("AI_"):` … `elif service_code.startswith("DOC_PACK_"):` …). There is no lookup of a template file by service_code or doc_type. |

**Gap:** The task implies **files** (e.g. one .docx per service or doc_type) and **loading** them. Current design uses **code as the “template”** (one code path per service family). To align with “templates stored server-side” you would add: a template store (e.g. GridFS or filesystem), a mapping service_code/doc_type → template key, and loading a .docx from that store before rendering.

---

### 3.2 Use docxtemplater or similar to inject fields

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| docxtemplater or similar | ❌ No | **docxtemplater** is a Node library (template + placeholders → inject data). The stack is **Python**; there is no equivalent (e.g. python-docx-template, or loading a .docx and replacing placeholders). Fields are “injected” by **building the document in code** from `structured_output` and `intake_snapshot` (e.g. `doc.add_paragraph(str(output["executive_summary"]))`). So: same **effect** (data → document), different **mechanism** (no template file + placeholder engine). |

**Gap:** No template-with-placeholders engine. If the requirement is “must use a template file + variable injection”, you’d need either (a) a Python equivalent (e.g. python-docx-template, or custom placeholder replacement in a stored .docx), or (b) to treat the current “code-built DOCX” as the approved implementation and document it as “similar” (data-driven output without stored .docx templates).

---

### 3.3 PDF generated from DOCX OR from HTML (WeasyPrint / puppeteer)

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| PDF from DOCX | ❌ No | PDF is **not** generated from the DOCX. It is built **independently** with **ReportLab** from the same `structured_output` + `intake_snapshot` (e.g. `_render_pdf` → `_add_pdf_content`). So there is a single source of truth (orchestrator JSON), but **two separate render paths** (DOCX and PDF), not DOCX → PDF. |
| PDF from HTML (WeasyPrint / Node puppeteer) | ❌ No | No HTML intermediate and no WeasyPrint or puppeteer. ReportLab is used directly. |

**Gap:** Pipeline is **Orchestrator JSON → DOCX** and **Orchestrator JSON → PDF** in parallel. Task asks for “PDF from DOCX **or** from HTML”. Safest option: **document** current approach (PDF from ReportLab) as the standard; if you later need “PDF from DOCX” for fidelity, add a converter step (e.g. docx2pdf, LibreOffice headless, or unoconv) and keep ReportLab as an alternative path.

---

### 3.4 Strong formatting (headings, spacing, tables, charts, branding)

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Headings | ✅ Yes | Custom styles: `CustomTitle`, `CustomHeading`, `_add_section_heading`, `_add_subsection`; PDF uses `BrandTitle`, `BrandHeading`. |
| Spacing | ✅ Yes | Paragraph spacing, spacers, `space_before` / `space_after` in styles. |
| Tables | ✅ Yes | DOCX: `doc.add_table()` for market research (competitor overview, SWOT). PDF: `_add_pdf_content` uses paragraphs/lists; ReportLab `Table` exists in the codebase in other modules (e.g. reporting, compliance_pack). In template_renderer, market research gets tables in DOCX; PDF content is more list/paragraph based. |
| Charts or graphs (tool reports, comparisons) | ⚠️ Partial | **No charts or graphs** in `template_renderer.py` (no Pie, Bar, or plot generation). `professional_reports.py` uses ReportLab `Pie` for charts but is a different context. So: tables yes; charts/graphs for “tool reports, comparisons” **not** in the main template renderer. |
| Consistent fonts and branding | ✅ Yes | `BRAND_TEAL`, `BRAND_NAVY`, `BRAND_GRAY`; consistent use in DOCX (RGBColor) and PDF (HexColor); header/footer and watermark. |

**Gap:** Add charts/graphs where the task requires them (e.g. tool comparison reports) – e.g. ReportLab graphics (Pie, Bar) or export from another source, inside the same service_code content branches.

---

### 3.5 Store DOCX as editable master; PDF as delivery artifact

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| DOCX stored | ✅ Yes | DOCX is generated and stored in GridFS (`order_files`), with metadata (order_id, version, sha256, content_type). |
| PDF stored | ✅ Yes | PDF stored in same bucket, same version record. |
| DOCX = editable master, PDF = delivery | ✅ Conceptually | Both are stored; DOCX is the editable format, PDF is the sealed delivery format. No explicit “master” vs “artifact” flag in schema; usage (download DOCX for edit, PDF for send) matches intent. |

---

### 3.6 In documents collection: storage keys, sha256, prompt_template_id + version, input_snapshot hash

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Storage keys | ✅ Yes | **document_versions_v2:** `docx.gridfs_id`, `pdf.gridfs_id` (and filename). **document_pack_items:** `docx_gridfs_id`, `pdf_gridfs_id`, `filename_docx`, `filename_pdf`. |
| sha256 hash | ✅ Yes | **document_versions_v2:** `docx.sha256_hash`, `pdf.sha256_hash`. **document_pack_items:** `docx_sha256_hash`, `pdf_sha256_hash`. |
| prompt_template_id + version used | ✅ Yes | **document_versions_v2:** `prompt_version_used` (dict with template_id, version, etc.). **document_pack_items:** `prompt_version_used` on item. Naming is “prompt_version_used” not “prompt_template_id”; semantics match. |
| input_snapshot hash | ✅ Yes | **document_versions_v2:** `intake_snapshot_hash`. **document_pack_items:** `input_snapshot_hash`. |

**Note:** The task says “documents collection”. The codebase uses **document_versions_v2** for single-doc orders and **document_pack_items** for pack items. Both hold the required fields; no separate single “documents” collection.

---

### 3.7 Admin preview: PDF in browser; download both DOCX and PDF

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| PDF preview in browser | ✅ Yes | `GET /api/admin/orders/{order_id}/documents/{version}/token?format=pdf` returns a time-limited URL; `GET .../view?format=pdf&token=...` returns the PDF with `Content-Disposition: inline` for browser/iframe. Frontend: `DocumentPreviewModal.jsx` uses token and preview URL for PDF. |
| Download DOCX | ✅ Yes | `GET .../preview?format=docx` (or .../view with format=docx) returns DOCX with `attachment` (preview) or inline; frontend has “Download DOCX” using preview URL with `format=docx`. |
| Download PDF | ✅ Yes | Same pattern with `format=pdf`; “Download PDF” in admin order UI. |

---

## 4. Gaps summary

| # | Gap | Severity | Recommendation |
|---|-----|----------|----------------|
| 1 | No server-side .docx template **files** per service/doc_type; content is code-built | Medium | Optional: introduce a template store and load .docx by service_code/doc_type; keep code path as fallback. |
| 2 | No docxtemplater-like **engine** (no template + placeholder injection); Python and code-built DOCX only | Medium | Accept code-built DOCX as “similar” for data injection, or add a Python template engine (e.g. python-docx-template) if placeholders are required. |
| 3 | PDF is **not** generated from DOCX or from HTML; it’s built with ReportLab from JSON | Low | Document as-is. If “PDF from DOCX” is required later, add a conversion step. |
| 4 | No **charts/graphs** in template_renderer (tables only) for tool reports/comparisons | Low | Add ReportLab (or other) chart generation in the relevant service_code branches when needed. |

---

## 5. Conflicts and safe options

- **Stack:** Task mentions “docxtemplater” (Node) and “WeasyPrint equivalent (Node: puppeteer)”. The app is **Python** (FastAPI, python-docx, ReportLab). So:
  - **Safe:** Keep Python; treat “docxtemplater or similar” as “data-driven document generation” (current code does that). Treat “WeasyPrint/puppeteer” as “PDF from HTML” and document that the current choice is “PDF from ReportLab” (no HTML).
- **Templates:** “DOCX templates stored server-side” can mean (a) literal .docx files, or (b) “template” as in “defined structure per service”. Current design is (b). If (a) is required, add file-based templates without removing (b) so existing behaviour stays.
- **Documents collection:** Task says “documents collection”; code uses **document_versions_v2** and **document_pack_items**. No conflict; just document that “documents” is realized as these two collections with the required fields.

---

## 6. What is already in place (no change needed)

- DOCX and PDF generation from orchestrator JSON, with service- and pack-specific content.
- Strong formatting: headings, spacing, tables (at least in DOCX for market research), consistent branding.
- GridFS storage for both DOCX and PDF; DOCX as editable, PDF as delivery.
- **document_versions_v2** (and **document_pack_items**): storage keys (gridfs_id), sha256, prompt_version_used, intake_snapshot_hash.
- Admin: PDF preview in browser (token + view), download DOCX and PDF via preview with `format=docx` / `format=pdf`.

---

## 7. Files reference

- **Rendering:** `backend/services/template_renderer.py` (DOCX: python-docx; PDF: ReportLab; version record; GridFS upload; render_pack_item).
- **Version store:** `document_versions_v2` (single-doc); `document_pack_items` (pack) with file fields.
- **Admin document API:** `backend/routes/admin_orders.py` (`/documents`, `.../preview`, `.../token`, `.../view`).
- **Frontend preview/download:** `frontend/src/components/admin/orders/DocumentPreviewModal.jsx`, `frontend/src/api/ordersApi.js`.

---

## 8. Recommended next steps (if implementing)

1. **Optional – server-side .docx templates:** Add a template registry (e.g. service_code/doc_type → GridFS key or path). Load .docx from store when present; fall back to current code-built DOCX. No change to PDF or storage schema.
2. **Optional – template + placeholders:** If product requires “edit a .docx and use placeholders”, add a Python layer (e.g. python-docx-template) and use it only when a template file exists; otherwise keep current code path.
3. **Optional – PDF from DOCX:** Only if you need pixel-perfect match between DOCX and PDF. Add a conversion step (e.g. LibreOffice, docx2pdf) and optionally keep ReportLab for simpler cases.
4. **Charts/graphs:** In `template_renderer`, in the content branch for “tool reports” or comparisons, add ReportLab chart generation (e.g. Pie, Bar) from `structured_output` where the schema supports it.

This audit reflects the current codebase and is intended to guide decisions without duplicating or conflicting with existing behaviour.
