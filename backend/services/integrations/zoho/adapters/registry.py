from services.integrations.zoho.adapters.analytics import ZohoAnalyticsAdapter
from services.integrations.zoho.adapters.books import ZohoBooksAdapter
from services.integrations.zoho.adapters.campaigns import ZohoCampaignsAdapter
from services.integrations.zoho.adapters.crm import ZohoCrmAdapter
from services.integrations.zoho.adapters.sign import ZohoSignAdapter
from services.integrations.zoho.adapters.workdrive import ZohoWorkdriveAdapter

ADAPTERS = {
    "analytics": ZohoAnalyticsAdapter(),
    "crm": ZohoCrmAdapter(),
    "campaigns": ZohoCampaignsAdapter(),
    "sign": ZohoSignAdapter(),
    "books": ZohoBooksAdapter(),
    "workdrive": ZohoWorkdriveAdapter(),
}


def get_adapter(integration: str):
    return ADAPTERS.get(integration)
