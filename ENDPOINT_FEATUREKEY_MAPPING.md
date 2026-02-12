# ENDPOINT-TO-FEATUREKEY MAPPING

**Date:** 2026-02-06  
**Source:** CVP Backend Routes Analysis  
**Purpose:** Complete mapping for launch enforcement

---

## 📋 **FEATURE GATING ENDPOINT MAP**

### Core Features (All Plans)

| Route | Method | FeatureKey | Allowed Plans | Notes |
|-------|--------|------------|---------------|-------|
| `/api/client/dashboard` | GET | `COMPLIANCE_DASHBOARD` | SOLO, PORTFOLIO, PROFESSIONAL | Main compliance dashboard |
| `/api/client/compliance-score` | GET | `COMPLIANCE_SCORE` | SOLO, PORTFOLIO, PROFESSIONAL | Overall compliance score |
| `/api/client/calendar` | GET | `EXPIRY_CALENDAR` | SOLO, PORTFOLIO, PROFESSIONAL | Calendar view of expiring items |
| `/api/client/notifications/preferences` | GET/PUT | `EMAIL_NOTIFICATIONS` | SOLO, PORTFOLIO, PROFESSIONAL | Email notification settings |

---

### Document Features

| Route | Method | FeatureKey | Allowed Plans | Notes |
|-------|--------|------------|---------------|-------|
| `/api/documents/upload` | POST | `DOCUMENT_UPLOAD_SINGLE` | SOLO, PORTFOLIO, PROFESSIONAL | Single file upload |
| `/api/documents/bulk-upload` | POST | `DOCUMENT_UPLOAD_BULK_ZIP` | PORTFOLIO, PROFESSIONAL | ZIP file upload & extraction |

---

### AI Features

| Route | Method | FeatureKey | Allowed Plans | Notes |
|-------|--------|------------|---------------|-------|
| `/api/documents/extract` | POST | `AI_EXTRACTION_BASIC` | SOLO, PORTFOLIO, PROFESSIONAL | Basic metadata extraction |
| `/api/documents/extract-advanced` | POST | `AI_EXTRACTION_ADVANCED` | PROFESSIONAL | Advanced extraction with confidence |
| `/api/documents/review-interface` | GET | `AI_REVIEW_INTERFACE` | PROFESSIONAL | Review & accept extracted data |

---

### Reporting Features

| Route | Method | FeatureKey | Allowed Plans | Notes |
|-------|--------|------------|---------------|-------|
| `/api/reports/generate-pdf` | POST | `PDF_REPORTS` | PORTFOLIO, PROFESSIONAL | Generate PDF compliance report |
| `/api/reports/export-csv` | GET | `CSV_EXPORT` | PROFESSIONAL | Export data as CSV |
| `/api/reports/schedule` | POST | `SCHEDULED_REPORTS` | PORTFOLIO, PROFESSIONAL | Schedule recurring reports |
| `/api/reports/scheduled` | GET | `SCHEDULED_REPORTS` | PORTFOLIO, PROFESSIONAL | List scheduled reports |

---

### Communication Features

| Route | Method | FeatureKey | Allowed Plans | Notes |
|-------|--------|------------|---------------|-------|
| `/api/notifications/sms` | POST | `SMS_REMINDERS` | PROFESSIONAL | Send SMS reminder |
| `/api/sms/preferences` | GET/PUT | `SMS_REMINDERS` | PROFESSIONAL | SMS notification settings |

---

### Tenant Portal

| Route | Method | FeatureKey | Allowed Plans | Notes |
|-------|--------|------------|---------------|-------|
| `/api/tenant/login` | POST | `TENANT_PORTAL_ACCESS` | PROFESSIONAL | Tenant portal login |
| `/api/tenant/dashboard` | GET | `TENANT_PORTAL_ACCESS` | PROFESSIONAL | Tenant view of their property |

---

### Integration Features

| Route | Method | FeatureKey | Allowed Plans | Notes |
|-------|--------|------------|---------------|-------|
| `/api/webhooks/register` | POST | `WEBHOOKS` | PROFESSIONAL | Register webhook endpoint |
| `/api/webhooks/test` | POST | `WEBHOOKS` | PROFESSIONAL | Test webhook delivery |
| `/api/v1/client/*` | ALL | `API_ACCESS` | PROFESSIONAL | Client API access |

---

### Advanced Features

| Route | Method | FeatureKey | Allowed Plans | Notes |
|-------|--------|------------|---------------|-------|
| `/api/audit/export` | GET | `AUDIT_LOG_EXPORT` | PROFESSIONAL | Export audit logs |

---

### Property Management

| Route | Method | FeatureKey | Allowed Plans | Notes |
|-------|--------|------------|---------------|-------|
| `/api/properties/create` | POST | Property cap enforcement | SOLO(2), PORTFOLIO(10), PRO(25) | Enforced by property count |

---

## 🔒 **ENFORCEMENT RULES**

**All protected endpoints will:**
1. Check `subscription_status == "ACTIVE"`
2. Check feature enabled in FEATURE_MATRIX
3. Return 403 if blocked
4. Log `PLAN_GATE_DENIED` audit event

**Property caps enforced on:**
- Property creation endpoint
- Bulk property import
- Returns 403 with `PLAN_LIMIT_EXCEEDED` audit log

---

**Total Protected Endpoints: 25+**

**Next:** Applying middleware to each endpoint...
