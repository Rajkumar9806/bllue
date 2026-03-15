# arrow Backend - EC2 Production Deployment Guide

## Prerequisites
- AWS EC2 instance (Ubuntu 22.04 recommended)
- Domain name (optional but recommended)
- SSL certificate (Let's Encrypt)

## Quick Setup (Copy-paste commands)

### 1. SSH into your EC2 instance
```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
```

### 2. Install Docker and Docker Compose
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose -y

# Re-login for docker group
exit
```

### 3. Clone and Deploy
```bash
# SSH back in
ssh -i your-key.pem ubuntu@your-ec2-ip

# Create app directory
mkdir -p ~/arrow-backend
cd ~/arrow-backend

# Create docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - JWT_SECRET=${JWT_SECRET}
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
EOF

# Upload your backend files (from local machine)
# scp -i your-key.pem -r /path/to/backend/* ubuntu@your-ec2-ip:~/arrow-backend/

# Create .env file on EC2
cat > .env << 'EOF'
DATABASE_URL=postgresql://neondb_owner:npg_mcuR2EY6gVwv@ep-delicate-wildflower-ahtlr24e-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require
JWT_SECRET=arrow_jwt_secret_key_2026_production_v1_secure_random_string
EOF

# Build and start
docker-compose up -d --build

# Check logs
docker-compose logs -f
```

### 4. Setup Nginx Reverse Proxy with SSL
```bash
# Install Nginx
sudo apt install nginx -y

# Install Certbot for SSL
sudo apt install certbot python3-certbot-nginx -y

# Create Nginx config (replace YOUR_DOMAIN)
sudo tee /etc/nginx/sites-available/arrow << 'EOF'
server {
    listen 80;
    server_name YOUR_DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/arrow /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Get SSL certificate (replace YOUR_DOMAIN and YOUR_EMAIL)
sudo certbot --nginx -d YOUR_DOMAIN --email YOUR_EMAIL --agree-tos --non-interactive
```

### 5. Configure EC2 Security Group
Make sure your EC2 security group allows:
- Port 22 (SSH)
- Port 80 (HTTP)
- Port 443 (HTTPS)
- Port 8000 (API - optional, for direct access)

## Alternative: Direct Python Deployment (No Docker)

```bash
# Install Python 3.12
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip -y

# Create app directory
mkdir -p ~/arrow-backend
cd ~/arrow-backend

# Upload files (from local machine)
# scp -i your-key.pem main.py requirements-prod.txt .env ubuntu@your-ec2-ip:~/arrow-backend/

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements-prod.txt

# Run with systemd (recommended for production)
sudo tee /etc/systemd/system/arrow.service << 'EOF'
[Unit]
Description=Arrow API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/arrow-backend
Environment="PATH=/home/ubuntu/arrow-backend/venv/bin"
ExecStart=/home/ubuntu/arrow-backend/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable arrow
sudo systemctl start arrow

# Check status
sudo systemctl status arrow
```

## Update Frontend App

After deploying, update the frontend `.env` file:
```bash
# /home/raj/app/frontend/.env
EXPO_PUBLIC_BACKEND_URL=https://YOUR_DOMAIN
```

Then rebuild the app with EAS:
```bash
cd frontend
eas build --platform android --profile production
eas build --platform ios --profile production
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/api/health` | GET | API health status |
| `/api/auth/send-otp` | POST | Send OTP to phone |
| `/api/auth/verify-otp` | POST | Verify OTP and get token |
| `/api/questionnaire` | POST | Save user questionnaire |
| `/api/date-ideas` | GET | Get date ideas |
| `/api/date-ideas/discover` | GET | Get curated ideas |
| `/api/date-ideas/trending` | GET | Get trending ideas |
| `/api/wishlist` | GET/POST/DELETE | Manage wishlist |
| `/api/calendar` | GET/POST | Manage planned dates |
| `/api/profile` | GET/PATCH | Manage user profile |

## Testing the Deployed API

```bash
# Test health
curl https://YOUR_DOMAIN/api/health

# Test OTP
curl -X POST https://YOUR_DOMAIN/api/auth/send-otp \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+1234567890"}'

# Test date ideas
curl https://YOUR_DOMAIN/api/date-ideas/discover
```
