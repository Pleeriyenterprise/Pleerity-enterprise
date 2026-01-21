from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db = None
    
    async def connect(self):
        try:
            mongo_url = os.environ['MONGO_URL']
            self.client = AsyncIOMotorClient(mongo_url)
            self.db = self.client[os.environ['DB_NAME']]
            # Verify connection
            await self.db.command("ping")
            logger.info(f"Connected to MongoDB: {os.environ['DB_NAME']}")
            
            # Create indexes for efficient search and lookups
            await self._create_indexes()
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def close(self):
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
    
    def get_db(self):
        return self.db
    
    async def _create_indexes(self):
        """Create MongoDB indexes for efficient queries."""
        try:
            # Client indexes - CRN (customer_reference) is critical for search
            # Use sparse=True to allow multiple null values
            try:
                await self.db.clients.create_index("customer_reference", unique=True, sparse=True)
            except Exception:
                pass  # Index may already exist with different options
            
            try:
                await self.db.clients.create_index("email", unique=True)
            except Exception:
                pass
            
            await self.db.clients.create_index("client_id", unique=True)
            await self.db.clients.create_index("full_name")  # For name search
            
            # Property indexes - for postcode search
            await self.db.properties.create_index("postcode")
            await self.db.properties.create_index("client_id")
            await self.db.properties.create_index("property_id", unique=True)
            await self.db.properties.create_index("compliance_status")
            
            # Portal user indexes
            try:
                await self.db.portal_users.create_index("auth_email", unique=True)
            except Exception:
                pass
            
            await self.db.portal_users.create_index("client_id")
            await self.db.portal_users.create_index("portal_user_id", unique=True)
            
            # Audit log indexes - for timeline queries
            await self.db.audit_logs.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.audit_logs.create_index("created_at")
            await self.db.audit_logs.create_index("action")
            
            # Compliance score history indexes - for trend queries
            await self.db.compliance_score_history.create_index([("client_id", 1), ("date_key", -1)])
            try:
                await self.db.compliance_score_history.create_index(
                    [("client_id", 1), ("date_key", 1)], 
                    unique=True
                )
            except Exception:
                pass  # Index may already exist
            
            logger.info("MongoDB indexes created/verified")
        except Exception as e:
            # Indexes may already exist, log but don't fail
            logger.warning(f"Index creation note: {e}")

# Global database instance
database = Database()

@asynccontextmanager
async def get_db_context():
    """Context manager for standalone scripts to access the database.
    
    Usage in scripts:
        async with get_db_context() as db:
            # db is now connected and ready to use
            await db.clients.find_one(...)
    """
    client = None
    try:
        mongo_url = os.environ['MONGO_URL']
        db_name = os.environ['DB_NAME']
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        # Verify connection
        await db.command("ping")
        logger.info(f"Script connected to MongoDB: {db_name}")
        yield db
    finally:
        if client:
            client.close()
            logger.info("Script MongoDB connection closed")
