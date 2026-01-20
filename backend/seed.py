"""
Seed script to create initial admin user and test data for Compliance Vault Pro
Run this once to set up the system for testing
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def seed_database():
    # Connect to MongoDB
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("🌱 Seeding Compliance Vault Pro database...")
    
    # Create admin user
    admin_exists = await db.portal_users.find_one({"auth_email": "admin@pleerity.com"})
    
    if not admin_exists:
        admin_user = {
            "portal_user_id": "admin-001",
            "client_id": None,
            "auth_email": "admin@pleerity.com",
            "password_hash": pwd_context.hash("Admin123!"),
            "role": "ROLE_ADMIN",
            "status": "ACTIVE",
            "password_status": "SET",
            "must_set_password": False,
            "last_login": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.portal_users.insert_one(admin_user)
        print("✅ Admin user created:")
        print("   Email: admin@pleerity.com")
        print("   Password: Admin123!")
    else:
        print("ℹ️  Admin user already exists")
    
    print("\n✅ Database seeding complete!")
    print("\n📝 Quick Start Guide:")
    print("   1. Admin Login: https://compliance-vault-2.preview.emergentagent.com/admin/signin")
    print("   2. Client Signup: https://compliance-vault-2.preview.emergentagent.com/intake/start")
    print("\n🔐 Admin Credentials:")
    print("   Email: admin@pleerity.com")
    print("   Password: Admin123!")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_database())
