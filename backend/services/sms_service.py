"""SMS Service - Twilio Integration for Compliance Alerts and OTP Verification
Feature flagged service for sending SMS notifications.
"""
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from database import database
from datetime import datetime, timezone
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Feature flag for SMS
SMS_ENABLED = os.getenv("SMS_ENABLED", "false").lower() == "true"

class SMSService:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.verify_service_sid = os.getenv("TWILIO_VERIFY_SERVICE_SID")
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.messaging_service_sid = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
        
        self.client = None
        if self.account_sid and self.auth_token:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("Twilio client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")
    
    def is_configured(self) -> bool:
        """Check if SMS service is properly configured."""
        return bool(self.client and self.from_number)
    
    def is_messaging_service_configured(self) -> bool:
        """Check if Twilio Messaging Service SID is set (for OTP / no direct From)."""
        return bool(self.client and self.messaging_service_sid)
    
    def is_enabled(self) -> bool:
        """Check if SMS feature is enabled."""
        return SMS_ENABLED and self.is_configured()
    
    async def send_sms(
        self,
        to_number: str,
        message: str,
        client_id: Optional[str] = None
    ) -> dict:
        """Send an SMS message.
        
        Args:
            to_number: Phone number in E.164 format (+44...)
            message: SMS message body (max 160 chars recommended)
            client_id: Optional client ID for logging
        
        Returns:
            dict with status and message_sid
        """
        if not self.is_enabled():
            logger.warning("SMS is not enabled or configured")
            return {"success": False, "error": "SMS not enabled"}
        
        # Validate phone number format
        if not to_number.startswith("+"):
            to_number = f"+{to_number}"
        
        try:
            message_obj = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            
            # Log the SMS
            db = database.get_db()
            await db.sms_logs.insert_one({
                "message_sid": message_obj.sid,
                "to_number": to_number,
                "message_preview": message[:50] + "..." if len(message) > 50 else message,
                "status": message_obj.status,
                "client_id": client_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            logger.info(f"SMS sent to {to_number[:7]}***: {message_obj.sid}")
            
            return {
                "success": True,
                "message_sid": message_obj.sid,
                "status": message_obj.status
            }
        
        except TwilioRestException as e:
            logger.error(f"Twilio error sending SMS: {e.code} - {e.msg}")
            return {"success": False, "error": str(e.msg), "code": e.code}
        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_sms_via_messaging_service(self, to_number: str, body: str) -> dict:
        """Send SMS using Twilio Messaging Service SID only (no direct From number).
        Used for OTP and other flows that must not expose a single sender number.
        """
        if not self.client or not self.messaging_service_sid:
            logger.warning("Twilio Messaging Service not configured")
            return {"success": False, "error": "Messaging service not configured"}
        if not to_number.startswith("+"):
            to_number = f"+{to_number}"
        try:
            message_obj = self.client.messages.create(
                body=body,
                messaging_service_sid=self.messaging_service_sid,
                to=to_number,
            )
            logger.info(f"SMS via Messaging Service to {to_number[:7]}***: {message_obj.sid}")
            return {"success": True, "message_sid": message_obj.sid, "status": message_obj.status}
        except TwilioRestException as e:
            logger.error(f"Twilio error (Messaging Service): {e.code} - {e.msg}")
            return {"success": False, "error": str(e.msg), "code": e.code}
        except Exception as e:
            logger.error(f"Error sending SMS via Messaging Service: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_otp(self, phone_number: str) -> dict:
        """Send OTP for phone verification using Twilio Verify.
        
        Args:
            phone_number: Phone number in E.164 format
        
        Returns:
            dict with status
        """
        if not self.client or not self.verify_service_sid:
            logger.warning("Twilio Verify not configured")
            return {"success": False, "error": "Verify service not configured"}
        
        # Validate phone number format
        if not phone_number.startswith("+"):
            phone_number = f"+{phone_number}"
        
        try:
            verification = self.client.verify.v2.services(
                self.verify_service_sid
            ).verifications.create(
                to=phone_number,
                channel="sms"
            )
            
            logger.info(f"OTP sent to {phone_number[:7]}***: {verification.status}")
            
            return {
                "success": True,
                "status": verification.status
            }
        
        except TwilioRestException as e:
            logger.error(f"Twilio Verify error: {e.code} - {e.msg}")
            return {"success": False, "error": str(e.msg), "code": e.code}
        except Exception as e:
            logger.error(f"Error sending OTP: {e}")
            return {"success": False, "error": str(e)}
    
    async def verify_otp(self, phone_number: str, code: str) -> dict:
        """Verify OTP code.
        
        Args:
            phone_number: Phone number in E.164 format
            code: 6-digit OTP code
        
        Returns:
            dict with valid status
        """
        if not self.client or not self.verify_service_sid:
            logger.warning("Twilio Verify not configured")
            return {"success": False, "error": "Verify service not configured"}
        
        # Validate phone number format
        if not phone_number.startswith("+"):
            phone_number = f"+{phone_number}"
        
        try:
            verification_check = self.client.verify.v2.services(
                self.verify_service_sid
            ).verification_checks.create(
                to=phone_number,
                code=code
            )
            
            is_valid = verification_check.status == "approved"
            
            logger.info(f"OTP verification for {phone_number[:7]}***: {verification_check.status}")
            
            return {
                "success": True,
                "valid": is_valid,
                "status": verification_check.status
            }
        
        except TwilioRestException as e:
            logger.error(f"Twilio Verify check error: {e.code} - {e.msg}")
            return {"success": False, "valid": False, "error": str(e.msg), "code": e.code}
        except Exception as e:
            logger.error(f"Error verifying OTP: {e}")
            return {"success": False, "valid": False, "error": str(e)}
    
    async def send_compliance_alert_sms(
        self,
        phone_number: str,
        client_name: str,
        property_address: str,
        new_status: str,
        client_id: str
    ) -> dict:
        """Send compliance status change alert via SMS.
        
        Args:
            phone_number: Phone number in E.164 format
            client_name: Client's name
            property_address: Property address
            new_status: New compliance status (AMBER/RED)
            client_id: Client ID for logging
        
        Returns:
            dict with send result
        """
        emoji = "🔴" if new_status == "RED" else "🟡"
        
        message = (
            f"{emoji} COMPLIANCE ALERT\n"
            f"Hi {client_name.split()[0]},\n"
            f"{property_address} is now {new_status}.\n"
            f"Action required. View details in your portal."
        )
        
        return await self.send_sms(phone_number, message, client_id)

# Singleton instance
sms_service = SMSService()
