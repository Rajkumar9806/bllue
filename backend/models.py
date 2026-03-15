"""
Arrow Backend - Database Models
PostgreSQL with SQLAlchemy Async
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Integer, JSON, Enum
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import uuid
import enum

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


class PersonalityType(str, enum.Enum):
    ADVENTUROUS = "adventurous"
    ROMANTIC = "romantic"
    CHILL = "chill"
    FOODIE = "foodie"
    CREATIVE = "creative"
    SOCIAL = "social"


class BudgetRange(str, enum.Enum):
    FREE = "free"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    LUXURY = "luxury"


class ConnectionType(str, enum.Enum):
    PARTNER = "partner"
    FRIEND = "friend"
    FAMILY = "family"


class OccasionType(str, enum.Enum):
    BIRTHDAY = "birthday"
    ANNIVERSARY = "anniversary"
    VALENTINE = "valentine"
    HOLIDAY = "holiday"
    DATE_NIGHT = "date_night"
    OTHER = "other"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100))
    email = Column(String(255))
    personality_type = Column(String(50))
    interests = Column(JSON, default=list)
    budget_preference = Column(String(20))
    partner_name = Column(String(100))
    partner_dob = Column(DateTime)
    anniversary_date = Column(DateTime)
    
    # Push notifications
    fcm_token = Column(Text)
    notifications_enabled = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime)
    
    # Relationships
    wishlists = relationship("WishlistItem", back_populates="user", cascade="all, delete-orphan")
    occasions = relationship("Occasion", back_populates="user", cascade="all, delete-orphan")
    connections_sent = relationship("Connection", foreign_keys="Connection.user_id", back_populates="user")
    connections_received = relationship("Connection", foreign_keys="Connection.connected_user_id", back_populates="connected_user")


class DateIdea(Base):
    __tablename__ = "date_ideas"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(50), index=True)
    
    # Details
    budget_estimate = Column(String(20))
    duration = Column(String(50))
    location_type = Column(String(20))  # indoor, outdoor, both
    
    # Media
    image_url = Column(Text)
    source = Column(String(50))  # instagram, tiktok, curated
    source_url = Column(Text)
    
    # Engagement
    likes_count = Column(Integer, default=0)
    saves_count = Column(Integer, default=0)
    is_trending = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    
    # Metadata
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    wishlist_items = relationship("WishlistItem", back_populates="date_idea")


class WishlistItem(Base):
    __tablename__ = "wishlist_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date_idea_id = Column(String, ForeignKey("date_ideas.id", ondelete="CASCADE"), nullable=False)
    
    notes = Column(Text)
    is_favorite = Column(Boolean, default=False)
    is_planned = Column(Boolean, default=False)
    planned_date = Column(DateTime)
    
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="wishlists")
    date_idea = relationship("DateIdea", back_populates="wishlist_items")


class Occasion(Base):
    __tablename__ = "occasions"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    person_name = Column(String(100), nullable=False)
    occasion_type = Column(String(50), nullable=False)
    date = Column(DateTime, nullable=False)
    
    reminder_days_before = Column(Integer, default=7)
    notes = Column(Text)
    
    # Notification tracking
    reminder_sent = Column(Boolean, default=False)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="occasions")


class Connection(Base):
    __tablename__ = "connections"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    connected_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    connection_type = Column(String(20), default="partner")
    invite_code = Column(String(10), unique=True, index=True)
    is_accepted = Column(Boolean, default=False)
    
    created_at = Column(DateTime, server_default=func.now())
    accepted_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="connections_sent")
    connected_user = relationship("User", foreign_keys=[connected_user_id], back_populates="connections_received")


class OTPCode(Base):
    __tablename__ = "otp_codes"

    id = Column(String, primary_key=True, default=generate_uuid)
    phone_number = Column(String(20), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class PushNotification(Base):
    __tablename__ = "push_notifications"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    title = Column(String(200), nullable=False)
    body = Column(Text)
    data = Column(JSON)
    
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime)
    scheduled_for = Column(DateTime)
    
    created_at = Column(DateTime, server_default=func.now())
