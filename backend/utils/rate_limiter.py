"""Rate limiting for sensitive operations - Compliance Vault Pro"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        # In-memory rate limiting (for production, use Redis)
        self.attempts = {}
    
    async def check_rate_limit(
        self,
        key: str,
        max_attempts: int,
        window_minutes: int
    ) -> tuple[bool, Optional[str]]:
        """
        Check if rate limit is exceeded.
        
        Returns:
            (allowed: bool, error_message: Optional[str])
        """
        now = datetime.now(timezone.utc)
        
        # Clean old entries
        if key in self.attempts:
            self.attempts[key] = [
                timestamp for timestamp in self.attempts[key]
                if now - timestamp < timedelta(minutes=window_minutes)
            ]
        else:
            self.attempts[key] = []
        
        # Check limit
        if len(self.attempts[key]) >= max_attempts:
            oldest = min(self.attempts[key])
            wait_until = oldest + timedelta(minutes=window_minutes)
            wait_seconds = int((wait_until - now).total_seconds())
            
            return False, f"Rate limit exceeded. Try again in {wait_seconds} seconds"
        
        # Record attempt
        self.attempts[key].append(now)
        return True, None

rate_limiter = RateLimiter()
