# Quick Test Data Cleanup Script

This script aggressively removes test data to give you a clean slate for real testing.

## What it removes:
- All orders without `paid_at` field (CREATED, unpaid test orders)
- All orders older than 48 hours in FAILED state
- All drafts except the last 5
- All workflow executions for removed orders

## Usage:

```bash
cd /app/backend && python3 scripts/cleanup_test_data.py
```

## Manual Database Cleanup (if needed):

```javascript
// Connect to MongoDB
use compliance_vault_pro

// Remove unpaid test orders
db.orders.deleteMany({ paid_at: { $exists: false }, status: "CREATED" })

// Remove old failed orders
db.orders.deleteMany({ 
  status: "FAILED",
  created_at: { $lt: new Date(Date.now() - 48 * 60 * 60 * 1000) }
})

// Keep only last 5 drafts
const draftsToKeep = db.intake_drafts.find().sort({created_at: -1}).limit(5).map(d => d.draft_id)
db.intake_drafts.deleteMany({ draft_id: { $nin: draftsToKeep } })

// Clean up orphaned workflow executions
const orderIds = db.orders.distinct("order_id")
db.workflow_executions.deleteMany({ order_id: { $nin: orderIds } })

// Verify counts
db.orders.countDocuments()
db.intake_drafts.countDocuments()
```

## Restart Services:

```bash
sudo supervisorctl restart backend
```
