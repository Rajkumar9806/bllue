"""
Arrow Backend - SMS OTP Service
Using Twilio for production
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Check if Twilio is available
TWILIO_ENABLED = False
twilio_client = None

try:
    from twilio.rest import Client
    
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
    
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        TWILIO_ENABLED = True
        logger.info("Twilio SMS service initialized")
    else:
        logger.warning("Twilio credentials not configured. SMS disabled.")
except ImportError:
    logger.warning("Twilio package not installed. SMS disabled.")


async def send_otp_sms(phone_number: str, otp_code: str) -> bool:
    """
    Send OTP via SMS using Twilio
    
    Returns True if sent successfully, False otherwise
    """
    if not TWILIO_ENABLED:
        # In development, log OTP instead of sending
        logger.info(f"[DEV MODE] OTP for {phone_number}: {otp_code}")
        return True
    
    try:
        message = twilio_client.messages.create(
            body=f"Your Arrow verification code is: {otp_code}\n\nThis code expires in 10 minutes.",
            from_=TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        
        logger.info(f"OTP sent to {phone_number}, SID: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP to {phone_number}: {e}")
        return False


async def send_welcome_sms(phone_number: str, name: str) -> bool:
    """Send welcome SMS after successful registration"""
    if not TWILIO_ENABLED:
        logger.info(f"[DEV MODE] Welcome SMS for {phone_number}")
        return True
    
    try:
        message = twilio_client.messages.create(
            body=f"Welcome to Arrow, {name}! 💕\n\nDiscover amazing date ideas and never forget a special moment.\n\n- The Arrow team",
            from_=TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        
        logger.info(f"Welcome SMS sent to {phone_number}, SID: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send welcome SMS to {phone_number}: {e}")
        return False


async def send_reminder_sms(
    phone_number: str,
    person_name: str,
    occasion_type: str,
    days_until: int
) -> bool:
    """Send occasion reminder via SMS as backup to push"""
    if not TWILIO_ENABLED:
        logger.info(f"[DEV MODE] Reminder SMS for {phone_number}")
        return True
    
    if days_until == 0:
        message_body = f"🎉 Reminder: Today is {person_name}'s {occasion_type}! Make it special!"
    elif days_until == 1:
        message_body = f"📅 Reminder: Tomorrow is {person_name}'s {occasion_type}!"
    else:
        message_body = f"💕 Reminder: {person_name}'s {occasion_type} is in {days_until} days!"
    
    try:
        message = twilio_client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        
        logger.info(f"Reminder SMS sent to {phone_number}, SID: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send reminder SMS to {phone_number}: {e}")
        return False
