"""
Configurable rate limits and session-related timeouts (env-driven).

Override via environment variables in production; defaults align with enterprise security policy.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    try:
        v = int(os.getenv(name, str(default)))
        return max(1, v)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class SecurityLimits:
    # Login (failed attempts — see rate_limiter peek/record in auth routes)
    login_client_ip_max: int
    login_client_email_max: int
    login_window_minutes: int
    login_admin_ip_max: int
    login_admin_window_minutes: int
    login_contractor_ip_max: int
    login_contractor_window_minutes: int

    # Forgot / reset
    forgot_password_ip_max: int
    forgot_password_ip_window_minutes: int
    forgot_password_email_max: int
    forgot_password_email_window_minutes: int
    set_password_ip_max: int
    set_password_ip_window_minutes: int

    # Activation resend (per client id)
    resend_activation_max_per_hour: int

    # Public lead / marketing capture (shared bucket per IP per hour)
    leads_public_per_hour: int

    # Public HTML forms (contact, partnership, etc.) — unified per-IP hourly
    public_form_per_ip_per_hour: int

    # Risk check (public)
    risk_check_preview_per_ip_per_hour: int
    risk_check_report_per_ip_per_hour: int
    risk_check_activate_per_ip_per_hour: int

    # Assistant (authenticated client) — per IP per hour
    assistant_per_ip_per_hour: int

    # Document upload (per client per hour)
    document_upload_per_client_per_hour: int

    # Report generation / export (per client per hour)
    report_export_per_client_per_hour: int

    # Admin staff: heavy exports (audit CSV/PDF, etc.) per portal_user per hour
    admin_export_per_staff_per_hour: int

    # Admin staff: manual job / provisioning runner triggers per hour
    admin_job_run_per_staff_per_hour: int

    # Maintenance issue create (per client per hour; abuse guard)
    maintenance_issue_create_per_client_per_hour: int

    # Maintenance work order create (per client per hour)
    maintenance_work_order_create_per_client_per_hour: int

    # Step-up token
    step_up_token_minutes: int


def load_security_limits() -> SecurityLimits:
    return SecurityLimits(
        login_client_ip_max=_int("RATE_LIMIT_LOGIN_CLIENT_IP_MAX", 5),
        login_client_email_max=_int("RATE_LIMIT_LOGIN_CLIENT_EMAIL_MAX", 5),
        login_window_minutes=_int("RATE_LIMIT_LOGIN_WINDOW_MINUTES", 10),
        login_admin_ip_max=_int("RATE_LIMIT_LOGIN_ADMIN_IP_MAX", 5),
        login_admin_window_minutes=_int("RATE_LIMIT_LOGIN_ADMIN_WINDOW_MINUTES", 10),
        login_contractor_ip_max=_int("RATE_LIMIT_LOGIN_CONTRACTOR_IP_MAX", 10),
        login_contractor_window_minutes=_int("RATE_LIMIT_LOGIN_CONTRACTOR_WINDOW_MINUTES", 15),
        forgot_password_ip_max=_int("RATE_LIMIT_FORGOT_PASSWORD_IP_MAX", 5),
        forgot_password_ip_window_minutes=_int("RATE_LIMIT_FORGOT_PASSWORD_IP_WINDOW_MINUTES", 60),
        forgot_password_email_max=_int("RATE_LIMIT_FORGOT_PASSWORD_EMAIL_MAX", 3),
        forgot_password_email_window_minutes=_int("RATE_LIMIT_FORGOT_PASSWORD_EMAIL_WINDOW_MINUTES", 60),
        set_password_ip_max=_int("RATE_LIMIT_SET_PASSWORD_IP_MAX", 5),
        set_password_ip_window_minutes=_int("RATE_LIMIT_SET_PASSWORD_IP_WINDOW_MINUTES", 30),
        resend_activation_max_per_hour=_int("RATE_LIMIT_RESEND_ACTIVATION_PER_HOUR", 3),
        leads_public_per_hour=_int("RATE_LIMIT_LEADS_PUBLIC_PER_HOUR", 15),
        public_form_per_ip_per_hour=_int("RATE_LIMIT_PUBLIC_FORM_PER_IP_HOUR", 15),
        risk_check_preview_per_ip_per_hour=_int("RATE_LIMIT_RISK_CHECK_PREVIEW_PER_HOUR", 10),
        risk_check_report_per_ip_per_hour=_int("RATE_LIMIT_RISK_CHECK_REPORT_PER_HOUR", 10),
        risk_check_activate_per_ip_per_hour=_int("RATE_LIMIT_RISK_CHECK_ACTIVATE_PER_HOUR", 20),
        assistant_per_ip_per_hour=_int("RATE_LIMIT_ASSISTANT_IP_PER_HOUR", 60),
        document_upload_per_client_per_hour=_int("RATE_LIMIT_DOCUMENT_UPLOAD_PER_CLIENT_HOUR", 20),
        report_export_per_client_per_hour=_int("RATE_LIMIT_REPORT_EXPORT_PER_CLIENT_HOUR", 10),
        admin_export_per_staff_per_hour=_int("RATE_LIMIT_ADMIN_EXPORT_PER_STAFF_HOUR", 5),
        admin_job_run_per_staff_per_hour=_int("RATE_LIMIT_ADMIN_JOB_RUN_PER_STAFF_HOUR", 10),
        maintenance_issue_create_per_client_per_hour=_int(
            "RATE_LIMIT_MAINTENANCE_ISSUE_CREATE_PER_CLIENT_HOUR", 30
        ),
        maintenance_work_order_create_per_client_per_hour=_int(
            "RATE_LIMIT_MAINTENANCE_WORK_ORDER_CREATE_PER_CLIENT_HOUR", 20
        ),
        step_up_token_minutes=_int("STEP_UP_TOKEN_MINUTES", 10),
    )


security_limits = load_security_limits()
