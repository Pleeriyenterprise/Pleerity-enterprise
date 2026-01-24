"""
Order Email Templates - Branded HTML + plaintext email templates for the Orders workflow.
Includes: Client Input Required, Client Response Received, Order Approved & Processing
"""
from typing import Dict, Any, Optional
import os

# Branding constants
COMPANY_NAME = "Pleerity Enterprise Ltd"
BRAND_COLOR_PRIMARY = "#0B1D3A"  # Midnight blue
BRAND_COLOR_ACCENT = "#00B8A9"  # Electric teal
SUPPORT_EMAIL = os.getenv("EMAIL_SENDER", "info@pleerityenterprise.co.uk")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://pleerity.com")


def _build_email_header(title: str, subtitle: Optional[str] = None, badge_text: Optional[str] = None) -> str:
    """Build consistent branded header."""
    badge_html = ""
    if badge_text:
        badge_html = f'<span style="background-color: {BRAND_COLOR_ACCENT}; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 12px; margin-left: 10px;">{badge_text}</span>'
    
    subtitle_html = ""
    if subtitle:
        subtitle_html = f'<p style="margin: 10px 0 0 0; opacity: 0.9; font-size: 14px;">{subtitle}</p>'
    
    return f"""
        <div style="background-color: {BRAND_COLOR_PRIMARY}; padding: 25px; border-radius: 8px 8px 0 0;">
            <h1 style="color: {BRAND_COLOR_ACCENT}; margin: 0; font-size: 22px; display: inline-block;">{title}</h1>
            {badge_html}
            {subtitle_html}
        </div>
    """


def _build_email_footer(order_reference: Optional[str] = None) -> str:
    """Build consistent branded footer."""
    ref_line = ""
    if order_reference:
        ref_line = f"<br><strong>Order Reference:</strong> {order_reference}"
    
    return f"""
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        <div style="background-color: #f8fafc; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
            <p style="color: #64748b; font-size: 13px; margin: 0;">
                {COMPANY_NAME}<br>
                AI-Driven Solutions & Property Compliance{ref_line}
            </p>
        </div>
        <p style="color: #94a3b8; font-size: 11px; margin: 0;">
            If you have questions, please contact us at <a href="mailto:{SUPPORT_EMAIL}" style="color: {BRAND_COLOR_ACCENT};">{SUPPORT_EMAIL}</a>
        </p>
    """


def _build_text_footer(order_reference: Optional[str] = None) -> str:
    """Build consistent plaintext footer."""
    ref_line = f"\nOrder Reference: {order_reference}" if order_reference else ""
    return f"""
--
{COMPANY_NAME}
AI-Driven Solutions & Property Compliance{ref_line}

Questions? Contact us at {SUPPORT_EMAIL}
"""


# ============================================================================
# ORDER CONFIRMATION EMAIL (Sent to customer after payment)
# ============================================================================

def build_order_confirmation_email(
    client_name: str,
    order_reference: str,
    service_name: str,
    total_amount: str,
    order_date: str,
    estimated_delivery: str = "48 hours",
    view_order_link: str = "",
) -> Dict[str, str]:
    """
    Build 'Order Confirmation' email - sent to customer after successful payment.
    
    Returns dict with 'subject', 'html', 'text' keys.
    """
    subject = f"Order Confirmed - {order_reference}"
    
    cta_html = ""
    cta_text = ""
    if view_order_link:
        cta_html = f"""
            <div style="text-align: center; margin: 25px 0;">
                <a href="{view_order_link}" style="background-color: {BRAND_COLOR_ACCENT}; color: white; 
                          padding: 12px 30px; text-decoration: none; border-radius: 6px; 
                          display: inline-block; font-weight: 600;">
                    View Your Order
                </a>
            </div>
        """
        cta_text = f"\nView your order: {view_order_link}\n"
    
    html = f"""
    <html>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto;">
        {_build_email_header("Order Confirmed!", "Thank you for your order", order_reference)}
        
        <div style="padding: 25px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px; background: white;">
            <p style="margin-bottom: 20px;">Hi {client_name},</p>
            
            <p style="margin-bottom: 20px;">
                Thank you for your order! We've received your payment and your order is now being processed by our team.
            </p>
            
            <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: {BRAND_COLOR_PRIMARY}; margin: 0 0 15px 0; font-size: 16px;">Order Summary</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; color: #64748b;">Order Reference:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: 600; font-family: monospace;">{order_reference}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #64748b;">Service:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: 600;">{service_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #64748b;">Order Date:</td>
                        <td style="padding: 8px 0; text-align: right;">{order_date}</td>
                    </tr>
                    <tr style="border-top: 1px solid #e2e8f0;">
                        <td style="padding: 12px 0 8px 0; color: #64748b; font-weight: 600;">Total Paid:</td>
                        <td style="padding: 12px 0 8px 0; text-align: right; font-weight: 700; font-size: 18px; color: {BRAND_COLOR_PRIMARY};">{total_amount}</td>
                    </tr>
                </table>
            </div>
            
            <div style="background-color: #ecfdf5; border-left: 4px solid #10b981; padding: 15px; margin: 20px 0;">
                <p style="margin: 0; color: #065f46;">
                    <strong>Estimated Delivery:</strong> Within {estimated_delivery}
                </p>
            </div>
            
            <h3 style="color: {BRAND_COLOR_PRIMARY}; margin: 25px 0 15px 0; font-size: 16px;">What Happens Next?</h3>
            <ol style="margin: 0; padding-left: 20px; color: #475569;">
                <li style="margin: 10px 0;">Our team will review your order and begin processing</li>
                <li style="margin: 10px 0;">Your documents will be generated based on the information you provided</li>
                <li style="margin: 10px 0;">You'll receive an email when your order is ready for download</li>
            </ol>
            
            {cta_html}
            
            <p style="margin-top: 25px; color: #64748b;">
                If you have any questions about your order, please reply to this email or contact us at 
                <a href="mailto:{SUPPORT_EMAIL}" style="color: {BRAND_COLOR_ACCENT};">{SUPPORT_EMAIL}</a>
            </p>
            
            {_build_email_footer(order_reference)}
        </div>
    </body>
    </html>
    """
    
    text = f"""
Order Confirmed - {order_reference}

Hi {client_name},

Thank you for your order! We've received your payment and your order is now being processed.

ORDER SUMMARY
-------------
Order Reference: {order_reference}
Service: {service_name}
Order Date: {order_date}
Total Paid: {total_amount}

Estimated Delivery: Within {estimated_delivery}

WHAT HAPPENS NEXT?
------------------
1. Our team will review your order and begin processing
2. Your documents will be generated based on the information you provided
3. You'll receive an email when your order is ready for download
{cta_text}
If you have any questions, please contact us at {SUPPORT_EMAIL}

{_build_text_footer(order_reference)}
"""
    
    return {
        "subject": subject,
        "html": html,
        "text": text,
    }


# ============================================================================
# CLIENT INPUT REQUIRED EMAIL
# ============================================================================

def build_client_input_required_email(
    client_name: str,
    order_reference: str,
    service_name: str,
    admin_notes: str,
    requested_fields: list,
    deadline: Optional[str] = None,
    provide_info_link: str = "",
) -> Dict[str, str]:
    """
    Build 'Client Input Required' email - sent when admin requests more info.
    
    Returns dict with 'subject', 'html', 'text' keys.
    """
    subject = f"Action Required: We need more information for your order {order_reference}"
    
    # Build requested fields list
    fields_html = ""
    fields_text = ""
    if requested_fields:
        fields_html = "<ul style='margin: 10px 0; padding-left: 20px;'>"
        for field in requested_fields:
            fields_html += f"<li style='margin: 5px 0; color: #334155;'>{field}</li>"
        fields_html += "</ul>"
        fields_text = "\n".join([f"  • {field}" for field in requested_fields])
    
    deadline_html = ""
    deadline_text = ""
    if deadline:
        deadline_html = f"""
            <div style="background-color: #fef3c7; border: 1px solid #f59e0b; border-radius: 6px; padding: 12px; margin: 15px 0;">
                <p style="margin: 0; color: #92400e; font-size: 14px;">
                    ⏰ Please respond by: <strong>{deadline}</strong>
                </p>
            </div>
        """
        deadline_text = f"\n⏰ Please respond by: {deadline}\n"
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #1e293b;">
        {_build_email_header("📋 Information Required", f"Order Reference: {order_reference}", order_reference)}
        
        <div style="padding: 25px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px; background: white;">
            <p style="margin-top: 0;">Hello {client_name},</p>
            
            <p>We're processing your <strong>{service_name}</strong> order and need some additional information to continue.</p>
            
            <div style="background-color: #f1f5f9; border-left: 4px solid {BRAND_COLOR_ACCENT}; padding: 15px; margin: 20px 0; border-radius: 0 6px 6px 0;">
                <p style="margin: 0 0 5px 0; font-weight: bold; color: {BRAND_COLOR_PRIMARY};">What we need from you:</p>
                <p style="margin: 0; color: #475569; white-space: pre-wrap;">{admin_notes}</p>
            </div>
            
            {f'<p style="font-weight: bold; margin-bottom: 5px;">Requested information:</p>{fields_html}' if fields_html else ''}
            
            {deadline_html}
            
            <p style="margin: 25px 0;">
                <a href="{provide_info_link}" 
                   style="background-color: {BRAND_COLOR_ACCENT}; color: white; padding: 14px 28px; 
                          text-decoration: none; border-radius: 6px; display: inline-block;
                          font-weight: bold; font-size: 16px;">
                    Provide Information
                </a>
            </p>
            
            <p style="color: #64748b; font-size: 14px;">
                Once you submit the requested information, we'll automatically resume processing your order.
            </p>
        </div>
        
        {_build_email_footer(order_reference)}
    </body>
    </html>
    """
    
    text = f"""
{COMPANY_NAME}
=====================

📋 INFORMATION REQUIRED
Order Reference: {order_reference}

Hello {client_name},

We're processing your {service_name} order and need some additional information to continue.

WHAT WE NEED FROM YOU:
----------------------
{admin_notes}

{f'REQUESTED INFORMATION:{chr(10)}{fields_text}' if fields_text else ''}
{deadline_text}
To provide this information, please visit:
{provide_info_link}

Once you submit the requested information, we'll automatically resume processing your order.

{_build_text_footer(order_reference)}
"""
    
    return {"subject": subject, "html": html, "text": text}


# ============================================================================
# CLIENT RESPONSE RECEIVED EMAIL (Admin Notification)
# ============================================================================

def build_client_response_received_email(
    admin_name: str,
    order_reference: str,
    service_name: str,
    client_name: str,
    client_email: str,
    submitted_fields: Dict[str, Any],
    files_uploaded: list,
    order_link: str,
) -> Dict[str, str]:
    """
    Build 'Client Response Received' email - sent to admin when client submits info.
    
    Returns dict with 'subject', 'html', 'text' keys.
    """
    subject = f"Client info received — Order {order_reference}"
    
    # Build fields summary
    fields_html = ""
    fields_text = ""
    if submitted_fields:
        fields_html = "<table style='width: 100%; border-collapse: collapse; margin: 10px 0;'>"
        for key, value in submitted_fields.items():
            display_key = key.replace("_", " ").title()
            fields_html += f"""
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; color: #64748b; width: 40%;">{display_key}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; font-weight: 500;">{value}</td>
                </tr>
            """
        fields_html += "</table>"
        fields_text = "\n".join([f"  {k.replace('_', ' ').title()}: {v}" for k, v in submitted_fields.items()])
    
    # Build files list
    files_html = ""
    files_text = ""
    if files_uploaded:
        files_html = "<ul style='margin: 10px 0; padding-left: 20px;'>"
        for f in files_uploaded:
            files_html += f"<li style='margin: 5px 0;'>{f.get('filename', 'Unknown file')}</li>"
        files_html += "</ul>"
        files_text = "\n".join([f"  • {f.get('filename', 'Unknown file')}" for f in files_uploaded])
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #1e293b;">
        {_build_email_header("✅ Client Info Received", f"Order {order_reference} is ready for review", order_reference)}
        
        <div style="padding: 25px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px; background: white;">
            <p style="margin-top: 0;">Hi {admin_name},</p>
            
            <p>The client has submitted the requested information for order <strong>{order_reference}</strong>.</p>
            
            <div style="background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 6px; padding: 15px; margin: 20px 0;">
                <p style="margin: 0 0 10px 0; font-weight: bold; color: #166534;">Order Details</p>
                <p style="margin: 5px 0; color: #334155;"><strong>Service:</strong> {service_name}</p>
                <p style="margin: 5px 0; color: #334155;"><strong>Client:</strong> {client_name} ({client_email})</p>
            </div>
            
            {f'<p style="font-weight: bold; margin-bottom: 5px;">Submitted Information:</p>{fields_html}' if fields_html else ''}
            
            {f'<p style="font-weight: bold; margin-bottom: 5px;">Files Uploaded:</p>{files_html}' if files_html else ''}
            
            <p style="margin: 25px 0;">
                <a href="{order_link}" 
                   style="background-color: {BRAND_COLOR_ACCENT}; color: white; padding: 12px 24px; 
                          text-decoration: none; border-radius: 6px; display: inline-block;
                          font-weight: bold;">
                    Review Order
                </a>
            </p>
            
            <p style="color: #64748b; font-size: 14px;">
                The order has been automatically moved back to <strong>Internal Review</strong>. 
                Please review the submitted information and take action.
            </p>
        </div>
        
        {_build_email_footer(order_reference)}
    </body>
    </html>
    """
    
    text = f"""
{COMPANY_NAME}
=====================

✅ CLIENT INFO RECEIVED
Order {order_reference} is ready for review

Hi {admin_name},

The client has submitted the requested information for order {order_reference}.

ORDER DETAILS:
--------------
Service: {service_name}
Client: {client_name} ({client_email})

{f'SUBMITTED INFORMATION:{chr(10)}{fields_text}' if fields_text else ''}

{f'FILES UPLOADED:{chr(10)}{files_text}' if files_text else ''}

To review this order, visit:
{order_link}

The order has been automatically moved back to Internal Review.
Please review the submitted information and take action.

{_build_text_footer(order_reference)}
"""
    
    return {"subject": subject, "html": html, "text": text}


# ============================================================================
# ORDER APPROVED & PROCESSING EMAIL
# ============================================================================

def build_order_approved_email(
    client_name: str,
    order_reference: str,
    service_name: str,
    estimated_delivery: Optional[str] = None,
    portal_link: str = "",
) -> Dict[str, str]:
    """
    Build 'Order Approved & Processing' email - sent to client after admin approval.
    
    Returns dict with 'subject', 'html', 'text' keys.
    """
    subject = f"Your order {order_reference} has been approved and is being finalized"
    
    delivery_html = ""
    delivery_text = ""
    if estimated_delivery:
        delivery_html = f"""
            <div style="background-color: #dbeafe; border: 1px solid #3b82f6; border-radius: 6px; padding: 12px; margin: 15px 0;">
                <p style="margin: 0; color: #1e40af; font-size: 14px;">
                    📅 Estimated Delivery: <strong>{estimated_delivery}</strong>
                </p>
            </div>
        """
        delivery_text = f"\n📅 Estimated Delivery: {estimated_delivery}\n"
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #1e293b;">
        {_build_email_header("✅ Order Approved", "Your documents are being finalized", order_reference)}
        
        <div style="padding: 25px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px; background: white;">
            <p style="margin-top: 0;">Hello {client_name},</p>
            
            <p>Great news! Your <strong>{service_name}</strong> order has been reviewed and approved.</p>
            
            <div style="background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 6px; padding: 20px; margin: 20px 0; text-align: center;">
                <p style="margin: 0 0 10px 0; font-size: 18px; font-weight: bold; color: #166534;">
                    ✓ Review Complete
                </p>
                <p style="margin: 0; color: #334155;">
                    We're now finalizing your documents for delivery.
                </p>
            </div>
            
            {delivery_html}
            
            <p><strong>What happens next?</strong></p>
            <ul style="color: #475569; padding-left: 20px;">
                <li>Your documents are being prepared for delivery</li>
                <li>You'll receive another email when they're ready</li>
                <li>Documents will be available in your portal</li>
            </ul>
            
            <p style="margin: 25px 0;">
                <a href="{portal_link}" 
                   style="background-color: {BRAND_COLOR_ACCENT}; color: white; padding: 12px 24px; 
                          text-decoration: none; border-radius: 6px; display: inline-block;
                          font-weight: bold;">
                    View Your Dashboard
                </a>
            </p>
            
            <p style="color: #64748b; font-size: 14px;">
                Thank you for choosing {COMPANY_NAME}. We appreciate your business!
            </p>
        </div>
        
        {_build_email_footer(order_reference)}
    </body>
    </html>
    """
    
    text = f"""
{COMPANY_NAME}
=====================

✅ ORDER APPROVED
Your documents are being finalized
Order Reference: {order_reference}

Hello {client_name},

Great news! Your {service_name} order has been reviewed and approved.

✓ Review Complete
We're now finalizing your documents for delivery.
{delivery_text}
WHAT HAPPENS NEXT:
------------------
• Your documents are being prepared for delivery
• You'll receive another email when they're ready
• Documents will be available in your portal

To view your dashboard, visit:
{portal_link}

Thank you for choosing {COMPANY_NAME}. We appreciate your business!

{_build_text_footer(order_reference)}
"""
    
    return {"subject": subject, "html": html, "text": text}


# ============================================================================
# ORDER DELIVERED EMAIL
# ============================================================================

def build_order_delivered_email(
    client_name: str,
    order_reference: str,
    service_name: str,
    documents: list,
    download_link: str = "",
    portal_link: str = "",
) -> Dict[str, str]:
    """
    Build 'Order Delivered' email - sent when documents are ready.
    
    Returns dict with 'subject', 'html', 'text' keys.
    """
    subject = f"Your documents are ready — Order {order_reference}"
    
    # Build documents list
    docs_html = "<ul style='margin: 10px 0; padding-left: 20px;'>"
    docs_text = ""
    for doc in documents:
        docs_html += f"<li style='margin: 5px 0;'>{doc.get('name', 'Document')}</li>"
        docs_text += f"  • {doc.get('name', 'Document')}\n"
    docs_html += "</ul>"
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #1e293b;">
        {_build_email_header("📦 Documents Ready", "Your order has been completed", order_reference)}
        
        <div style="padding: 25px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px; background: white;">
            <p style="margin-top: 0;">Hello {client_name},</p>
            
            <p>Your <strong>{service_name}</strong> order is complete and your documents are ready!</p>
            
            <div style="background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 6px; padding: 20px; margin: 20px 0;">
                <p style="margin: 0 0 10px 0; font-weight: bold; color: #166534;">Included Documents:</p>
                {docs_html}
            </div>
            
            <p style="margin: 25px 0; text-align: center;">
                <a href="{download_link}" 
                   style="background-color: {BRAND_COLOR_ACCENT}; color: white; padding: 14px 28px; 
                          text-decoration: none; border-radius: 6px; display: inline-block;
                          font-weight: bold; font-size: 16px;">
                    Download Documents
                </a>
            </p>
            
            <p style="color: #64748b; font-size: 14px; text-align: center;">
                Your documents are also available in your <a href="{portal_link}" style="color: {BRAND_COLOR_ACCENT};">portal dashboard</a>.
            </p>
            
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 25px 0;">
            
            <p style="color: #64748b; font-size: 14px;">
                <strong>Need help?</strong> If you have any questions about your documents, 
                please don't hesitate to contact us at <a href="mailto:{SUPPORT_EMAIL}" style="color: {BRAND_COLOR_ACCENT};">{SUPPORT_EMAIL}</a>.
            </p>
        </div>
        
        {_build_email_footer(order_reference)}
    </body>
    </html>
    """
    
    text = f"""
{COMPANY_NAME}
=====================

📦 DOCUMENTS READY
Your order has been completed
Order Reference: {order_reference}

Hello {client_name},

Your {service_name} order is complete and your documents are ready!

INCLUDED DOCUMENTS:
-------------------
{docs_text}

To download your documents, visit:
{download_link}

Your documents are also available in your portal dashboard:
{portal_link}

NEED HELP?
----------
If you have any questions about your documents, please contact us at {SUPPORT_EMAIL}.

{_build_text_footer(order_reference)}
"""
    
    return {"subject": subject, "html": html, "text": text}


# ============================================================================
# ADMIN NOTIFICATION: ORDER NEEDS REVIEW
# ============================================================================

def build_admin_order_review_email(
    admin_name: str,
    order_reference: str,
    service_name: str,
    client_name: str,
    client_email: str,
    order_link: str,
) -> Dict[str, str]:
    """
    Build admin notification email when order reaches INTERNAL_REVIEW.
    
    Returns dict with 'subject', 'html', 'text' keys.
    """
    subject = f"Order {order_reference} Ready for Review"
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #1e293b;">
        {_build_email_header("🔔 Order Ready for Review", "Action required in the admin pipeline", order_reference)}
        
        <div style="padding: 25px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px; background: white;">
            <p style="margin-top: 0;">Hi {admin_name},</p>
            
            <p>A new order has reached the <strong>Internal Review</strong> stage and requires your attention.</p>
            
            <div style="background-color: #fef3c7; border: 1px solid #f59e0b; border-radius: 6px; padding: 15px; margin: 20px 0;">
                <p style="margin: 0 0 10px 0; font-weight: bold; color: #92400e;">Order Details</p>
                <p style="margin: 5px 0; color: #334155;"><strong>Reference:</strong> {order_reference}</p>
                <p style="margin: 5px 0; color: #334155;"><strong>Service:</strong> {service_name}</p>
                <p style="margin: 5px 0; color: #334155;"><strong>Client:</strong> {client_name} ({client_email})</p>
            </div>
            
            <p style="margin: 25px 0;">
                <a href="{order_link}" 
                   style="background-color: {BRAND_COLOR_ACCENT}; color: white; padding: 12px 24px; 
                          text-decoration: none; border-radius: 6px; display: inline-block;
                          font-weight: bold;">
                    Review Order Now
                </a>
            </p>
            
            <p style="color: #64748b; font-size: 14px;">
                Available actions: <strong>Approve & Finalize</strong>, <strong>Request Regeneration</strong>, or <strong>Request More Info</strong>
            </p>
        </div>
        
        {_build_email_footer(order_reference)}
    </body>
    </html>
    """
    
    text = f"""
{COMPANY_NAME}
=====================

🔔 ORDER READY FOR REVIEW
Action required in the admin pipeline
Order Reference: {order_reference}

Hi {admin_name},

A new order has reached the Internal Review stage and requires your attention.

ORDER DETAILS:
--------------
Reference: {order_reference}
Service: {service_name}
Client: {client_name} ({client_email})

To review this order, visit:
{order_link}

Available actions: Approve & Finalize, Request Regeneration, or Request More Info

{_build_text_footer(order_reference)}
"""
    
    return {"subject": subject, "html": html, "text": text}
