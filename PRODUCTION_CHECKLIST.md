# bllue.app - Production Deployment Checklist

## 🔐 Store Account Setup

### Apple Developer Account ($99/year)
1. Go to https://developer.apple.com/programs/enroll/
2. Sign in with your Apple ID (or create one)
3. Enroll as Individual or Organization
4. Pay $99/year fee
5. Wait for approval (usually 24-48 hours)
6. Once approved, note your **Team ID** from Membership details

### Google Play Console ($25 one-time)
1. Go to https://play.google.com/console/signup
2. Sign in with Google account
3. Pay $25 registration fee
4. Complete developer profile
5. Create your first app listing
6. Generate **Service Account JSON** for automated uploads:
   - Go to Setup > API Access
   - Create new service account
   - Grant "Release Manager" permissions
   - Download JSON key file

---

## 📱 App Configuration

### Required Assets
- [ ] App Icon (1024x1024 PNG, no transparency for iOS)
- [ ] Adaptive Icon for Android (foreground + background)
- [ ] Splash Screen Image
- [ ] App Store Screenshots (iPhone 6.5", 5.5", iPad Pro)
- [ ] Play Store Screenshots (phone + tablet)
- [ ] Feature Graphic (1024x500 for Play Store)

### App Store Listing Content
- [ ] App Name: bllue
- [ ] Subtitle: Date ideas, made easy
- [ ] Description (short + long)
- [ ] Keywords (for App Store)
- [ ] Category: Lifestyle / Social
- [ ] Privacy Policy URL
- [ ] Support URL
- [ ] Marketing URL (optional)

---

## 🔧 Technical Setup

### Environment Variables Needed
```
# Database
MONGO_URL=mongodb+srv://...
DB_NAME=bllue_production

# Authentication
JWT_SECRET_KEY=<generate-secure-key>
OTP_SERVICE_API_KEY=<twilio-or-similar>

# Push Notifications
EXPO_ACCESS_TOKEN=<from-expo.dev>

# Analytics (optional)
MIXPANEL_TOKEN=<optional>
SENTRY_DSN=<optional>
```

### Bundle Identifiers
- iOS: `app.bllue.ios`
- Android: `app.bllue.android`

---

## 🚀 Build Commands

```bash
# Install EAS CLI
npm install -g eas-cli

# Login to Expo
eas login

# Configure project
eas build:configure

# Build for Android (Play Store)
eas build --platform android --profile production

# Build for iOS (App Store)
eas build --platform ios --profile production

# Submit to stores
eas submit --platform android --profile production
eas submit --platform ios --profile production
```

---

## 📋 Pre-Submission Checklist

### iOS App Store
- [ ] App builds without errors
- [ ] All required screenshots uploaded
- [ ] Privacy policy URL added
- [ ] App Review Information filled
- [ ] Sign in credentials for review (if needed)
- [ ] Export Compliance (no encryption = EXEMPT)

### Google Play Store
- [ ] App bundle uploaded
- [ ] Store listing complete
- [ ] Content rating questionnaire done
- [ ] Data safety section filled
- [ ] Target audience declared
- [ ] Privacy policy URL added

---

## 💳 In-App Purchases (if needed)
- [ ] Set up in App Store Connect
- [ ] Set up in Google Play Console
- [ ] Test with sandbox accounts
