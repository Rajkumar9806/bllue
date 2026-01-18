#!/bin/bash
# bllue Backend Deployment Script for EC2

set -e

echo "🚀 bllue Backend Deployment Script"
echo "=================================="

# Configuration
EC2_USER="${EC2_USER:-ubuntu}"
EC2_HOST="${EC2_HOST:-your-ec2-ip}"
KEY_FILE="${KEY_FILE:-~/.ssh/your-key.pem}"
REMOTE_DIR="/home/$EC2_USER/bllue-backend"

# Check if key file exists
if [ ! -f "$KEY_FILE" ]; then
    echo "❌ Key file not found: $KEY_FILE"
    echo "Usage: EC2_HOST=your-ip KEY_FILE=~/.ssh/key.pem ./deploy.sh"
    exit 1
fi

echo "📦 Preparing files..."
DEPLOY_FILES="main.py requirements-prod.txt Dockerfile .env"

# Create temp directory
TEMP_DIR=$(mktemp -d)
for file in $DEPLOY_FILES; do
    if [ -f "$file" ]; then
        cp "$file" "$TEMP_DIR/"
    fi
done

# Create docker-compose.yml
cat > "$TEMP_DIR/docker-compose.yml" << 'EOF'
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
EOF

echo "📤 Uploading to EC2..."
ssh -i "$KEY_FILE" "$EC2_USER@$EC2_HOST" "mkdir -p $REMOTE_DIR"
scp -i "$KEY_FILE" "$TEMP_DIR"/* "$EC2_USER@$EC2_HOST:$REMOTE_DIR/"

echo "🔨 Building and starting on EC2..."
ssh -i "$KEY_FILE" "$EC2_USER@$EC2_HOST" << 'REMOTE'
cd ~/bllue-backend
docker-compose down || true
docker-compose up -d --build
sleep 5
curl -s http://localhost:8000/api/health
REMOTE

echo ""
echo "✅ Deployment complete!"
echo "🌐 API should be running at http://$EC2_HOST:8000"
echo ""
echo "Next steps:"
echo "1. Configure Nginx + SSL (see DEPLOY_EC2.md)"
echo "2. Update frontend .env with production URL"
echo "3. Rebuild mobile apps with EAS"

# Cleanup
rm -rf "$TEMP_DIR"
