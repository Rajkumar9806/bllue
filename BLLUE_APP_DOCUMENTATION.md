# Arrow - AI-Powered Date Night Planning App

## 📱 App Overview

**Arrow** is a mobile application that helps couples discover, plan, and execute memorable date nights using AI-powered personalization. The app learns user preferences through a personality quiz and delivers tailored date ideas with step-by-step execution guides.

**Target Market:** Couples aged 22-40 seeking meaningful experiences together  
**Problem Solved:** Decision fatigue around planning dates + lack of personalized recommendations  
**Unique Value:** AI that understands relationship dynamics and suggests dates that strengthen connections

---

## 🏗️ Technical Architecture

### Frontend
| Technology | Purpose |
|------------|---------|
| **React Native** | Cross-platform mobile development |
| **Expo SDK 54** | Development framework & build tooling |
| **Expo Router** | File-based navigation |
| **TypeScript** | Type-safe development |
| **AsyncStorage** | Local data persistence |
| **Axios** | HTTP client for API calls |

### Backend
| Technology | Purpose |
|------------|---------|
| **FastAPI (Python)** | High-performance async API framework |
| **PostgreSQL** | Primary database (Neon for dev, EC2 for prod) |
| **asyncpg** | Async PostgreSQL driver |
| **JWT (python-jose)** | Stateless authentication |
| **Pydantic** | Data validation & serialization |
| **uvicorn** | ASGI server |

### Infrastructure
| Service | Purpose |
|---------|---------|
| **AWS EC2** | Production backend hosting |
| **Neon PostgreSQL** | Managed development database |
| **EAS Build** | iOS/Android app builds |
| **Apple App Store** | iOS distribution |
| **Google Play Store** | Android distribution |

---

## 🤖 AI & External API Integrations

### 1. Google Gemini AI (Gemini 2.0 Flash)
- **Purpose:** Generate personalized date ideas based on user personality profiles
- **Features:**
  - Personality-matched recommendations
  - Step-by-step execution guides
  - Budget estimates and duration
  - Gift suggestions and booking options
  - Mood/ambiance recommendations

### 2. Eventbrite API
- **Purpose:** Fetch real local events for date nights
- **Features:**
  - Location-based event discovery
  - Category filtering (food, arts, wellness, etc.)
  - Direct booking links
  - Real-time availability

### 3. Twilio SMS API
- **Purpose:** OTP-based phone authentication
- **Features:**
  - Secure 6-digit verification codes
  - 5-minute expiry
  - Fallback to test mode for development

### 4. Curated Deal Integration (Groupon-style)
- **Purpose:** Surface discounted date experiences
- **Features:**
  - Spa packages, cooking classes, adventures
  - Price comparisons (original vs deal)
  - Expiration tracking

---

## ✨ Core Features

### 1. 📝 Personality Onboarding
- Interactive quiz to understand couple dynamics
- Captures: interests, budget preferences, indoor/outdoor preference
- Stores partner information and special dates
- Powers all AI recommendations

### 2. 🔍 Discover Tab
- AI-generated personalized date ideas
- Curated database of 30+ date concepts
- Real-time Eventbrite events
- Groupon-style deals
- Swipe/browse interface with detailed cards

### 3. 💕 Date Idea Details
- Step-by-step execution guide
- "Why it's perfect for you" AI explanation
- Budget estimate and duration
- What to bring checklist
- Pro tips
- Booking CTAs (restaurants, activities, gifts)
- Personality match score

### 4. ❤️ Wishlist
- Save favorite date ideas
- Quick access for planning
- Sync across devices

### 5. 📅 Calendar
- Plan dates with scheduled reminders
- Anniversary/birthday tracking
- Partner's special dates
- Push notification reminders

### 6. 👤 Profile
- Edit personal information
- Partner connection (invite via code)
- Retake personality quiz
- Settings & preferences
- FAQ, Terms, Privacy links

### 7. 🔐 Authentication
- Phone number + OTP verification
- JWT token-based sessions (30-day expiry)
- Secure, passwordless login

---

## 📊 Database Schema

```
users
├── id (UUID)
├── phone_number (unique)
├── name
├── email
├── personality_type
├── interests[]
├── budget_range
├── indoor_outdoor_preference
├── partner_name
├── partner_dob
├── anniversary_date
└── timestamps

date_ideas
├── id (UUID)
├── title
├── description
├── category
├── budget (low/medium/high)
├── duration
├── location_type
├── image_url
├── tags[]
├── is_trending
└── created_at

wishlist
├── id (UUID)
├── user_id → users
├── date_idea_id → date_ideas
├── notes
└── created_at

planned_dates
├── id (UUID)
├── user_id → users
├── date_idea_id → date_ideas
├── title
├── scheduled_date
├── notes
├── status
└── created_at

otp_codes
├── id (UUID)
├── phone_number
├── otp_code
├── expires_at
├── used
└── created_at
```

---

## 🔌 API Endpoints

### Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/send-otp` | POST | Send OTP to phone |
| `/api/auth/verify-otp` | POST | Verify OTP, get JWT |

### Date Ideas
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/date-ideas` | GET | No | Browse all ideas with filters |
| `/api/date-ideas/discover` | GET | Yes | AI-personalized feed |
| `/api/date-ideas/ai-personalized` | GET | Yes | Full AI generation |
| `/api/date-ideas/trending` | GET | No | Trending ideas |
| `/api/date-ideas/all` | GET | Optional | Combined sources |

### External Sources
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/events/eventbrite` | GET | Real Eventbrite events |
| `/api/deals/groupon` | GET | Deal-style offers |
| `/api/date-ideas/external` | GET | Combined external sources |

### User Features
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/wishlist` | GET/POST/DELETE | Yes | Manage saved ideas |
| `/api/calendar` | GET/POST | Yes | Manage planned dates |
| `/api/profile` | GET/PATCH | Yes | User profile |
| `/api/personality/submit` | POST | Yes | Save quiz results |

### Legal Pages
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/terms` | GET | Terms of Service (HTML) |
| `/privacy` | GET | Privacy Policy (HTML) |
| `/faq` | GET | FAQs (HTML) |

---

## 🚀 Deployment Status

### Production Environment
- **Backend URL:** https://arrow.app
- **Server:** AWS EC2 (t2.micro, us-east-1)
- **Database:** PostgreSQL on EC2
- **SSL:** Let's Encrypt via Nginx

### App Distribution
- **iOS:** TestFlight (Apple Developer Program active)
- **Android:** Internal testing APK available
- **Bundle ID:** com.arrow.app

---

## 🔧 Development Setup

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npx expo start --tunnel
```

---

## 📈 Key Metrics to Track

1. **User Acquisition:** Sign-ups, OTP verifications
2. **Engagement:** Ideas viewed, wishlist saves, dates planned
3. **Retention:** Weekly active users, dates completed
4. **AI Quality:** Personality match scores, user feedback
5. **Conversion:** Booking CTA clicks, external link opens

---

## 🛣️ Product Roadmap

### Phase 1 (Current) ✅
- Core date discovery and planning
- AI personalization
- Phone authentication
- Wishlist and calendar

### Phase 2 (Next)
- Partner pairing (share wishlist)
- Push notification reminders
- Date completion tracking
- Reviews and ratings

### Phase 3 (Future)
- Premium subscription (unlimited AI ideas)
- Direct booking integration
- Social features (share date ideas)
- Relationship insights dashboard

---

## 👥 Team

**Developer:** Raj (Full-stack development)  
**Platform:** React Native + FastAPI  
**Timeline:** Built in January 2026

---

## 📞 Contact & Links

- **App URL:** https://arrow.app
- **API Docs:** https://arrow.app/docs
- **Support:** support@arrow.app
- **Privacy:** privacy@arrow.app

---

*Last Updated: January 31, 2026*
