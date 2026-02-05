"""
Fix Document Pack Prompt Ambiguity
Archives individual document prompts and ensures DOC_PACK_ORCHESTRATOR is active
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import database
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fix_prompt_ambiguity():
    """Fix document pack prompt ambiguity by archiving individual doc prompts."""
    await database.connect()
    db = database.get_db()
    
    logger.info("=" * 80)
    logger.info("FIXING DOCUMENT PACK PROMPT AMBIGUITY")
    logger.info("=" * 80)
    
    pack_services = ['DOC_PACK_ESSENTIAL', 'DOC_PACK_PLUS', 'DOC_PACK_PRO']
    
    # Archive all individual document prompts for pack services
    logger.info("\n1. Archiving individual document prompts...")
    
    total_archived = 0
    for pack_code in pack_services:
        result = await db.prompt_templates.update_many(
            {'service_code': pack_code, 'status': 'ACTIVE'},
            {'$set': {
                'status': 'ARCHIVED',
                'archived_reason': 'Individual docs handled by DOC_PACK_ORCHESTRATOR',
                'archived_at': datetime.now(timezone.utc)
            }}
        )
        
        if result.modified_count > 0:
            logger.info(f"   {pack_code}: Archived {result.modified_count} prompts")
            total_archived += result.modified_count
    
    logger.info(f"\n   ✅ Total archived: {total_archived} prompts")
    
    # Check if DOC_PACK_ORCHESTRATOR exists
    logger.info("\n2. Checking DOC_PACK_ORCHESTRATOR...")
    
    orchestrator = await db.prompt_templates.find_one({
        'service_code': 'DOC_PACK_ORCHESTRATOR'
    }, {'_id': 0, 'template_id': 1, 'status': 1})
    
    if orchestrator:
        if orchestrator['status'] == 'ACTIVE':
            logger.info(f"   ✅ Already ACTIVE: {orchestrator['template_id']}")
        else:
            # Activate it
            await db.prompt_templates.update_one(
                {'template_id': orchestrator['template_id']},
                {'$set': {'status': 'ACTIVE'}}
            )
            logger.info(f"   ✅ Activated: {orchestrator['template_id']}")
    else:
        logger.warning("   ⚠️  DOC_PACK_ORCHESTRATOR not found - document packs may not work")
        logger.warning("      Document packs will need to use legacy registry")
    
    # Verify no more ambiguities
    logger.info("\n3. Verification - checking for remaining ambiguities...")
    
    ambiguous_services = await db.prompt_templates.aggregate([
        {'$match': {'status': 'ACTIVE'}},
        {'$group': {'_id': '$service_code', 'count': {'$sum': 1}}},
        {'$match': {'count': {'$gt': 1}}},
        {'$sort': {'count': -1}}
    ]).to_list(100)
    
    if ambiguous_services:
        logger.warning(f"   ⚠️  Still have {len(ambiguous_services)} ambiguous services:")
        for svc in ambiguous_services:
            logger.warning(f"      - {svc['_id']}: {svc['count']} prompts")
    else:
        logger.info("   ✅ No ambiguous services remaining")
    
    logger.info("\n" + "=" * 80)
    logger.info("CLEANUP COMPLETE")
    logger.info("=" * 80)
    
    await database.close()


if __name__ == "__main__":
    asyncio.run(fix_prompt_ambiguity())
