# Compliance Vault Pro

**AI-Driven Solutions & Compliance**  
*Built for Pleerity Enterprise Ltd*

A comprehensive SaaS platform for UK landlords, letting agents, and property companies to manage compliance requirements across their property portfolios.

---

## 🎯 System Overview

**Service Type:** Full-stack SaaS web application  
**Target Audience:** UK landlords, letting agents, property managers  
**Tech Stack:** React + FastAPI + MongoDB  
**Deployment:** Emergent Platform

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
- Stripe (payment processing via emergentintegrations)

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

**Backend (`.env`):**
```bash
MONGO_URL=mongodb://localhost:27017
DB_NAME=compliance_vault_pro
CORS_ORIGINS=*
JWT_SECRET=your-production-secret-key-change-this
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
STRIPE_API_KEY=sk_test_emergent
POSTMARK_SERVER_TOKEN=
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
```

**Frontend (`.env`):**
```bash
REACT_APP_BACKEND_URL=https://content-forge-411.preview.emergentagent.com
```

### Quick Start

```bash
# Backend
cd /app/backend
pip install -r requirements.txt
python seed.py  # Create admin user
sudo supervisorctl restart backend

# Frontend
cd /app/frontend
yarn install
sudo supervisorctl restart frontend
```

### Admin Credentials (Development)
```
Email: admin@pleerity.com
Password: Admin123!
```

### API Health Check
```bash
curl https://content-forge-411.preview.emergentagent.com/api/health
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
curl https://content-forge-411.preview.emergentagent.com/api/health

# Submit intake
curl -X POST https://content-forge-411.preview.emergentagent.com/api/intake/submit \
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

# Login
curl -X POST https://content-forge-411.preview.emergentagent.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "Password123"}'
```

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
**Platform:** Emergent

---

## 🎉 Next Steps

1. **Configure Postmark:**
   - Create account at postmarkapp.com
   - Set `POSTMARK_SERVER_TOKEN` in backend/.env
   - Create email templates with specified aliases

2. **Stripe Setup:**
   - Test mode works with `sk_test_emergent`
   - For production: Add live keys
   - Configure webhooks to point to `/api/webhook/stripe`

3. **Admin Access:**
   - Use seeded admin credentials
   - Create additional admin users via database

4. **Client Onboarding:**
   - Share landing page URL
   - Walk through intake → payment → setup flow
   - Monitor provisioning in audit logs

---

**Built with ❤️ by Pleerity Enterprise Ltd**  
*Making UK landlord compliance simple and audit-ready*
