"""
bllue Backend - Pydantic Schemas
Request/Response Models
"""

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime


# ==================== AUTH ====================

class OTPRequest(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=15)


class OTPVerify(BaseModel):
    phone_number: str
    otp: str = Field(..., min_length=4, max_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


# ==================== USER ====================

class UserCreate(BaseModel):
    phone_number: str
    name: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    personality_type: Optional[str] = None
    interests: Optional[List[str]] = None
    budget_preference: Optional[str] = None
    partner_name: Optional[str] = None
    partner_dob: Optional[datetime] = None
    anniversary_date: Optional[datetime] = None
    fcm_token: Optional[str] = None
    notifications_enabled: Optional[bool] = None


class UserResponse(BaseModel):
    id: str
    phone_number: str
    name: Optional[str] = None
    email: Optional[str] = None
    personality_type: Optional[str] = None
    interests: List[str] = []
    budget_preference: Optional[str] = None
    partner_name: Optional[str] = None
    partner_dob: Optional[datetime] = None
    anniversary_date: Optional[datetime] = None
    notifications_enabled: bool = True
    created_at: datetime

    class Config:
        from_attributes = True


class QuestionnaireSubmit(BaseModel):
    name: str
    personality_type: str
    interests: List[str]
    budget_preference: str
    partner_name: Optional[str] = None
    partner_dob: Optional[datetime] = None
    anniversary_date: Optional[datetime] = None


# ==================== DATE IDEAS ====================

class DateIdeaCreate(BaseModel):
    title: str
    description: str
    category: str
    budget_estimate: str = "medium"
    duration: str = "2-3 hours"
    location_type: str = "both"
    image_url: Optional[str] = None
    source: str = "curated"
    source_url: Optional[str] = None
    tags: List[str] = []


class DateIdeaResponse(BaseModel):
    id: str
    title: str
    description: str
    category: str
    budget_estimate: str
    duration: str
    location_type: str
    image_url: Optional[str] = None
    source: str
    source_url: Optional[str] = None
    likes_count: int = 0
    saves_count: int = 0
    is_trending: bool = False
    is_featured: bool = False
    tags: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True


class DateIdeasListResponse(BaseModel):
    ideas: List[DateIdeaResponse]
    total: int
    page: int
    per_page: int


# ==================== WISHLIST ====================

class WishlistItemCreate(BaseModel):
    date_idea_id: str
    notes: Optional[str] = None


class WishlistItemResponse(BaseModel):
    id: str
    user_id: str
    date_idea_id: str
    date_idea: DateIdeaResponse
    notes: Optional[str] = None
    is_favorite: bool = False
    is_planned: bool = False
    planned_date: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WishlistResponse(BaseModel):
    items: List[WishlistItemResponse]
    total: int


# ==================== OCCASIONS ====================

class OccasionCreate(BaseModel):
    person_name: str
    occasion_type: str
    date: datetime
    reminder_days_before: int = 7
    notes: Optional[str] = None


class OccasionUpdate(BaseModel):
    person_name: Optional[str] = None
    occasion_type: Optional[str] = None
    date: Optional[datetime] = None
    reminder_days_before: Optional[int] = None
    notes: Optional[str] = None


class OccasionResponse(BaseModel):
    id: str
    user_id: str
    person_name: str
    occasion_type: str
    date: datetime
    reminder_days_before: int
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OccasionsListResponse(BaseModel):
    occasions: List[OccasionResponse]
    total: int


# ==================== CONNECTIONS ====================

class ConnectionCreate(BaseModel):
    connection_type: str = "partner"


class ConnectionAccept(BaseModel):
    invite_code: str


class ConnectionResponse(BaseModel):
    id: str
    user_id: str
    connected_user_id: str
    connection_type: str
    is_accepted: bool
    created_at: datetime
    accepted_at: Optional[datetime] = None
    connected_user: Optional[UserResponse] = None

    class Config:
        from_attributes = True


class InviteCodeResponse(BaseModel):
    invite_code: str
    expires_in: int = 86400  # 24 hours


# ==================== NOTIFICATIONS ====================

class RegisterFCMToken(BaseModel):
    fcm_token: str


class NotificationResponse(BaseModel):
    id: str
    title: str
    body: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    is_sent: bool
    sent_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== GIFT SUGGESTIONS ====================

class GiftSuggestionRequest(BaseModel):
    occasion_type: str
    person_name: str
    budget: str = "medium"
    interests: List[str] = []


class GiftSuggestionResponse(BaseModel):
    suggestions: List[str]
    occasion_type: str
    budget: str


# Forward references
TokenResponse.model_rebuild()
