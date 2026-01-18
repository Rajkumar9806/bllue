# 🚀 bllue App - Production Deployment Guide

## Overview
This guide will help you deploy **bllue** to both the Apple App Store and Google Play Store.

---

## 📋 Pre-Deployment Checklist

### ✅ Already Completed:
- [x] App configuration (app.json) with bundle IDs
- [x] EAS build configuration (eas.json)
- [x] PostgreSQL backend with all API endpoints
- [x] 40+ curated date ideas in seed data
- [x] Push notification service (expo-notifications)
- [x] App icons generated (1024x1024)
- [x] Privacy Policy for app stores
- [x] API service for frontend-backend communication

### 🔲 Pending (Need Your Input):
- [ ] Neon PostgreSQL connection URL
- [ ] Firebase project setup (for push notifications)
- [ ] Apple Developer Account ($99/year)
- [ ] Google Play Developer Account ($25 one-time)
- [ ] Twilio account for SMS OTP (optional for now)

---

## 🔥 Step 1: Firebase Setup (Push Notifications)

### 1.1 Create Firebase Project
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Create a project"
3. Name it: **bllue**
4. Disable Google Analytics (optional) → Create Project

### 1.2 Add Android App
1. Click "Add app" → Select Android
2. Package name: `com.bllue.app`
3. App nickname: **bllue**
4. Download `google-services.json`
5. **Place it in:** `/frontend/google-services.json`

### 1.3 Add iOS App
1. Click "Add app" → Select iOS
2. Bundle ID: `com.bllue.app`
3. App nickname: **bllue**
4. Download `GoogleService-Info.plist`
5. **Save it** - you'll need it for the iOS build

### 1.4 Enable Cloud Messaging
1. Go to Project Settings → Cloud Messaging
2. Generate a Server Key (or use Firebase Admin SDK)
3. Copy the Server Key for your backend `.env`

---

## 🗄️ Step 2: Database Setup (Neon PostgreSQL)

### 2.1 Get Your Connection URL
1. Go to [Neon Console](https://console.neon.tech/)
2. Select your project
3. Copy the connection string (looks like):
   ```
   postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

### 2.2 Create Backend .env File
Create `/backend/.env`:
```env
DATABASE_URL=your_neon_connection_string_here
JWT_SECRET=generate_a_secure_random_string_here
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone
FIREBASE_CREDENTIALS=path_to_firebase_admin_sdk.json
```

### 2.3 Initialize Database
```bash
cd backend
pip install -r requirements-production.txt
python -c "from database import init_db; import asyncio; asyncio.run(init_db())"
python seed_data.py
```

---

## 🍎 Step 3: Apple Developer Account

### 3.1 Create Account
1. Go to [Apple Developer Program](https://developer.apple.com/programs/)
2. Click "Enroll"
3. Sign in with your Apple ID (or create one)
4. Choose: Individual ($99/year)
5. Complete identity verification
6. **Wait:** Approval takes 24-48 hours

### 3.2 After Approval
1. Go to [App Store Connect](https://appstoreconnect.apple.com/)
2. Create a new app:
   - Platform: iOS
   - Name: **bllue**
   - Primary Language: English
   - Bundle ID: `com.bllue.app`
   - SKU: `bllue-ios-v1`

---

## 🤖 Step 4: Google Play Developer Account

### 4.1 Create Account
1. Go to [Google Play Console](https://play.google.com/console/)
2. Sign in with your Google account
3. Pay $25 registration fee (one-time)
4. Complete the developer profile

### 4.2 Create App
1. Click "Create app"
2. App name: **bllue**
3. Default language: English
4. App or game: App
5. Free or paid: Free
6. Accept declarations

---

## 🔐 Step 5: EAS Login & Project Setup

### 5.1 Login to Expo
```bash
cd frontend
eas login
# Enter your Expo account credentials
# Create account at https://expo.dev if needed
```

### 5.2 Configure Project
```bash
eas build:configure
# This will link your project to your Expo account
```

---

## 📱 Step 6: Build the Apps

### 6.1 Build for Android (APK for testing)
```bash
cd frontend
eas build --platform android --profile preview
```

### 6.2 Build for Android (AAB for Play Store)
```bash
eas build --platform android --profile production
```

### 6.3 Build for iOS
```bash
eas build --platform ios --profile production
```

**Note:** iOS builds require:
- Apple Developer account credentials
- EAS will prompt for them during build
- First build takes longer (creating certificates)

---

## 📤 Step 7: Submit to Stores

### 7.1 Submit to Google Play Store
```bash
eas submit --platform android
# Select the production build
# Enter your Play Console service account key
```

Or manually:
1. Download the .aab file from EAS
2. Go to Play Console → Your App → Production
3. Upload the .aab file
4. Fill in store listing details

### 7.2 Submit to Apple App Store
```bash
eas submit --platform ios
# Enter your Apple ID credentials
# Select the build to submit
```

Or use Transporter app on Mac:
1. Download the .ipa from EAS
2. Open Transporter app
3. Upload the .ipa
4. Complete submission in App Store Connect

---

## 📝 Store Listing Content

### App Store / Play Store Description:
```
bllue - Your Date Night Companion 💕

Never run out of date ideas again! bllue helps couples discover unique, personalized date experiences based on your interests, budget, and available time.

Features:
• 🎯 Personalized Recommendations - Date ideas tailored just for you
• 💝 Wishlist - Save ideas you both love
• 📅 Calendar - Plan and remember special occasions
• 🔔 Reminders - Never forget an anniversary again
• 👫 Partner Sync - Share wishlists with your significant other

Categories include:
- Romantic Dinners
- Outdoor Adventures
- Creative Activities
- At-Home Dates
- Budget-Friendly Options

Download bllue and make every date special!
```

### Keywords:
`date night, couples, relationship, date ideas, romantic, activities, couples app, date planner`

### Screenshots Needed:
1. Welcome/Onboarding screen
2. Discover/Browse ideas screen
3. Idea detail view
4. Wishlist screen
5. Calendar screen

---

## 🌐 Backend Deployment (AWS)

### Option 1: AWS App Runner (Recommended for simplicity)
```bash
# Install AWS CLI and configure with your credentials
aws configure

# Create App Runner service (provide details when ready)
```

### Option 2: AWS EC2
1. Launch EC2 instance (t2.micro for free tier)
2. Install Python 3.11+
3. Clone your backend code
4. Set up environment variables
5. Run with uvicorn + supervisor

### Option 3: AWS Lambda + API Gateway
- Use Mangum adapter for FastAPI
- Serverless, scales automatically
- Pay per request

---

## 🔧 Environment Variables Summary

### Frontend (.env)
```env
EXPO_PUBLIC_BACKEND_URL=https://your-backend-url.com
```

### Backend (.env)
```env
DATABASE_URL=postgresql://...
JWT_SECRET=your-super-secret-key
TWILIO_ACCOUNT_SID=ACxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxx
TWILIO_PHONE_NUMBER=+1234567890
FIREBASE_CREDENTIALS=./firebase-admin-sdk.json
```

---

## 📞 Support Contacts

- **Expo Support:** https://expo.dev/support
- **Apple Developer:** https://developer.apple.com/support/
- **Google Play:** https://support.google.com/googleplay/android-developer/

---

## 🎉 Ready to Go!

Once you provide:
1. ✅ Neon DB connection URL
2. ✅ Firebase google-services.json
3. ✅ Apple Developer enrollment confirmation
4. ✅ Google Play Console access

We can run the builds and submit to stores!
