# Compliance Vault Pro

**AI-Driven Solutions & Compliance**  
*Built for Pleerity Enterprise Ltd*

A comprehensive SaaS platform for UK landlords, letting agents, and property companies to manage compliance requirements across their property portfolios.

---

## 🎯 System Overview

**Service Type:** Full-stack SaaS web application  
**Target Audience:** UK landlords, letting agents, property managers  
**Tech Stack:** React + FastAPI + MongoDB  
**Deployment:** Render (backend), Vercel (frontend), MongoDB Atlas

### Brand Identity
- **Primary Color:** Midnight Blue (#0B1D3A)
- **Secondary Color:** Electric Teal (#00B8A9)
- **Typography:** Montserrat (headings), Inter (body)
- **Tagline:** "AI-Driven Solutions & Compliance"

---

## 🏗️ Architecture

### Application Structure

```
Public Site
├── / - Marketing landing page
├── /login - Client sign-in
├── /admin/signin - Admin sign-in
└── /intake/start - Universal intake form

Client Portal (/app/*)
├── /app/dashboard - Compliance overview
├── /app/properties - Property management
├── /app/documents - Document vault
└── /app/reports - Compliance reports

Admin Console (/admin/*)
├── /admin/dashboard - System overview
├── /admin/clients - Client management
├── /admin/audit-logs - Audit trail
└── /admin/messages - Email logs
```

### Tech Stack

**Backend:**
- FastAPI (async Python web framework)
- Motor (async MongoDB driver)
- Pydantic (data validation)
- bcrypt + JWT (authentication)
- Postmark (transactional emails)
- Stripe (payment processing)

**Frontend:**
- React 19 with React Router
- shadcn/ui components
- Tailwind CSS
- Axios (API client)
- Context API (state management)

**Database:**
- MongoDB (document store)
- Collections: clients, portal_users, properties, requirements, documents, audit_logs, message_logs, password_tokens, payment_transactions

---

## 🔐 Security Architecture

### RBAC (Role-Based Access Control)

**Roles:**
- `ROLE_ADMIN` - Pleerity internal staff (full system access)
- `ROLE_CLIENT_ADMIN` - Client account owner (client data only)
- `ROLE_CLIENT` - Additional client users (client data only)

**Enforcement:**
- Server-side route guards on ALL protected endpoints
- JWT tokens with role claims
- Client data scoping (client_id validation)
- No admin data accessible to clients
- Separate UI shells (ClientShell vs AdminShell)

### Authentication Flow

1. **Intake** → Client submits intake form
2. **Payment** → Stripe checkout (test mode available)
3. **Provisioning** → Automated account setup
4. **Password Setup** → Secure token-based (60min expiry, single-use)
5. **Login** → JWT-based authentication
6. **Dashboard Access** → Route-guarded client portal

---

## 📋 Core Features

### 1. Universal Intake Flow
- Multi-step form (details → properties → billing)
- Client type selection (Individual, Company, Agent)
- Property collection (repeatable blocks)
- Consent management
- Direct Stripe checkout integration

### 2. Provisioning Engine
**Single source of truth:** `Client.onboarding_status`

States:
- `INTAKE_PENDING` - Form submitted, awaiting payment
- `PROVISIONING` - Automated setup in progress
- `PROVISIONED` - Ready for use
- `FAILED` - Provisioning error

Automatic triggers:
- Generate compliance requirements (Gas Safety, EICR, EPC, Fire Alarm, Legionella)
- Create PortalUser account
- Initialize document vault
- Compute compliance status
- Send password setup email

### 3. Password Setup System
**Production-safe token flow:**
- High-entropy tokens (256-bit)
- Hashed at rest (SHA-256)
- 60-minute expiry
- Single-use only
- Revocable by admin
- Route: `/set-password?token=...`

### 4. Compliance Tracking
**Deterministic status calculation:**
- **GREEN:** All requirements compliant
- **AMBER:** Some expiring soon (30 days)
- **RED:** One or more overdue

**Requirement types:**
- Gas Safety Certificate (annual)
- EICR (5 years)
- EPC (10 years)
- Fire Alarm Inspection (annual)
- Legionella Risk Assessment (2 years)

### 5. Audit System
**Every action logged:**
- User authentication events
- Provisioning steps
- Compliance status changes
- Document operations
- Admin actions
- Route guard redirects

Log structure includes:
- before/after state (where applicable)
- actor role and ID
- client scoping
- metadata and reason codes
- IP addresses

### 6. Email System (Postmark)
**Templates (by alias):**
- `password-setup` - Initial account setup
- `password-reset` - Password recovery
- `portal-ready` - Provisioning complete
- `monthly-digest` - Compliance summary
- `admin-manual` - Admin communications
- `payment-receipt` - Payment confirmations

All sends logged to `MessageLog` collection.

### 7. Payment Integration (Stripe)
**Fixed pricing (no client-side amounts):**
- Plan 1: £29.99/mo (1 property)
- Plan 2-5: £49.99/mo (2-5 properties)
- Plan 6-15: £79.99/mo (6-15 properties)

**Webhook handlers:**
- `checkout.session.completed` → triggers provisioning
- `customer.subscription.updated` → updates status
- `customer.subscription.deleted` → marks cancelled

---

## 🚀 Deployment & Operations

### Environment Variables

**How to configure env vars (activation links and API):**
- **FRONTEND_PUBLIC_URL** (preferred) or **PUBLIC_APP_URL** or **FRONTEND_URL** — Public frontend base URL used for ALL activation/set-password links in emails (e.g. `https://pleerityenterprise.co.uk`). Must be https in production; no trailing slash. If unset, backend uses canonical `https://pleerityenterprise.co.uk` so links never point at the default Vercel deployment URL.
- **REACT_APP_BACKEND_URL** — Frontend build-time: backend API base URL (e.g. `https://your-backend.onrender.com`). Set on Vercel so the app calls the correct API.
- **BACKEND_URL** — Backend base URL for scripts and health checks. Keep Stripe vars (`STRIPE_API_KEY`, webhook secret) unchanged.

**Where to set env vars:** Backend (Render): Dashboard → Service → Environment. Frontend (Vercel): Project → Settings → Environment Variables. Recommended future domain: `https://portal.pleerityenterprise.co.uk`.

**Env checklist (activation links + API):**
| Platform | Variable | Required |
|----------|----------|----------|
| **Render** (backend) | `FRONTEND_PUBLIC_URL` | Must be set so activation/reset links use your frontend domain (not localhost or backend). |
| **Vercel** (frontend) | `REACT_APP_BACKEND_URL` | Must be set so the app calls the correct API; rebuild after changing. |

**If activation links still go to localhost or don’t work after deploy:**  
1. **Backend (Render):** Set `FRONTEND_PUBLIC_URL=https://<your-actual-frontend-domain>` (or `PUBLIC_APP_URL`; no trailing slash). Set `ENVIRONMENT=production` so production rejects localhost. Save and **redeploy** the backend.  
2. **Frontend (Vercel):** Set `REACT_APP_BACKEND_URL=https://<your-backend-url>`. Trigger a **new deploy** (env vars are baked in at build time).  
3. Ensure `CORS_ORIGINS` on the backend includes your frontend origin.

**Backend (Render / local `.env`):**
```bash
MONGO_URL=mongodb+srv://user:pass@cluster.mongodb.net/DB_NAME
DB_NAME=compliance_vault_pro
CORS_ORIGINS=https://pleerityenterprise.co.uk,http://localhost:3000
JWT_SECRET=your-production-secret-key-change-this
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
STRIPE_API_KEY=sk_live_xxx
POSTMARK_SERVER_TOKEN=
FRONTEND_PUBLIC_URL=https://pleerityenterprise.co.uk
PUBLIC_APP_URL=https://pleerityenterprise.co.uk
FRONTEND_URL=https://pleerityenterprise.co.uk
UNSUBSCRIBE_URL=https://pleerityenterprise.co.uk/unsubscribe
LLM_API_KEY=
ENVIRONMENT=production
```

**Frontend (Vercel / local `.env`):**
```bash
REACT_APP_BACKEND_URL=https://your-backend.onrender.com
```

### Quick Start

```bash
# Backend — local
cd backend
pip install -r requirements.txt
python seed.py  # Create admin user
uvicorn server:app --host 0.0.0.0 --port 8001

# Backend — Render (Web Service): root directory = backend, start command must use Render’s PORT:
#   uvicorn server:app --host 0.0.0.0 --port $PORT
# See render.yaml and docs/RENDER_STARTUP_DIAGNOSIS.md.

# Frontend (Vercel or local)
cd frontend
npm install
npm run build   # Vercel runs this; locally: npm start for dev
```

### Admin Credentials (Development)
```
Email: admin@pleerity.com
Password: Admin123!
```

### API Health Check
```bash
curl https://your-backend.onrender.com/api/health
```

---

## 📊 Data Models

### Client
```python
{
  client_id: uuid,
  full_name: str,
  email: EmailStr,
  phone: str,
  company_name: str,
  client_type: "INDIVIDUAL" | "COMPANY" | "AGENT",
  billing_plan: "PLAN_1" | "PLAN_2_5" | "PLAN_6_15",
  subscription_status: "PENDING" | "ACTIVE" | "CANCELLED",
  onboarding_status: "INTAKE_PENDING" | "PROVISIONING" | "PROVISIONED" | "FAILED",
  stripe_customer_id: str,
  created_at: datetime
}
```

### PortalUser
```python
{
  portal_user_id: uuid,
  client_id: uuid,
  auth_email: EmailStr,
  password_hash: str,
  role: "ROLE_CLIENT" | "ROLE_CLIENT_ADMIN" | "ROLE_ADMIN",
  status: "INVITED" | "ACTIVE" | "DISABLED",
  password_status: "NOT_SET" | "SET",
  must_set_password: bool,
  created_at: datetime
}
```

### Property
```python
{
  property_id: uuid,
  client_id: uuid,
  address_line_1: str,
  city: str,
  postcode: str,
  compliance_status: "GREEN" | "AMBER" | "RED",
  created_at: datetime
}
```

### Requirement
```python
{
  requirement_id: uuid,
  client_id: uuid,
  property_id: uuid,
  requirement_type: str,
  description: str,
  frequency_days: int,
  due_date: datetime,
  status: "PENDING" | "COMPLIANT" | "OVERDUE" | "EXPIRING_SOON"
}
```

---

## 🧪 Testing

CI runs on push and pull requests to `main` (see [.github/workflows](.github/workflows)).

### Manual Testing Flow

1. **Intake → Payment → Provisioning:**
   - Visit `/intake/start`
   - Complete 3-step form
   - Use Stripe test card: `4242 4242 4242 4242`
   - Check email for password setup link

2. **Password Setup:**
   - Click link from email (or check MessageLog in DB)
   - Set password (8+ chars, uppercase, lowercase, number)
   - Auto-redirect to dashboard

3. **Client Dashboard:**
   - View compliance summary
   - See property list with status badges
   - Navigate between dashboard/properties/documents

4. **Admin Console:**
   - Login at `/admin/signin`
   - View all clients
   - Check audit logs
   - Resend password setup links

### API Testing (curl)

```bash
# Health check
curl https://YOUR_BACKEND_URL/api/health

# Submit intake
curl -X POST https://YOUR_BACKEND_URL/api/intake/submit \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Test User",
    "email": "test@example.com",
    "client_type": "INDIVIDUAL",
    "preferred_contact": "EMAIL",
    "billing_plan": "PLAN_1",
    "properties": [{"address_line_1": "123 Test St", "city": "London", "postcode": "SW1A 1AA"}],
    "consent_data_processing": true,
    "consent_communications": true
  }'

# Login (client portal – ROLE_CLIENT / ROLE_CLIENT_ADMIN only)
curl -X POST https://YOUR_BACKEND_URL/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "client@example.com", "password": "Password123"}'
# Staff accounts get 403: {"detail": "This account must sign in via the Staff/Admin portal."}

# Staff/Admin login (admin portal – ROLE_ADMIN / ROLE_OWNER only)
curl -X POST https://YOUR_BACKEND_URL/api/auth/admin/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "Password123"}'
# Client accounts get 403: {"detail": "This account must sign in via the Client portal."}
```

---

## 🔧 Render + Vercel + Atlas – Env Checklist

**Backend Web Service (Render):** Use **`render.yaml`** as a blueprint, or set **Root Directory** to `backend` and **Start Command** to:

`uvicorn server:app --host 0.0.0.0 --port $PORT`

Using a fixed port (e.g. `8001`) while Render assigns **`PORT`** leads to deploy timeout (“no open ports”). Vercel only builds the frontend; it does not validate this.

Set these for a clean deploy with **no Emergent dependencies**:

| Where | Variable | Required | Notes |
|-------|----------|----------|--------|
| **Render** (backend) | `MONGO_URL` | Yes | MongoDB Atlas connection string |
| | `DB_NAME` | Yes | e.g. `compliance_vault_pro` |
| | `CORS_ORIGINS` | Yes | Include your frontend origin (e.g. `https://pleerityenterprise.co.uk`) |
| | `JWT_SECRET` | Yes | Strong secret for tokens |
| | `STRIPE_API_KEY` | Yes | Stripe secret key (test or live) |
| | `FRONTEND_URL` | Recommended | Full frontend URL (e.g. `https://pleerityenterprise.co.uk`); if unset, email links use canonical domain |
| | `POSTMARK_SERVER_TOKEN` | If using email | Postmark API token |
| | `UNSUBSCRIBE_URL` | If using email | e.g. `{FRONTEND_URL}/unsubscribe` |
| | `LLM_API_KEY` | If using AI features | Google AI Studio / Gemini API key. When unset, AI endpoints return 503 or graceful fallback (no crash). |
| | `ENVIRONMENT` | Optional | `production` on Render |
| **Vercel** (frontend) | `REACT_APP_BACKEND_URL` | Yes | Backend base URL (e.g. `https://your-app.onrender.com`) |

**Scripts:** `scripts/production_check.sh` uses `BACKEND_URL` (default `http://localhost:8001`) and `FRONTEND_URL` (default `http://localhost:3000`).

| Context | Start command |
|--------|----------------|
| **Local** | `uvicorn server:app --host 0.0.0.0 --port 8001` (from `backend/`) |
| **Render** | `uvicorn server:app --host 0.0.0.0 --port $PORT` (root **`backend/`**; see `render.yaml`) |

**Frontend build:** `npm run build` (CRA); Vercel runs this automatically.

---

## 📝 Implementation Checklist

### ✅ Phase 1 Complete
- [x] Database schema with enums and constraints
- [x] RBAC middleware and auth primitives
- [x] Provisioning engine (deterministic, idempotent)
- [x] Stripe integration (webhooks + checkout)
- [x] Postmark email service (templated emails)
- [x] Password setup flow (production-safe tokens)
- [x] Route guards (client + admin)
- [x] Universal intake form (multi-step)
- [x] Client dashboard (compliance overview)
- [x] Landing page (marketing site)
- [x] Authentication flows (login, password setup)
- [x] Audit logging system
- [x] Brand identity implementation

### 🚧 Phase 2 (Future Enhancements)
- [ ] Document upload + AI extraction
- [ ] Admin console full features
- [ ] Compliance pack generation
- [ ] Monthly digest emails
- [ ] Reminder scheduling
- [ ] SMS notifications (preferred_contact: SMS)
- [ ] Property requirements detail pages
- [ ] Document verification workflow
- [ ] Advanced reporting

---

## 🛡️ Security Considerations

1. **No credentials before PROVISIONED:** Password setup emails only sent after provisioning completes
2. **No dashboard access before password set:** Route guards enforce password_status == SET
3. **Server-side RBAC enforcement:** Never trust client-supplied client_id
4. **Token security:** High-entropy, hashed at rest, single-use, time-limited
5. **Audit trail:** All meaningful actions logged with before/after states
6. **Payment security:** Amounts defined server-side only, never accept from client
7. **Email logging:** All sends tracked in MessageLog for compliance

---

## 📞 Support & Contact

**Product Owner:** Pleerity Enterprise Ltd  
**Email:** support@pleerity.com  
**System:** Compliance Vault Pro  
**Platform:** Render + Vercel + MongoDB Atlas

---

## 🎉 Next Steps

1. **Configure Postmark:**
   - Create account at postmarkapp.com
   - Set `POSTMARK_SERVER_TOKEN` in backend/.env
   - Create email templates with specified aliases

2. **OTP & SMS (Twilio Messaging Service):**
   - See `backend/docs/NOTIFICATION_ENV_VARS.md` for `OTP_PEPPER`, `OTP_TTL_SECONDS`, `OTP_MAX_ATTEMPTS`, `OTP_RESEND_COOLDOWN_SECONDS`, `OTP_MAX_SENDS_PER_HOUR`, `STEP_UP_TOKEN_TTL_SECONDS`, and `TWILIO_MESSAGING_SERVICE_SID`.
   - Endpoints: `POST /api/otp/send`, `POST /api/otp/verify` (step_up verify requires auth).

3. **Stripe Setup:**
   - Test mode: set STRIPE_API_KEY to your Stripe test key
   - For production: Add live keys
   - Configure webhooks to point to `/api/webhook/stripe`

4. **Admin Access:**
   - Use seeded admin credentials
   - Create additional admin users via database

5. **Client Onboarding:**
   - Share landing page URL
   - Walk through intake → payment → setup flow
   - Monitor provisioning in audit logs

---

**Built with ❤️ by Pleerity Enterprise Ltd**  
*Making UK landlord compliance simple and audit-ready*
