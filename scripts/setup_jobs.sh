#!/bin/bash
# Cron job setup for Compliance Vault Pro
# Run this script to install scheduled jobs

echo "Setting up Compliance Vault Pro scheduled jobs..."

# Add daily reminder job (9 AM daily)
(crontab -l 2>/dev/null; echo "0 9 * * * cd /app/backend && /usr/local/bin/python services/jobs.py daily >> /var/log/compliance_vault_daily.log 2>&1") | crontab -

echo "✅ Daily reminder job installed (9 AM daily)"

# Add monthly digest job (10 AM on 1st of month)
(crontab -l 2>/dev/null; echo "0 10 1 * * cd /app/backend && /usr/local/bin/python services/jobs.py monthly >> /var/log/compliance_vault_monthly.log 2>&1") | crontab -

echo "✅ Monthly digest job installed (10 AM on 1st of month)"

# Display current crontab
echo ""
echo "Current scheduled jobs:"
crontab -l

echo ""
echo "✅ Job setup complete!"
echo "Logs will be written to:"
echo "  - /var/log/compliance_vault_daily.log"
echo "  - /var/log/compliance_vault_monthly.log"
