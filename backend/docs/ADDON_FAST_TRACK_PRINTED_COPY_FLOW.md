# Add-on Selection, Fast Track, and Printed Copy — Flow and Gap Analysis

**Purpose:** Document how addon selection and implementation work, whether Fast Track hastens delivery, how the printed-copy flow works, and how admin knows an order needs printing/dispatch. Identify conflicts and safest options. No blind implementation.

---

## 1. Add-on selection and implementation — flow

### 1.1 Where addons are defined

- **Backend:** `backend/services/pack_registry.py`
  - **PACK_ADDONS:** `FAST_TRACK` (£20, 24h priority, queue_priority 5) and `PRINTED_COPY` (£25, requires postal address, `requires_postal_delivery`).
  - **applies_to:** `["ESSENTIAL", "TENANCY", "ULTIMATE"]` (pack types in PACK_REGISTRY).
- **Pricing:** `calculate_pack_price(pack_type, addons)` adds addon prices to pack base. `validate_pack_addons(pack_type, addons)` checks addon codes and that `pack_type.upper()` is in each addon’s `applies_to`.

### 1.2 Intake / draft flow

1. **Frontend:** `UnifiedIntakeWizard.js`
   - For document packs, calls `GET /api/intake/packs` → `packs` + `addons`.
   - User toggles addons via `handleToggleAddon(addon_code)`; state: `selectedAddons` (e.g. `["FAST_TRACK", "PRINTED_COPY"]`).
   - If **PRINTED_COPY** selected, shows postal address fields; validation requires recipient, line1, city, postcode, phone.
   - On save/submit: `PUT /api/intake/draft/{draft_id}/addons` with `{ addons, postal_address }` (postal only when PRINTED_COPY selected).

2. **Backend:** `intake_wizard.py`
   - `PUT /draft/{draft_id}/addons` → `update_draft_addons(draft_id, addons, postal_address)`.
   - Only allowed when draft `service_code.startswith("DOC_PACK")`.

3. **Backend:** `intake_draft_service.update_draft_addons`
   - Derives **pack_type** as `service_code.replace("DOC_PACK_", "")` → `"ESSENTIAL"`, `"PLUS"`, or `"PRO"`.
   - Calls `validate_pack_addons(pack_type, addons)` and `calculate_pack_price(pack_type, addons)`.
   - Stores `selected_addons`, `pricing_snapshot` (with addon breakdown), and `postal_address` when applicable.

### 1.3 Order creation from draft

- **intake_draft_service** (e.g. on payment confirmation / create order from draft):
  - Reads `draft["selected_addons"]`.
  - Sets on **order**:
    - `fast_track` / `priority` = `"FAST_TRACK" in addons`
    - `requires_postal_delivery` = `"PRINTED_COPY" in addons`
    - `postal_status` = `"PENDING_PRINT"` if PRINTED_COPY else `None`
    - `postal_address` from draft
    - `selected_addons` snapshot.

### 1.4 Checkout / Stripe

- **Checkout validation** (`checkout_validation.py`): can receive `variant_code` (e.g. `standard`, `fast_track`, `printed`). Service catalogue exposes `fast_track_available`, `fast_track_price`, `printed_copy_available`, `printed_copy_price`.
- Frontend can send `variant_code: 'fast_track'` or `'printed'` based on selected addons; Stripe price ID can vary by variant.

**Summary:** Addons are chosen in the intake wizard for document packs, validated and priced using `pack_registry.PACK_ADDONS` and `pack_type`, stored on the draft, and copied onto the order at creation. No separate “addon service”; they are flags and pricing modifiers on the pack order.

---

## 2. Does Fast Track hasten delivery?

**Yes.** It is implemented in two ways:

1. **Shorter SLA**
   - **workflow_automation_service:** `get_sla_hours_for_order(order)` uses `order.get("fast_track")` (or `priority`). If true, uses `fast_track_hours` from `SLA_CONFIG_BY_CATEGORY` or `SLA_SERVICE_OVERRIDES`; otherwise `standard_hours`.
   - Document packs: standard 48h, fast_track 24h (same in overrides for DOC_PACK_ESSENTIAL/PLUS/PRO).
   - `initialize_order_sla` is called in WF1 (payment verified → queued) and sets `sla_target_at`, `sla_warning_at` from these hours.

2. **Queue priority**
   - In WF1, if `fast_track` or `priority`: order is updated with `queue_priority = 10` (if priority) or `5` (fast_track), and `expedited = True`.
   - **Batch processing** (`get_orders_to_process` or equivalent): sorts by `queue_priority` descending, then `priority`, then `fast_track`, then `created_at` ascending. So fast-track orders are picked before standard ones.
   - Admin can also get a **PRIORITY_FLAGGED** notification for fast-track orders.

So Fast Track both **reduces the SLA target (e.g. 24h)** and **moves the order up the processing queue**; it does hasten delivery.

---

## 3. Printed copy flow

### 3.1 Order-side state

- When **PRINTED_COPY** is in `selected_addons` at order creation:
  - `requires_postal_delivery` = True
  - `postal_status` = `"PENDING_PRINT"`
  - `postal_address` (or equivalent) from draft stored on order.

### 3.2 WF1 (payment → queue)

- In **workflow_automation_service** WF1, if order has `printed_copy` (or equivalent): `requires_postal_delivery` and `postal_status = "PENDING_PRINT"` are set (if not already from order creation). So printed-copy orders are explicitly marked for postal.

### 3.3 Admin: how they know an order needs printing and dispatch

- **Endpoint:** `GET /api/admin/orders/postal/pending` (**admin_orders.py**).
  - Returns orders where `requires_postal_delivery == True` and `postal_status` not in `["DELIVERED", "CANCELLED"]`.
  - Groups them by `postal_status`: **PENDING_PRINT**, **PRINTED**, **DISPATCHED**, **OTHER**.
  - Response includes `total`, `pending_print`, `printed`, `dispatched`, and `orders` (grouped).

- **Frontend:** **Admin Postal Tracking** page.
  - Route: `/admin/postal-tracking` (`AdminPostalTrackingPage.js`).
  - Fetches `GET /admin/orders/postal/pending`, shows counts and lists by status (PENDING_PRINT, PRINTED, DISPATCHED, etc.).
  - Admin can update status via `POST /admin/orders/{order_id}/postal/status` with `{ status, tracking_number?, carrier?, notes? }`.
  - Admin can set/update delivery address via `POST /admin/orders/{order_id}/postal/address` (delivery_address, recipient_name, tracking_number, carrier, notes).

- **Admin layout:** `UnifiedAdminLayout.js` shows a “Postal Tracking” nav item with a badge from `GET /admin/orders/postal/pending` → `data.total` (number of orders needing postal handling).

- **Order detail:** In admin order list/detail (e.g. `OrderDetailsPane.jsx`), if `order.requires_postal_delivery` the UI shows postal status badge (PENDING_PRINT / PRINTED / DISPATCHED / DELIVERED) and tracking/carrier/address.

### 3.4 Status flow and manual steps

- **Status flow:** `PENDING_PRINT` → `PRINTED` → `DISPATCHED` → `DELIVERED` (or `FAILED`). Documented in `update_postal_status`.
- **No automatic print/fulfilment:** There is no integration with a print shop or courier. Admin:
  1. Sees orders in **Postal Tracking** (or order list with postal badge).
  2. Prints (or has printed) the pack (e.g. from the approved bundle/ZIP).
  3. Updates status to **PRINTED**, then **DISPATCHED** (with optional tracking/carrier).
  4. When known, sets **DELIVERED** (or **FAILED**).
- Optional: when status is set to DISPATCHED with a tracking number, the code can notify the customer (e.g. via notification_orchestrator).

**Summary:** Printed copy is a manual fulfilment path: order is flagged with `requires_postal_delivery` and `postal_status = PENDING_PRINT`; admin uses the Postal Tracking page and order detail to see what needs printing and dispatch, and updates status as they print and send the pack.

---

## 4. Conflicts and safest options

### 4.1 Pack type vs service_code (addon validation)

- **Current:** `intake_draft_service` uses `pack_type = service_code.replace("DOC_PACK_", "")`, so:
  - DOC_PACK_ESSENTIAL → **ESSENTIAL** ✓ (in PACK_ADDONS applies_to)
  - DOC_PACK_PLUS → **PLUS** ✗ (applies_to has **TENANCY**, not PLUS)
  - DOC_PACK_PRO → **PRO** ✗ (applies_to has **ULTIMATE**, not PRO)
- **Effect:** For DOC_PACK_PLUS and DOC_PACK_PRO, `validate_pack_addons("PLUS", addons)` or `validate_pack_addons("PRO", addons)` fails, so addons are rejected and pricing does not include addons for PLUS/PRO.

**Safest fix:** Map service_code to the pack_type used in PACK_REGISTRY and PACK_ADDONS:

- DOC_PACK_ESSENTIAL → ESSENTIAL  
- DOC_PACK_PLUS → TENANCY  
- DOC_PACK_PRO → ULTIMATE  

Use this mapping in `update_draft_addons` (and anywhere else that derives pack_type from service_code for addons or pricing). Do not change PACK_REGISTRY keys (ESSENTIAL/TENANCY/ULTIMATE) or addon pricing; only fix the mapping so PLUS and PRO get the same addon behaviour as ESSENTIAL.

### 4.2 Dual pack systems (document_pack_orchestrator vs pack_registry)

- **document_pack_orchestrator** uses **DOCUMENT_REGISTRY** and **doc_key** (e.g. doc_rent_arrears_letter_template) and service codes DOC_PACK_ESSENTIAL / DOC_PACK_PLUS / DOC_PACK_PRO.
- **pack_registry** uses **PACK_REGISTRY** (ESSENTIAL, TENANCY, ULTIMATE), **DOCUMENT_DEFINITIONS**, and different document codes (e.g. RENT_ARREARS_LETTER).
- Intake/checkout and addon pricing use pack_registry (ESSENTIAL/TENANCY/ULTIMATE); generation uses document_pack_orchestrator (DOC_PACK_* and doc_key). This is acceptable as long as the mapping above is used for addons and the same logical pack (Essential / Tenancy / Ultimate) is represented consistently in both systems.

### 4.3 Printed copy: no automatic fulfilment

- Spec text sometimes says “create internal fulfillment task” for POSTAL. Current behaviour is: internal list (Postal Tracking) and manual status updates only; no task queue or external shipping API. Safest is to keep this unless you explicitly add a “fulfilment task” entity and/or integrate with a print/ship provider.

---

## 5. Summary table

| Requirement / question | Implemented? | Where / how |
|------------------------|-------------|--------------|
| Addon selection (FAST_TRACK, PRINTED_COPY) | Yes | Intake wizard; PUT draft addons; pack_registry.PACK_ADDONS |
| Addon pricing | Yes | calculate_pack_price(pack_type, addons) |
| Addon validation | Partial | validate_pack_addons; **PLUS/PRO broken** due to pack_type mapping |
| Order gets fast_track / requires_postal_delivery | Yes | Order created from draft with selected_addons snapshot |
| Fast Track shortens SLA | Yes | get_sla_hours_for_order; fast_track_hours vs standard_hours |
| Fast Track queue priority | Yes | queue_priority / expedited in WF1; batch sort by priority then fast_track |
| Printed copy: order flagged | Yes | requires_postal_delivery; postal_status = PENDING_PRINT |
| Admin sees orders needing print | Yes | GET /admin/orders/postal/pending; Postal Tracking page; nav badge |
| Admin updates print/dispatch status | Yes | POST /admin/orders/{id}/postal/status (PENDING_PRINT→PRINTED→DISPATCHED→DELIVERED) |
| Admin sets/edits postal address | Yes | POST /admin/orders/{id}/postal/address |
| Automatic print/ship | No | Manual process only; no fulfilment task or external API |

---

## 6. Recommended next step (no blind implementation)

- **Fix addon applicability for DOC_PACK_PLUS and DOC_PACK_PRO** by introducing a single mapping (e.g. in `intake_draft_service` or `pack_registry`): DOC_PACK_ESSENTIAL→ESSENTIAL, DOC_PACK_PLUS→TENANCY, DOC_PACK_PRO→ULTIMATE, and use it when calling `validate_pack_addons` and `calculate_pack_price`. After that, re-test addon selection and pricing for all three pack types.
