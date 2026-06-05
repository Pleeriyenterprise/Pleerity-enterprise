"""
Canonical markdown defaults for governed legal/marketing pages.
Source: static public JSX copy (Jan 2026) + SaaS subscription alignment for terms.
"""
from __future__ import annotations

from typing import Dict, TypedDict

LEGAL_SLUGS = (
    "privacy",
    "terms",
    "cookies",
    "accessibility",
    "careers",
    "partnerships",
    "about",
)

PROVENANCE = "canonical_seed_v1"


class CanonicalPage(TypedDict):
    title: str
    content: str


COMPANY_BLOCK = """**Registered Company:** Pleerity Enterprise Ltd
**Company No.:** SC855023
**Registered Address:** 8 Valley Court, Hamilton ML3 8HW
**Email:** info@pleerityenterprise.co.uk
"""

CANONICAL_DEFAULTS: Dict[str, CanonicalPage] = {
    "privacy": {
        "title": "Privacy Policy",
        "content": f"""# Privacy Policy

Pleerity Enterprise Ltd ("we", "our", or "us") is committed to protecting the privacy and security of the personal information we collect from our clients and website visitors. This Privacy Policy explains how we collect, use, store, and protect personal data in accordance with the UK General Data Protection Regulation (UK GDPR).

{COMPANY_BLOCK}

## 1. Information We Collect

We collect and process personal data necessary for providing our services, including:

- Contact information (name, email, phone number)
- Business or property details (address, ownership, compliance data)
- Payment information (processed securely via Stripe)
- Documents uploaded or shared during service delivery
- Communication records via email or portal correspondence

## 2. How We Use Your Information

We process personal data to:

- Deliver and manage our services
- Create, send, and track compliance and automation reports
- Communicate with clients and respond to enquiries
- Process payments and issue invoices
- Improve our services and maintain security of our systems

## 3. Data Sharing and Third Parties

We use trusted third-party providers to support our operations, including:

- Stripe (secure online payment processing)
- AI language model providers (for automated document generation and insights)
- Email service providers (for transactional communications)
- Secure cloud storage systems (for encrypted document storage)

These providers only process data in accordance with our instructions and applicable data protection laws.

## 4. Data Storage and Retention

Personal data is stored securely using encrypted cloud systems. We retain data only as long as necessary to fulfil the purpose it was collected for or to comply with legal obligations. Documents and reports are archived or deleted upon client request or at the end of the retention period.

## 5. Your Rights

Under UK GDPR, you have the right to:

- Access the personal data we hold about you
- Request correction of inaccurate information
- Request erasure of your data (where applicable)
- Restrict or object to data processing
- Request data portability

To exercise any of these rights, contact us at [info@pleerityenterprise.co.uk](mailto:info@pleerityenterprise.co.uk).

## 6. Security

We implement appropriate technical and organisational measures to safeguard data against unauthorised access, loss, or misuse. This includes encryption, access controls, and secure transfer protocols.

## 7. Updates to This Policy

We may update this Privacy Policy periodically to reflect changes in law or business operations. The latest version will always be available on our website at pleerityenterprise.co.uk.

---

Pleerity Enterprise Ltd – AI-Driven Solutions & Compliance

*Last updated: January 2026*
""",
    },
    "terms": {
        "title": "Terms of Service",
        "content": f"""# Terms of Service

These Terms of Service ("Terms") govern the use of services provided by Pleerity Enterprise Ltd ("we", "our", or "us"). By engaging our services, you ("Client") agree to comply with and be bound by these Terms. If you do not agree, please do not use our services.

{COMPANY_BLOCK}

## 1. Services Provided

Pleerity Enterprise Ltd provides AI-powered workflow automation, compliance and documentation services for landlords, AI-enhanced market research for SMEs, document automation for professional firms, and professional cleaning services. Service details, inclusions, and fees are specified in proposals or service descriptions provided to clients.

## 2. Client Responsibilities

Clients are responsible for providing accurate, complete, and timely information necessary for the delivery of services. We are not liable for delays or outcomes caused by incorrect or incomplete data provided by the client. **These Terms do not constitute legal advice.** Landlords and operators remain responsible for meeting their legal and regulatory obligations.

## 3. Payments and Refunds

All payments must be made in accordance with the invoice or payment link provided. Payments are processed securely via Stripe or other approved platforms. Refunds are issued only in cases of proven service error or as outlined in specific service agreements. Once a digital document, report, or automation has been delivered, it is considered a completed service.

### Contractor and job coordination

Where the platform is used to coordinate jobs and contractor engagements, Pleerity facilitates coordination and invoice approval workflows only. Contractors are independent service providers engaged by the client. Payment responsibility for contractor work lies with the client. Pleerity does not process contractor payments unless explicitly agreed otherwise in writing.

## 3a. Software Subscriptions (Compliance Vault Pro)

Where you subscribe to our SaaS platform, including Compliance Vault Pro:

- Subscriptions are billed on a **recurring basis** via **Stripe** checkout
- Plan changes take effect according to your selected billing cycle and account settings
- You may **cancel** via account billing settings or by contacting support at [info@pleerityenterprise.co.uk](mailto:info@pleerityenterprise.co.uk)
- Access to paid features generally continues until the end of the current paid period unless otherwise stated
- Non-payment may result in suspension of subscription entitlements after reasonable notice
- The platform provides workflow tools, structured compliance indicators, and reporting support — **not legal advice or certification**
- Immutable report artifacts and audit logs support operational traceability; they do not replace professional legal judgment

## 4. Cancellations

Clients may cancel services prior to commencement by providing written notice. Once processing or automation setup has begun, cancellation may not be eligible for refund. We reserve the right to cancel or suspend services in the event of non-payment or breach of these Terms.

## 5. Intellectual Property

All templates, systems, reports, and automation designs created by Pleerity Enterprise Ltd remain our intellectual property, unless expressly transferred in writing. Clients are granted a non-exclusive, non-transferable licence to use delivered documents or reports for their own lawful business purposes.

## 6. Confidentiality

Both parties agree to maintain confidentiality of all business, personal, or technical information shared during service delivery. We will not disclose client information to any third party except as required by law or to fulfil service obligations through approved partners.

## 7. Limitation of Liability

To the maximum extent permitted by law, Pleerity Enterprise Ltd shall not be liable for any indirect, incidental, or consequential damages arising from the use of our services. Our total liability shall not exceed the amount paid by the client for the specific service in question.

## Service Scope Updates

Pleerity Enterprise Ltd reserves the right to update, modify, or discontinue any aspect of its services, pricing, or delivery scope at any time, provided such changes do not materially diminish the core functionality of an ongoing service for which the client has already paid.

Clients will be notified of significant updates via email or website notice. Continued use of the service after such notice constitutes acceptance of the updated scope.

## 8. Termination of Services

We may suspend or terminate services without liability if the client breaches these Terms, provides misleading information, or uses our services for unlawful purposes.

## 9. Data Protection

We comply with UK GDPR and process all personal data in accordance with our Privacy Policy. By using our services, clients consent to such processing as described in that policy.

## 10. Governing Law

These Terms are governed by and construed in accordance with the laws of Scotland and the United Kingdom. Any disputes shall be subject to the exclusive jurisdiction of the Scottish courts.

## 11. Contact Information

For questions about these Terms, please contact:

- **Email:** [info@pleerityenterprise.co.uk](mailto:info@pleerityenterprise.co.uk)
- **Address:** 8 Valley Court, Hamilton ML3 8HW

---

Pleerity Enterprise Ltd – AI-Driven Solutions & Compliance

*Last updated: January 2026*
""",
    },
    "cookies": {
        "title": "Cookie Policy",
        "content": """# Cookie Policy

*Last updated: November 2025*

This Cookie Policy explains how Pleerity Enterprise Ltd ("we", "our", "us") uses cookies and similar technologies to recognize you when you visit our website at pleerityenterprise.co.uk ("Website"). It explains what these technologies are and why we use them, as well as your rights to control our use of them.

## 1. What Are Cookies?

Cookies are small data files that are placed on your computer or mobile device when you visit a website. They are widely used by website owners to make their websites work more efficiently, as well as to provide reporting information.

## 2. How We Use Cookies

We use cookies for several reasons:

- **Essential cookies** – required for the operation of our website and secure login areas
- **Performance and analytics cookies** – to understand how visitors use our site and improve user experience
- **Functionality cookies** – to remember user preferences and provide enhanced features
- **Targeting cookies** – used for limited marketing analysis through anonymized metrics

## 3. Third-Party Cookies

Our website may use third-party cookies from trusted service providers for payment processing, customer support, and other essential functions.

## 4. Managing Cookies

You have the right to decide whether to accept or reject cookies. You can set your web browser controls to accept or refuse cookies. Note that disabling cookies may affect the functionality of this Website.

## 5. Updates to This Policy

We may update this Cookie Policy periodically to reflect changes to the cookies we use or for other operational, legal, or regulatory reasons. Please revisit this Cookie Policy regularly to stay informed.

## 6. Contact Us

If you have any questions about our use of cookies or this policy, contact us at:

- **Email:** [info@pleerityenterprise.co.uk](mailto:info@pleerityenterprise.co.uk)
- **Address:** 8 Valley Court, Hamilton, ML3 8HW, United Kingdom

---

Pleerity Enterprise Ltd – AI-Driven Solutions & Compliance

*Last updated: November 2025*
""",
    },
    "accessibility": {
        "title": "Accessibility Statement",
        "content": """# Accessibility Statement

*Last updated: November 2025*

Pleerity Enterprise Ltd is committed to ensuring digital accessibility for people with disabilities. We continuously work to improve the user experience for everyone and apply relevant accessibility standards.

## 1. Our Commitment

We aim to conform to the Web Content Accessibility Guidelines (WCAG) 2.1 Level AA standard. These guidelines explain how to make web content more accessible for people with disabilities and more user-friendly for everyone. We do not claim formal third-party certification unless explicitly stated in writing.

## 2. Measures to Support Accessibility

We take the following measures to ensure accessibility:

- Regular accessibility audits and testing on all main pages
- Use of readable font contrasts and resizable text
- Alt-text for images and descriptive labels for forms
- Screen reader and keyboard navigation support

## 3. Known Limitations

Despite our best efforts to ensure accessibility, some content may not yet fully comply. We are committed to continuous improvement and encourage feedback.

## 4. Feedback and Contact

We welcome your feedback on the accessibility of our website. If you encounter any barriers, please contact us:

- **Email:** [info@pleerityenterprise.co.uk](mailto:info@pleerityenterprise.co.uk)
- **Phone:** 020 3337 6060
- **Postal Address:** 8 Valley Court, Hamilton ML3 8HW, United Kingdom

## 5. Enforcement Procedure

If you are dissatisfied with our response to any accessibility concern, you have the right to escalate the issue to the Equality and Human Rights Commission (EHRC) in the United Kingdom.

## 6. Ongoing Improvements

We continue to review and update our accessibility approach in line with changes to technology, user feedback, and updates to accessibility standards.

---

Pleerity Enterprise Ltd – AI-Driven Solutions & Compliance

*Last updated: November 2025*
""",
    },
    "careers": {
        "title": "Careers",
        "content": """# Build Systems That Make Businesses Stronger

Join Pleerity Enterprise Ltd as we develop secure automation, compliance, and documentation solutions for organisations across the UK.

## Join the Talent Pool

Pleerity Enterprise Ltd is a UK-based automation and compliance company providing AI-driven workflows, digital documentation, and landlord compliance solutions. Our goal is to make complex regulatory work simpler, safer, and more efficient for individuals and organisations.

We are building a structured, professional team. As the company expands, we aim to recruit individuals who value accuracy, responsibility, and strong attention to detail.

We encourage prospective applicants to join our Talent Pool so they can be contacted when suitable roles become available.

**Field contractors** (e.g. gas, electrical, plumbing) who want to receive jobs from our clients should apply to the contractor network — this is separate from the office Talent Pool above.

## Our Hiring Philosophy

We recruit with care, prioritising:

- Professional integrity
- Strong ethics and data responsibility
- Accuracy in documentation and record-keeping
- Willingness to learn emerging technologies
- Commitment to secure and compliant working practices

We believe that a stable and well-supported team produces the most reliable work for clients.

## Why Work With Us

- **Structured, Process-Driven Work** – Clear compliance frameworks guide our systems and workflows
- **Work With Real Impact** – Our work helps landlords, SMEs, and professional firms meet legal requirements and improve operational safety
- **Flexible Working Options** – Hybrid and remote roles may be available depending on position
- **Training and Professional Development** – Structured onboarding and training in AI tools, compliance procedures, digital record-keeping, and secure workflow systems
- **Ethical and Secure Environment** – We follow UK GDPR data standards and maintain strict operational governance

## Future Roles

As the company grows, we expect to recruit for:

**AI & Workflow Operations:** Automation Technician, Workflow Assistant, Data Quality and Review Officer

**Compliance & Documentation:** Compliance Assistant, Documentation Analyst, Tenancy & Property Compliance Officer

**Client Delivery:** Client Onboarding Coordinator, Support Desk Advisor

**Administrative & Governance:** HR & Compliance Administrator, Operations Assistant

*These are not open positions yet. They reflect our anticipated hiring plan.*

## How Recruitment Works

1. **Join the Talent Pool** – Submit your details using the Careers Form
2. **Document Screening** – Applications are reviewed against compliance criteria and role requirements
3. **Interview & Assessment** – Shortlisted applicants may complete a practical task
4. **Onboarding** – Successful applicants receive structured onboarding covering governance, internal systems, and right-to-work compliance

## Equal Opportunities Statement

Pleerity Enterprise Ltd is an equal-opportunity employer. We assess all applicants based on capability, competence, and integrity. We do not discriminate on the basis of age, gender, race, nationality, disability, or any protected characteristic.

---

[Join the Talent Pool](/careers/talent-pool) · [Apply as a field contractor](/contractors/register)
""",
    },
    "partnerships": {
        "title": "Partnerships",
        "content": """# Partnerships Built on Trust and Operational Excellence

Collaborate with Pleerity Enterprise Ltd to deliver secure automation, compliance, and digital transformation solutions that create measurable value.

Pleerity Enterprise Ltd collaborates with organisations that share a commitment to operational excellence, regulatory compliance, and intelligent automation.

Our partnership model is designed to help organisations integrate trusted AI solutions, expand service capabilities, or unlock new efficiencies across compliance and documentation workflows.

Whether you are a technology provider, consultancy, property service business, or academic institution, we welcome proposals that create measurable value and uphold strong compliance standards.

## Why Partner With Us

- **Proven Compliance Expertise** – Automated documentation, digital compliance, data governance, and landlord regulatory workflows aligned with UK GDPR standards
- **Scalable AI Automation** – Integrate AI-powered templates, document generation tools, and workflow engines
- **Secure Infrastructure** – Secure, auditable environment suitable for regulated sectors
- **Flexible Collaboration Models** – Referral partnerships, white-label solutions, API integrations, and research collaborations
- **Fast Implementation** – Rapid deployment without long development cycles

## Types of Partnerships We Support

- Referral Partnerships
- White-Label Automations
- Technology Integrations
- Compliance Collaboration
- Service Delivery Partnerships
- Research & Development Collaborations
- Enterprise partnership integration network

## Who We Work With

Our partnerships are suitable for:

- Property management companies
- Legal and professional service firms
- Technology and SaaS companies
- Government-related programmes
- Universities and research groups
- Recruitment and HR agencies
- Compliance consultants
- Training organisations

If your organisation delivers compliance, automation, risk, or digital transformation services, we are open to a conversation.

## Partnership Standards

All partnerships must align with:

- UK GDPR and the Data Protection Act 2018
- Ethical AI usage practices
- Transparent operational standards
- Security and confidentiality requirements
- Home Office-aligned frameworks where applicable

Each partnership request undergoes a structured review before approval.

## How the Partnership Works

1. Submit Your Enquiry – Complete the online partnership form
2. Compliance Review – We evaluate suitability based on capability
3. Proposal Discussion – Structured call to refine scope
4. Agreement & Onboarding – Review and sign cooperation agreement
5. Launch & Support – Onboarding and technical support

## Partnership FAQ

**Do you accept international partners?** Yes, provided regulatory and data handling standards can be met.

**Is there a minimum business size required?** No. We work with start-ups, SMEs, and established organisations.

**Do you offer exclusivity?** Only in rare, strategic cases.

**Can partnerships be fully remote?** Yes. All communication and collaboration can be delivered online.

---

[Become a Partner](/partnerships/enquiry)
""",
    },
    "about": {
        "title": "About Us",
        "content": """# Built for Organisations That Need Structure — Not Guesswork

Compliance is often reactive. We built structured systems to make it proactive.

## The Problem We Saw

Landlords juggling certificates in email folders. Deadlines missed. Spreadsheets breaking. No central audit trail.

Compliance Vault Pro was created to bring structure, visibility, and automation to this process.

## Our Approach

Our approach is built on three principles:

- **Evidence First** – We track documents, not assumptions
- **Structured Indicators** – We provide risk indicators, not legal verdicts
- **Audit Visibility** – Every update is logged. Every change traceable

## Security & Data Handling

- Secure cloud infrastructure with encryption in transit
- Role-based access controls
- Audit logs for traceability
- Data access limited to what is operationally required; we do not monetise or resell client data

**Compliance disclaimer:** We do not provide legal advice or certification. Our platform supports compliance oversight through structured tracking and reporting; you remain responsible for meeting your legal and regulatory obligations.

## AI Philosophy

**AI is assistive only.** All extracted data requires user confirmation before it is applied. Compliance status is determined by structured rules and your confirmed inputs, not by AI-generated legal conclusions.

## Who It's Built For

- Solo landlords
- Portfolio landlords
- Managing agents
- Property professionals

---

[Explore Compliance Vault Pro](/compliance-vault-pro)
""",
    },
}


def get_canonical(slug: str) -> CanonicalPage | None:
    return CANONICAL_DEFAULTS.get(slug)
