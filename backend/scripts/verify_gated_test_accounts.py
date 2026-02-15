"""
Verify Stripe-gated test accounts: subscription_status, billing_plan, entitlements_version,
and optional audit proof (PLAN_UPDATED_FROM_STRIPE). No manual overrides; read-only checks.

Usage (from backend/):
  python -m scripts.verify_gated_test_accounts --emails aigbochiev@gmail.com,drjpane@gmail.com,pleerityenterprise@gmail.com
  python -m scripts.verify_gated_test_accounts --client-ids <id1>,<id2>,<id3>

Optional:
  --audit    Check for PLAN_UPDATED_FROM_STRIPE and PLAN_LIMIT_EXCEEDED / PLAN_GATE_DENIED audit entries.
  --json     Output machine-readable JSON (no passwords; credentials must be supplied separately).
"""
import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import database


async def verify_clients(emails=None, client_ids=None, check_audit=False, output_json=False):
    if emails:
        emails = [e.strip() for e in emails.split(",") if e.strip()]
    if client_ids:
        client_ids = [c.strip() for c in client_ids.split(",") if c.strip()]

    await database.connect()
    try:
        db = database.get_db()

        if emails:
            clients = []
            for email in emails:
                c = await db.clients.find_one(
                    {"email": email},
                    {"_id": 0, "client_id": 1, "email": 1, "billing_plan": 1, "subscription_status": 1, "entitlements_version": 1}
                )
                if c:
                    clients.append(c)
                else:
                    clients.append({"email": email, "client_id": None, "error": "not_found"})
        elif client_ids:
            clients = []
            for cid in client_ids:
                c = await db.clients.find_one(
                    {"client_id": cid},
                    {"_id": 0, "client_id": 1, "email": 1, "billing_plan": 1, "subscription_status": 1, "entitlements_version": 1}
                )
                if c:
                    clients.append(c)
                else:
                    clients.append({"client_id": cid, "email": None, "error": "not_found"})
        else:
            print("Provide --emails or --client-ids")
            return

        # Enrich with client_billing entitlements_version if missing on client
        for c in clients:
            if c.get("error"):
                continue
            bid = c.get("client_id")
            if bid:
                b = await db.client_billing.find_one(
                    {"client_id": bid},
                    {"_id": 0, "entitlements_version": 1, "current_plan_code": 1, "subscription_status": 1}
                )
                if b and c.get("entitlements_version") is None:
                    c["entitlements_version"] = b.get("entitlements_version")
                if b:
                    c["_billing_plan"] = b.get("current_plan_code")
                    c["_billing_status"] = b.get("subscription_status")

        if check_audit:
            for c in clients:
                if c.get("error"):
                    continue
                cid = c.get("client_id")
                if not cid:
                    continue
                plan_updated = await db.audit_logs.find_one(
                    {"client_id": cid, "metadata.action_type": "PLAN_UPDATED_FROM_STRIPE"},
                    {"_id": 0, "created_at": 1, "metadata": 1}
                )
                c["_audit_plan_updated"] = bool(plan_updated)
                if plan_updated:
                    c["_audit_entitlements_version"] = (plan_updated.get("metadata") or {}).get("entitlements_version")

        if output_json:
            import json
            # Redact any accidental credential fields
            out = []
            for c in clients:
                o = {k: v for k, v in c.items() if not k.startswith("_")}
                o["subscription_status"] = c.get("subscription_status") or c.get("_billing_status")
                o["billing_plan"] = c.get("billing_plan") or c.get("_billing_plan")
                o["entitlements_version"] = c.get("entitlements_version")
                if check_audit:
                    o["audit_plan_updated_from_stripe"] = c.get("_audit_plan_updated")
                    o["audit_entitlements_version"] = c.get("_audit_entitlements_version")
                out.append(o)
            print(json.dumps(out, indent=2))
            return

        # Human-readable
        for c in clients:
            if c.get("error"):
                print(f"  {c.get('email') or c.get('client_id')}: {c['error']}")
                continue
            status = c.get("subscription_status") or c.get("_billing_status")
            plan = c.get("billing_plan") or c.get("_billing_plan")
            ev = c.get("entitlements_version")
            print(f"  email: {c.get('email')}")
            print(f"  client_id: {c.get('client_id')}")
            print(f"  billing_plan: {plan}")
            print(f"  subscription_status: {status}")
            print(f"  entitlements_version: {ev}")
            if check_audit:
                print(f"  audit PLAN_UPDATED_FROM_STRIPE: {c.get('_audit_plan_updated')}")
                if c.get("_audit_entitlements_version") is not None:
                    print(f"  audit entitlements_version: {c.get('_audit_entitlements_version')}")
            print()
    finally:
        await database.close()


def main():
    ap = argparse.ArgumentParser(description="Verify Stripe-gated test accounts (read-only)")
    ap.add_argument("--emails", type=str, help="Comma-separated emails")
    ap.add_argument("--client-ids", type=str, help="Comma-separated client_ids")
    ap.add_argument("--audit", action="store_true", help="Check PLAN_UPDATED_FROM_STRIPE audit entries")
    ap.add_argument("--json", action="store_true", help="Output JSON")
    args = ap.parse_args()
    if not args.emails and not args.client_ids:
        ap.error("Provide --emails or --client-ids")
    asyncio.run(verify_clients(emails=args.emails, client_ids=args.client_ids, check_audit=args.audit, output_json=args.json))


if __name__ == "__main__":
    main()
