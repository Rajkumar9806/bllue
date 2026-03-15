"""
Arrow Backend - Firebase Cloud Messaging Service
Push Notifications
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import User, PushNotification, Occasion

logger = logging.getLogger(__name__)

# Initialize Firebase
firebase_app = None

def init_firebase():
    """Initialize Firebase Admin SDK"""
    global firebase_app
    
    if firebase_app is not None:
        return
    
    try:
        # Try to load from file
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            # Try to load from environment variable (JSON string)
            cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
            if cred_json:
                cred_dict = json.loads(cred_json)
                cred = credentials.Certificate(cred_dict)
            else:
                logger.warning("Firebase credentials not found. Push notifications disabled.")
                return
        
        firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")


async def send_push_notification(
    fcm_token: str,
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
    image_url: Optional[str] = None
) -> bool:
    """Send push notification to a single device"""
    if firebase_app is None:
        logger.warning("Firebase not initialized. Skipping push notification.")
        return False
    
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
                image=image_url
            ),
            data=data or {},
            token=fcm_token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    icon="notification_icon",
                    color="#E04060",
                    sound="default",
                    channel_id="arrow_notifications"
                )
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        badge=1
                    )
                )
            )
        )
        
        response = messaging.send(message)
        logger.info(f"Successfully sent notification: {response}")
        return True
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False


async def send_bulk_notifications(
    tokens: List[str],
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None
) -> int:
    """Send push notification to multiple devices"""
    if firebase_app is None or not tokens:
        return 0
    
    try:
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            data=data or {},
            tokens=tokens
        )
        
        response = messaging.send_each_for_multicast(message)
        logger.info(f"Sent {response.success_count} notifications successfully")
        return response.success_count
    except Exception as e:
        logger.error(f"Failed to send bulk notifications: {e}")
        return 0


async def send_occasion_reminder(
    db: AsyncSession,
    user: User,
    occasion: Occasion,
    days_until: int
) -> bool:
    """Send reminder notification for upcoming occasion"""
    if not user.fcm_token or not user.notifications_enabled:
        return False
    
    if days_until == 0:
        title = f"🎉 Today is {occasion.person_name}'s {occasion.occasion_type}!"
        body = "Don't forget to make it special!"
    elif days_until == 1:
        title = f"📅 Tomorrow: {occasion.person_name}'s {occasion.occasion_type}"
        body = "Last chance to prepare something amazing!"
    else:
        title = f"💝 {days_until} days until {occasion.person_name}'s {occasion.occasion_type}"
        body = "Time to start planning!"
    
    success = await send_push_notification(
        fcm_token=user.fcm_token,
        title=title,
        body=body,
        data={
            "type": "occasion_reminder",
            "occasion_id": occasion.id,
            "days_until": str(days_until)
        }
    )
    
    # Log notification
    notification = PushNotification(
        user_id=user.id,
        title=title,
        body=body,
        data={"occasion_id": occasion.id},
        is_sent=success,
        sent_at=datetime.utcnow() if success else None
    )
    db.add(notification)
    await db.commit()
    
    return success


async def send_partner_wishlist_notification(
    db: AsyncSession,
    user: User,
    partner_name: str,
    idea_title: str
) -> bool:
    """Notify user when partner adds something to wishlist"""
    if not user.fcm_token or not user.notifications_enabled:
        return False
    
    return await send_push_notification(
        fcm_token=user.fcm_token,
        title=f"💕 {partner_name} added a new date idea!",
        body=f'"{idea_title}" - maybe plan a surprise?',
        data={"type": "partner_wishlist"}
    )


async def send_new_trending_notification(
    db: AsyncSession,
    user: User,
    idea_title: str
) -> bool:
    """Notify user about new trending date idea"""
    if not user.fcm_token or not user.notifications_enabled:
        return False
    
    return await send_push_notification(
        fcm_token=user.fcm_token,
        title="🔥 New trending date idea!",
        body=idea_title,
        data={"type": "trending_idea"}
    )
