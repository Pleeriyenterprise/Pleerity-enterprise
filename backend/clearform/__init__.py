"""
ClearForm - Intent-Driven Paperwork Assistant
=============================================

A standalone SaaS product with credit-based economy for professional document generation.

Phase 1 Scope:
- 3 document types (intent-based)
- Credit wallet + deduction on generation
- Manual Stripe top-ups + subscription → monthly grant
- Credit expiry logic
- Document vault

ISOLATION RULES:
- ClearForm must NOT use: Service Catalogue, Orders, CVP subscriptions, Document Pack Orchestrator
- ClearForm must use: Intent-based flow, Credit economy, Document vault

This module is completely isolated from Pleerity's core business logic.
"""

__version__ = "1.0.0"
__product__ = "ClearForm"
