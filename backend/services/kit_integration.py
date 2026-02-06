"""
Kit.com Newsletter Integration
One-way sync: Website subscribers → Kit
Handles tagging by source (footer, newsletter_page, insights)
"""
import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

KIT_API_KEY = os.getenv("KIT_API_KEY", "1nG0QycdXFwymTr1oLiuUA")
KIT_API_BASE = "https://api.kit.com/v4"


class KitIntegration:
    """Kit.com API integration for newsletter management."""
    
    def __init__(self):
        self.api_key = KIT_API_KEY
        self.base_url = KIT_API_BASE
    
    async def add_subscriber(
        self, 
        email: str, 
        source: str = "website",
        first_name: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Add subscriber to Kit.
        
        Returns: (success: bool, error_message: Optional[str])
        """
        try:
            async with httpx.AsyncClient() as client:
                # Kit API v4 endpoint for adding subscribers
                url = f"{self.base_url}/subscribers"
                
                payload = {
                    "email": email,
                    "state": "active",
                    "tags": [source]  # Tag by source
                }
                
                if first_name:
                    payload["first_name"] = first_name
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                response = await client.post(url, json=payload, headers=headers, timeout=10.0)
                
                if response.status_code in [200, 201]:
                    logger.info(f"Kit: Subscriber added - {email} (source: {source})")
                    return True, None
                elif response.status_code == 409:
                    # Already exists - update tags
                    logger.info(f"Kit: Subscriber already exists - {email}")
                    return True, None  # Not an error
                else:
                    error_msg = f"Kit API error {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    return False, error_msg
                    
        except httpx.TimeoutException:
            error_msg = "Kit API timeout"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Kit API error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def get_subscriber_by_email(self, email: str) -> Optional[dict]:
        """Get subscriber from Kit by email (for verification)."""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/subscribers"
                headers = {"Authorization": f"Bearer {self.api_key}"}
                params = {"email_address": email}
                
                response = await client.get(url, headers=headers, params=params, timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    subscribers = data.get("subscribers", [])
                    return subscribers[0] if subscribers else None
                
                return None
        except Exception as e:
            logger.error(f"Kit get subscriber error: {e}")
            return None


# Singleton instance
kit_integration = KitIntegration()
