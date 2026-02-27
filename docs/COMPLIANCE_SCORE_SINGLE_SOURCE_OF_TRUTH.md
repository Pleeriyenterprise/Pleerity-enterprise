# Compliance Score & Risk: Single Source of Truth

## Rule

**All consumer-facing portfolio score and risk level (grade, color, message) MUST come from one place:**

- **Function:** `services.compliance_score.calculate_compliance_score(client_id)`
- **Behaviour:**
  - When `requirements_catalog` is populated and `get_portfolio_compliance_from_catalog(client_id)` returns data, that result is used for **score**, **grade**, **color**, and **message** (and risk level comes from catalog’s guardrail logic).
  - When the catalog is empty or returns no data, score/grade/color/message are derived from **stored property scores** (legacy path).

No other code path should compute or overwrite portfolio score/risk for display. Callers should not call `get_portfolio_compliance_from_catalog` directly for the purpose of showing “the” score; they should call `calculate_compliance_score(client_id)`.

## Where it’s used

| Consumer | How it gets score/risk |
|----------|-------------------------|
| **GET /api/client/compliance-score** | Returns `calculate_compliance_score(client_id)` as-is. |
| **Dashboard (main card, risk line)** | Uses portfolio summary for layout; grade/message aligned with backend `risk_level` (see risk level consistency). |
| **Compliance Score page** | Calls GET /api/client/compliance-score → same as above. |
| **Reports (PDF/CSV, score explanation)** | Call `calculate_compliance_score(user["client_id"])`; they automatically get the canonical score. |
| **Trending / snapshots** | Call `calculate_compliance_score(client_id)`; snapshots store the canonical score. |

## Portfolio summary (dashboard tables)

- **GET /api/portfolio/compliance-summary** continues to call `get_portfolio_compliance_from_catalog(client_id)` first (same underlying source when catalog exists).
- The **dashboard main card** uses `portfolioSummary.risk_level` for grade/message when present so the card matches the “Risk level” line and table (single source for risk label).

## Adding new consumers

- For **portfolio-level score or risk** in API or UI: call `calculate_compliance_score(client_id)` (or the GET /api/client/compliance-score endpoint). Do not implement a separate “compute score from catalog” or “compute score from stored” path for display.
- For **property-level** score/risk: use `get_property_compliance_detail(client_id, property_id)` (catalog-driven when catalog exists); property detail page and portfolio summary property rows use this.

## Risk bands

- **Backend:** `utils.risk_bands` — `score_to_risk_level`, `score_to_grade_color_message`, `risk_level_to_grade_color_message`. Single source for score→risk and risk→grade/message.
- **Frontend:** `utils/riskLabel.js` — `formatRiskLabel`, `riskLevelToGradeColorMessage` for display labels only; must stay in sync with backend risk levels (Low Risk, Moderate Risk, High Risk, Critical Risk).
