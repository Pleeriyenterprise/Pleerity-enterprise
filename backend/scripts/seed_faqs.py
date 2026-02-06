"""
Seed FAQ Database with Comprehensive Question List
Run this once to populate the FAQ database
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import database
from datetime import datetime, timezone

FAQS = [
    # General Questions
    ("General Questions", "What does Pleerity Enterprise do?", "Pleerity Enterprise helps landlords and businesses handle compliance, automation, and documentation in a structured, reliable way. We work through paid intake workflows that collect the right information upfront, then use automation and human review where needed to deliver professional outputs.", 1),
    ("General Questions", "How do I get started?", "Click 'Get Started' on any service page, complete the intake form, and proceed to payment. Once paid, your request enters our workflow system.", 2),
    ("General Questions", "Do I need to pay before anything starts?", "Yes. Payment confirms your request and ensures we can allocate resources to deliver your service professionally.", 3),
    ("General Questions", "Why do you require payment upfront?", "Upfront payment prevents abandoned requests, ensures commitment, and allows us to allocate proper resources to your service delivery.", 4),
    ("General Questions", "Can I talk to someone before paying?", "You can contact us via email or phone for general questions, but detailed service scoping requires completing the intake form.", 5),
    ("General Questions", "Do you give legal or compliance advice?", "No. We generate documents and reports based on your inputs, but we do not provide legal advice. Consult a solicitor for legal matters.", 6),
    ("General Questions", "How long does it take to receive my documents?", "Standard delivery: 48 hours for document packs, 72 hours for compliance services. Fast Track reduces this to 24 hours.", 7),
    ("General Questions", "What is Fast Track?", "Fast Track is a priority service that reduces delivery time to 24 hours. It includes a one-time fee and moves your request to the front of the queue.", 8),
    ("General Questions", "Is my information secure?", "Yes. We use encrypted storage, follow UK GDPR standards, and implement strict access controls. All data handling is audited.", 9),
    ("General Questions", "Are you legitimate / a registered business?", "Yes. Pleerity Enterprise Ltd is registered in Scotland (Company No. SC855023). Our registered address is 8 Valley Court, Hamilton ML3 8HW.", 10),
    
    # Process & Intake
    ("Process & Intake", "Why is the intake form so detailed?", "Detailed forms ensure we collect accurate information upfront, reducing delays and ensuring the output meets your specific needs.", 11),
    ("Process & Intake", "Can I submit now and complete the details later?", "No. The form must be completed before submission. This ensures we have everything needed to start work immediately.", 12),
    ("Process & Intake", "Can I change details after submitting?", "Minor corrections may be possible. Contact us immediately if you spot an error. Significant changes may require a new request.", 13),
    ("Process & Intake", "Do you work with letting agents or only landlords?", "We work with both landlords and letting agents, as well as property managers and professional firms.", 14),
    ("Process & Intake", "Is this service suitable for just one property?", "Yes. Our services work for single properties or large portfolios.", 15),
    ("Process & Intake", "What happens after I submit the form?", "Your request is converted to an order, enters our workflow system, and progresses through generation, review, and delivery stages.", 16),
    ("Process & Intake", "Will I get an order or reference number?", "Yes. You'll receive an order reference (e.g., PLE-2026-0001) that you can use to track progress.", 17),
    ("Process & Intake", "Can I track the status of my request?", "Yes. Log into your portal to view order status and progress.", 18),
    
    # Pricing & Payments
    ("Pricing & Payments", "Can I get a discount?", "We occasionally offer discounts for bulk orders or returning customers. Contact us to discuss.", 19),
    ("Pricing & Payments", "Is VAT included?", "Prices shown include VAT where applicable.", 20),
    ("Pricing & Payments", "What happens if I select the wrong service?", "Contact us immediately. We may be able to adjust or refund if work hasn't started.", 21),
    ("Pricing & Payments", "Is my payment secure?", "Yes. All payments are processed securely via Stripe. We never store your full card details.", 22),
    ("Pricing & Payments", "Can I pay by bank transfer?", "For large orders, bank transfer may be available. Contact us to arrange.", 23),
    ("Pricing & Payments", "Do you offer refunds?", "Refunds are issued only in cases of proven service error. Once documents are delivered, the service is considered complete.", 24),
    
    # Service Delivery
    ("Service Delivery", "Is this service automated or handled by a person?", "We use a combination. AI handles initial generation, then human experts review for accuracy before delivery.", 25),
    ("Service Delivery", "Can you guarantee compliance?", "We provide documents and analysis based on current UK regulations, but we cannot guarantee compliance outcomes as circumstances vary.", 26),
    ("Service Delivery", "Is there ongoing support after delivery?", "General questions are welcome via email. Revisions or additional services require separate orders.", 27),
    ("Service Delivery", "Do you work weekends or evenings?", "Orders are processed Monday-Friday during business hours. Fast Track orders may receive weekend attention depending on capacity.", 28),
    
    # Document Pack Services
    ("Document Packs", "Can I choose which documents I want in a document pack?", "Yes. During the intake wizard, you can select specific documents from the pack.", 29),
    ("Document Packs", "Do I automatically get all documents in the pack?", "No. You select which documents you need during the intake process.", 30),
    ("Document Packs", "What is included in the Essential Document Pack?", "Essential pack includes: Rent Arrears Letter, Deposit Refund Letter, Tenant Reference Letter, Rent Receipt, and GDPR Notice.", 31),
    ("Document Packs", "What is included in the Tenancy Document Pack (Plus)?", "Plus pack includes: AST Agreement, Tenancy Renewal, Notice to Quit, Guarantor Agreement, and Rent Increase Notice.", 32),
    ("Document Packs", "What is included in the Ultimate Document Pack (Pro)?", "Pro pack includes: Inventory & Condition Report, Deposit Information Pack, Property Access Notice, and Additional Landlord Notice.", 33),
    ("Document Packs", "Can I upgrade my document pack?", "You would need to purchase the higher tier pack separately. Packs cannot be upgraded mid-order.", 34),
    ("Document Packs", "Are these documents legal advice?", "No. These are template documents populated with your information. They are not legal advice. Consult a solicitor for legal matters.", 35),
    
    # Compliance Services  
    ("Compliance Services", "What is Compliance Vault Pro?", "Compliance Vault Pro is our subscription platform for landlords to track compliance requirements, store documents, and receive automated reminders.", 36),
    ("Compliance Services", "What is HMO Compliance Audit?", "A comprehensive audit of your HMO property against licensing and safety requirements, delivered as a detailed report.", 37),
    ("Compliance Services", "What is Full Compliance Audit?", "A complete compliance review covering all regulatory requirements for your property or portfolio.", 38),
    ("Compliance Services", "Is Compliance Vault Pro a one-off?", "No. CVP is a subscription service billed monthly or annually.", 39),
    
    # Technical Questions
    ("Technical & Usage", "Can I save and come back later?", "The intake wizard auto-saves your progress. You can close your browser and return to complete it.", 40),
    ("Technical & Usage", "What if I made a mistake?", "Contact us immediately after submission. Minor corrections may be possible before work begins.", 41),
    ("Technical & Usage", "Do you keep backups?", "Yes. All documents are stored securely with redundant backups.", 42),
    ("Technical & Usage", "Will I be added to marketing lists?", "Only if you consent. We respect your privacy and follow UK GDPR.", 43),
    ("Technical & Usage", "What if I have multiple properties?", "Our services work for single properties or portfolios. Some services offer bulk discounts.", 44),
]

async def seed_faqs():
    await database.connect()
    db = database.get_db()
    
    print("Seeding FAQ Database...")
    print("=" * 80)
    
    # Clear existing
    deleted = await db.faq_items.delete_many({})
    print(f"Deleted {deleted.deleted_count} existing FAQs")
    
    # Insert new
    count = 0
    for category, question, answer, order in FAQS:
        doc = {
            "faq_id": f"faq_{count}",
            "category": category,
            "question": question,
            "answer": answer,
            "is_active": True,
            "display_order": order,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": "SYSTEM"
        }
        await db.faq_items.insert_one(doc)
        count += 1
    
    print(f"✅ Inserted {count} FAQs")
    print(f"Categories: {len(set(c for c,_,_,_ in FAQS))}")
    
    await database.close()

if __name__ == "__main__":
    asyncio.run(seed_faqs())
