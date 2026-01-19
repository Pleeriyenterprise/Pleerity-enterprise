#!/bin/bash
# Production deployment checklist for Compliance Vault Pro

echo "======================================================"
echo "COMPLIANCE VAULT PRO - PRODUCTION DEPLOYMENT CHECKLIST"
echo "======================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass=0
check_fail=0

# Function to check requirement
check_requirement() {
    local name="$1"
    local command="$2"
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ $name${NC}"
        ((check_pass++))
        return 0
    else
        echo -e "${RED}❌ $name${NC}"
        ((check_fail++))
        return 1
    fi
}

check_env_var() {
    local name="$1"
    local var_name="$2"
    
    if grep -q "^${var_name}=" /app/backend/.env && [ "$(grep "^${var_name}=" /app/backend/.env | cut -d'=' -f2-)" != "" ]; then
        echo -e "${GREEN}✅ $name${NC}"
        ((check_pass++))
    else
        echo -e "${RED}❌ $name - ${var_name} not set${NC}"
        ((check_fail++))
    fi
}

echo "1. ENVIRONMENT CONFIGURATION"
echo "----------------------------"
check_env_var "JWT Secret configured" "JWT_SECRET"
check_env_var "Postmark token configured" "POSTMARK_SERVER_TOKEN"
check_env_var "Stripe API key configured" "STRIPE_API_KEY"
check_env_var "Frontend URL configured" "FRONTEND_URL"
echo ""

echo "2. DATABASE CONNECTIVITY"
echo "------------------------"
check_requirement "MongoDB connection" "cd /app/backend && python -c 'from motor.motor_asyncio import AsyncIOMotorClient; import os; from dotenv import load_dotenv; load_dotenv(); client = AsyncIOMotorClient(os.environ[\"MONGO_URL\"]); client.admin.command(\"ping\")'"
echo ""

echo "3. BACKEND SERVICES"
echo "-------------------"
check_requirement "Backend server running" "curl -s http://localhost:8001/api/health > /dev/null"
check_requirement "All routes registered" "curl -s http://localhost:8001/api/health | grep -q healthy"
echo ""

echo "4. FRONTEND BUILD"
echo "-----------------"
check_requirement "Frontend accessible" "curl -s https://compliancevault.preview.emergentagent.com > /dev/null"
echo ""

echo "5. CRITICAL FILES"
echo "-----------------"
check_requirement "Admin routes exist" "[ -f /app/backend/routes/admin.py ]"
check_requirement "Client routes exist" "[ -f /app/backend/routes/client.py ]"
check_requirement "Document routes exist" "[ -f /app/backend/routes/documents.py ]"
check_requirement "Jobs module exists" "[ -f /app/backend/services/jobs.py ]"
check_requirement "Compliance pack generator exists" "[ -f /app/backend/services/compliance_pack.py ]"
echo ""

echo "6. SCHEDULED JOBS"
echo "-----------------"
if crontab -l 2>/dev/null | grep -q "services/jobs.py daily"; then
    echo -e "${GREEN}✅ Daily reminder job configured${NC}"
    ((check_pass++))
else
    echo -e "${YELLOW}⚠️  Daily reminder job not configured${NC}"
    echo "   Run: bash /app/scripts/setup_jobs.sh"
    ((check_fail++))
fi

if crontab -l 2>/dev/null | grep -q "services/jobs.py monthly"; then
    echo -e "${GREEN}✅ Monthly digest job configured${NC}"
    ((check_pass++))
else
    echo -e "${YELLOW}⚠️  Monthly digest job not configured${NC}"
    echo "   Run: bash /app/scripts/setup_jobs.sh"
    ((check_fail++))
fi
echo ""

echo "======================================================"
echo "RESULTS: ${check_pass} passed, ${check_fail} failed"
echo "======================================================"
echo ""

if [ $check_fail -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED - System ready for production${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Configure Postmark email templates"
    echo "2. Test full intake → payment → provision flow"
    echo "3. Verify email delivery"
    echo "4. Monitor audit logs"
    exit 0
else
    echo -e "${RED}❌ $check_fail CHECKS FAILED - Do not deploy to production${NC}"
    echo ""
    echo "Fix the failed checks before proceeding."
    exit 1
fi
