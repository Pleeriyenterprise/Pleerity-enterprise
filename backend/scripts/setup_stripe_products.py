"""
Stripe Product Setup Script

Creates/updates Stripe products and prices for all services in the Service Catalogue.
Ensures alignment between backend service_codes and Stripe product metadata.

Run this script to:
1. Create Stripe products for each service
2. Create pricing variants (standard, fast_track, printed)
3. Store Stripe IDs back in the service catalogue
4. Validate existing products

Usage:
    python scripts/setup_stripe_products.py [--dry-run] [--force-update]

Environment:
    STRIPE_SECRET_KEY - Required
    MONGO_URL - Required
"""
import os
import sys
import asyncio
import argparse
import logging
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import stripe
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Service definitions with Stripe-specific metadata
SERVICE_STRIPE_CONFIG = {
    # ========================================
    # AI Automation Services
    # ========================================
    "AI_WF_BLUEPRINT": {
        "name": "Workflow Automation Blueprint",
        "description": "Comprehensive AI-generated workflow automation blueprint for your business",
        "category": "ai_automation",
        "prices": {
            "standard": {"amount": 9900, "nickname": "Standard", "target_hours": 48},
            "fast_track": {"amount": 11900, "nickname": "Fast Track (+£20)", "target_hours": 24},
        }
    },
    "AI_PROC_MAP": {
        "name": "Business Process Mapping",
        "description": "Detailed workflow mapping to identify inefficiencies and automation opportunities",
        "category": "ai_automation",
        "prices": {
            "standard": {"amount": 12900, "nickname": "Standard", "target_hours": 48},
            "fast_track": {"amount": 14900, "nickname": "Fast Track (+£20)", "target_hours": 24},
        }
    },
    "AI_TOOL_RECOMMENDATION": {
        "name": "AI Tool Recommendation Report",
        "description": "Personalised AI tool recommendations based on your business needs",
        "category": "ai_automation",
        "prices": {
            "standard": {"amount": 7900, "nickname": "Standard", "target_hours": 48},
            "fast_track": {"amount": 9900, "nickname": "Fast Track (+£20)", "target_hours": 24},
        }
    },
    
    # ========================================
    # Market Research Services
    # ========================================
    "MR_BASIC": {
        "name": "Market Research – Basic",
        "description": "Concise market overview with competitor insights for early-stage decision-making",
        "category": "market_research",
        "prices": {
            "standard": {"amount": 6900, "nickname": "Standard", "target_hours": 48},
            "fast_track": {"amount": 8900, "nickname": "Fast Track (+£20)", "target_hours": 24},
        }
    },
    "MR_ADV": {
        "name": "Market Research – Advanced",
        "description": "Comprehensive research covering market size, pricing analysis, and competitor positioning",
        "category": "market_research",
        "prices": {
            "standard": {"amount": 14900, "nickname": "Standard", "target_hours": 48},
            "fast_track": {"amount": 16900, "nickname": "Fast Track (+£20)", "target_hours": 24},
        }
    },
    
    # ========================================
    # Compliance Services
    # ========================================
    "FULL_COMPLIANCE_AUDIT": {
        "name": "Full Compliance Audit Report",
        "description": "Comprehensive compliance review covering certificates, licensing, and regulatory risk areas",
        "category": "compliance",
        "prices": {
            "standard": {"amount": 9900, "nickname": "Standard", "target_hours": 72},
            "fast_track": {"amount": 11900, "nickname": "Fast Track (+£20)", "target_hours": 24},
        }
    },
    "HMO_COMPLIANCE_AUDIT": {
        "name": "HMO Compliance Audit",
        "description": "Specialist HMO compliance review for licensing requirements and safety standards",
        "category": "compliance",
        "prices": {
            "standard": {"amount": 7900, "nickname": "Standard", "target_hours": 48},
            "fast_track": {"amount": 9900, "nickname": "Fast Track (+£20)", "target_hours": 24},
        }
    },
    "MOVE_IN_OUT_CHECKLIST": {
        "name": "Move-In / Move-Out Checklist",
        "description": "Structured checklist documenting property condition at tenancy start and end",
        "category": "compliance",
        "prices": {
            "standard": {"amount": 3500, "nickname": "Standard", "target_hours": 48},
            "fast_track": {"amount": 5500, "nickname": "Fast Track (+£20)", "target_hours": 24},
        }
    },
    
    # ========================================
    # Document Packs (with inheritance)
    # ========================================
    "DOC_PACK_ESSENTIAL": {
        "name": "Essential Landlord Document Pack",
        "description": "Core landlord forms: rent arrears letter, deposit refund letter, tenant reference, rent receipt, GDPR notice",
        "category": "document_pack",
        "pack_tier": "ESSENTIAL",
        "includes_docs": 5,
        "prices": {
            "standard": {"amount": 2900, "nickname": "Standard", "target_hours": 72},
            "fast_track": {"amount": 4900, "nickname": "Fast Track (+£20)", "target_hours": 24},
            "printed": {"amount": 5400, "nickname": "With Printed Copy (+£25)", "target_hours": 72},
        }
    },
    "DOC_PACK_PLUS": {
        "name": "Tenancy Legal & Notices Pack",
        "description": "Essential + AST agreement, tenancy renewal, notice to quit, guarantor agreement, rent increase notice",
        "category": "document_pack",
        "pack_tier": "PLUS",
        "inherits_from": "DOC_PACK_ESSENTIAL",
        "includes_docs": 10,
        "prices": {
            "standard": {"amount": 4900, "nickname": "Standard", "target_hours": 72},
            "fast_track": {"amount": 6900, "nickname": "Fast Track (+£20)", "target_hours": 24},
            "printed": {"amount": 7400, "nickname": "With Printed Copy (+£25)", "target_hours": 72},
        }
    },
    "DOC_PACK_PRO": {
        "name": "Ultimate Document Pack",
        "description": "Complete coverage: Essential + Plus + inventory report, deposit info pack, property access notice, additional notices",
        "category": "document_pack",
        "pack_tier": "PRO",
        "inherits_from": "DOC_PACK_PLUS",
        "includes_docs": 14,
        "prices": {
            "standard": {"amount": 7900, "nickname": "Standard", "target_hours": 72},
            "fast_track": {"amount": 9900, "nickname": "Fast Track (+£20)", "target_hours": 24},
            "printed": {"amount": 10400, "nickname": "With Printed Copy (+£25)", "target_hours": 72},
        }
    },
}


class StripeProductSetup:
    """Manages Stripe product and price creation/updates."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.created_products = []
        self.created_prices = []
        self.errors = []
        
    async def setup_all_products(self, force_update: bool = False):
        """Create/update all products and prices in Stripe."""
        logger.info(f"Starting Stripe product setup (dry_run={self.dry_run}, force_update={force_update})")
        
        if not stripe.api_key:
            raise ValueError("STRIPE_SECRET_KEY not set")
        
        # Test Stripe connection
        try:
            stripe.Account.retrieve()
            logger.info("✅ Stripe connection verified")
        except stripe.error.AuthenticationError:
            raise ValueError("Invalid Stripe API key")
        
        for service_code, config in SERVICE_STRIPE_CONFIG.items():
            try:
                await self._setup_product(service_code, config, force_update)
            except Exception as e:
                logger.error(f"❌ Failed to setup {service_code}: {e}")
                self.errors.append({"service_code": service_code, "error": str(e)})
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("STRIPE SETUP SUMMARY")
        logger.info("="*60)
        logger.info(f"Products created/updated: {len(self.created_products)}")
        logger.info(f"Prices created/updated: {len(self.created_prices)}")
        logger.info(f"Errors: {len(self.errors)}")
        
        if self.errors:
            for err in self.errors:
                logger.error(f"  - {err['service_code']}: {err['error']}")
        
        return {
            "products": self.created_products,
            "prices": self.created_prices,
            "errors": self.errors,
        }
    
    async def _setup_product(self, service_code: str, config: dict, force_update: bool):
        """Setup a single product with its prices."""
        logger.info(f"\n📦 Processing: {service_code} - {config['name']}")
        
        # Check if product already exists
        existing_product = await self._find_existing_product(service_code)
        
        if existing_product and not force_update:
            logger.info(f"  ⏭️  Product exists: {existing_product.id}")
            product = existing_product
        else:
            # Create or update product
            product = await self._create_or_update_product(service_code, config, existing_product)
        
        # Setup prices
        for variant_code, price_config in config.get("prices", {}).items():
            await self._setup_price(service_code, variant_code, price_config, product.id)
    
    async def _find_existing_product(self, service_code: str):
        """Find existing Stripe product by service_code in metadata."""
        try:
            products = stripe.Product.search(
                query=f"metadata['service_code']:'{service_code}'"
            )
            if products.data:
                return products.data[0]
        except Exception:
            # Fallback: search by name
            products = stripe.Product.list(limit=100)
            for product in products.auto_paging_iter():
                if product.metadata.get("service_code") == service_code:
                    return product
        return None
    
    async def _create_or_update_product(self, service_code: str, config: dict, existing_product=None):
        """Create or update a Stripe product."""
        product_data = {
            "name": config["name"],
            "description": config["description"],
            "metadata": {
                "service_code": service_code,
                "category": config.get("category", ""),
                "pack_tier": config.get("pack_tier", ""),
                "inherits_from": config.get("inherits_from", ""),
                "includes_docs": str(config.get("includes_docs", 0)),
                "pleerity_managed": "true",
            },
        }
        
        if self.dry_run:
            logger.info(f"  [DRY RUN] Would create/update product: {product_data}")
            return type('obj', (object,), {'id': f'prod_dryrun_{service_code}'})()
        
        if existing_product:
            product = stripe.Product.modify(existing_product.id, **product_data)
            logger.info(f"  ✅ Updated product: {product.id}")
        else:
            product = stripe.Product.create(**product_data)
            logger.info(f"  ✅ Created product: {product.id}")
        
        self.created_products.append({
            "service_code": service_code,
            "product_id": product.id,
            "name": config["name"],
        })
        
        return product
    
    async def _setup_price(self, service_code: str, variant_code: str, price_config: dict, product_id: str):
        """Create or update a price for a product."""
        price_id_lookup = f"price_{service_code}_{variant_code}"
        
        # Check if price exists
        existing_price = await self._find_existing_price(price_id_lookup)
        
        price_data = {
            "unit_amount": price_config["amount"],
            "currency": "gbp",
            "product": product_id,
            "nickname": price_config["nickname"],
            "metadata": {
                "service_code": service_code,
                "variant_code": variant_code,
                "target_hours": str(price_config.get("target_hours", 48)),
                "price_id_lookup": price_id_lookup,
            },
            "lookup_key": price_id_lookup,
        }
        
        if self.dry_run:
            logger.info(f"    [DRY RUN] Would create price: {price_id_lookup} = £{price_config['amount']/100:.2f}")
            return
        
        if existing_price:
            # Can't modify price amount, must create new if different
            if existing_price.unit_amount != price_config["amount"]:
                # Archive old price and create new
                stripe.Price.modify(existing_price.id, active=False)
                price = stripe.Price.create(**price_data)
                logger.info(f"    ✅ Replaced price: {price_id_lookup} = £{price_config['amount']/100:.2f}")
            else:
                logger.info(f"    ⏭️  Price unchanged: {price_id_lookup}")
                return
        else:
            price = stripe.Price.create(**price_data)
            logger.info(f"    ✅ Created price: {price_id_lookup} = £{price_config['amount']/100:.2f}")
        
        self.created_prices.append({
            "service_code": service_code,
            "variant_code": variant_code,
            "price_id": price.id,
            "lookup_key": price_id_lookup,
            "amount": price_config["amount"],
        })
    
    async def _find_existing_price(self, lookup_key: str):
        """Find existing price by lookup key."""
        try:
            prices = stripe.Price.list(lookup_keys=[lookup_key], limit=1)
            if prices.data:
                return prices.data[0]
        except Exception:
            pass
        return None
    
    async def sync_to_database(self):
        """Sync created Stripe IDs back to the service catalogue."""
        if self.dry_run:
            logger.info("[DRY RUN] Would sync Stripe IDs to database")
            return
        
        mongo_url = os.getenv("MONGO_URL")
        db_name = os.getenv("DB_NAME", "compliance_vault_pro")
        
        if not mongo_url:
            logger.warning("MONGO_URL not set, skipping database sync")
            return
        
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        # Update service catalogue with Stripe price IDs
        for price_info in self.created_prices:
            service_code = price_info["service_code"]
            variant_code = price_info["variant_code"]
            stripe_price_id = price_info["price_id"]
            
            # Update the pricing_variants array
            await db.service_catalogue_v2.update_one(
                {
                    "service_code": service_code,
                    "pricing_variants.variant_code": variant_code
                },
                {
                    "$set": {
                        f"pricing_variants.$.stripe_price_id": stripe_price_id,
                        "updated_at": datetime.now(timezone.utc),
                    }
                }
            )
        
        logger.info(f"✅ Synced {len(self.created_prices)} Stripe price IDs to database")
        client.close()
    
    async def validate_alignment(self):
        """Validate that all service codes have corresponding Stripe products."""
        logger.info("\n" + "="*60)
        logger.info("VALIDATING STRIPE ALIGNMENT")
        logger.info("="*60)
        
        issues = []
        
        for service_code in SERVICE_STRIPE_CONFIG.keys():
            product = await self._find_existing_product(service_code)
            if not product:
                issues.append(f"❌ Missing product: {service_code}")
            else:
                # Check prices
                for variant_code in SERVICE_STRIPE_CONFIG[service_code].get("prices", {}).keys():
                    price_lookup = f"price_{service_code}_{variant_code}"
                    price = await self._find_existing_price(price_lookup)
                    if not price:
                        issues.append(f"❌ Missing price: {price_lookup}")
                    else:
                        logger.info(f"✅ {service_code}/{variant_code} -> {price.id}")
        
        if issues:
            logger.warning("\nAlignment Issues Found:")
            for issue in issues:
                logger.warning(f"  {issue}")
        else:
            logger.info("\n✅ All services aligned with Stripe")
        
        return issues


async def main():
    parser = argparse.ArgumentParser(description="Setup Stripe products for Pleerity services")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without making them")
    parser.add_argument("--force-update", action="store_true", help="Force update existing products")
    parser.add_argument("--validate-only", action="store_true", help="Only validate alignment, don't create")
    parser.add_argument("--sync-db", action="store_true", help="Sync Stripe IDs to database after creation")
    
    args = parser.parse_args()
    
    setup = StripeProductSetup(dry_run=args.dry_run)
    
    if args.validate_only:
        await setup.validate_alignment()
    else:
        await setup.setup_all_products(force_update=args.force_update)
        
        if args.sync_db and not args.dry_run:
            await setup.sync_to_database()
        
        await setup.validate_alignment()


if __name__ == "__main__":
    asyncio.run(main())
