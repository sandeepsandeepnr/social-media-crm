# Social Media CRM - Phase-1a Deployment & Setup Guide

## Quick Start (Local Development)

### Prerequisites
- Docker & Docker Compose (or Python 3.11+, PostgreSQL)
- Git
- Text editor/IDE

### Option 1: Docker Compose (Recommended)

```bash
# 1. Clone/navigate to project
cd social-media-crm

# 2. Create .env file (copy from example)
cp backend/.env.example backend/.env

# 3. Update .env with your values
# - FACEBOOK_APP_ID, FACEBOOK_APP_SECRET
# - INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET
# - SECRET_KEY (generate a secure key)
# - WEBHOOK_VERIFY_TOKEN

# 4. Start services
docker-compose -f deployment/docker-compose.yml up -d

# 5. Wait for services to be healthy
docker-compose -f deployment/docker-compose.yml ps

# 6. Access the application
# Backend: http://localhost:8000
# Frontend: http://localhost:80
# Docs: http://localhost:8000/api/docs
```

### Option 2: Manual Setup (Local Development)

**Backend Setup:**
```bash
cd backend

# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file
cp .env.example .env

# 4. Create database
# Ensure PostgreSQL is running
createdb -U postgres social_media_crm

# 5. Apply schema
psql -U postgres -d social_media_crm < ../database/schema.sql

# 6. Run backend
python main.py
```

**Frontend Setup:**
```bash
cd frontend

# Option A: Simple HTTP server
python -m http.server 8080

# Option B: Use Node.js http-server
npx http-server -p 8080 -c-1

# Access: http://localhost:8080/login.html
```

---

## First Run - Initial Setup

### 1. Access the Application

```
http://localhost (via Docker)
or
http://localhost:8080/login.html (manual setup)
```

### 2. Create Admin User

**Via API:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@example.com",
    "password": "AdminPassword123!",
    "first_name": "Admin",
    "last_name": "User",
    "role": "admin"
  }'
```

**Response:**
```json
{
  "id": "user_uuid",
  "username": "admin",
  "email": "admin@example.com",
  "token": "jwt_token"
}
```

### 3. Login to Dashboard

1. Go to login page
2. Enter admin@example.com / AdminPassword123!
3. Access dashboard

### 4. Configure Social Platform Integrations

**In Admin Panel / Settings:**

1. Navigate to "Settings" → "Platform Integrations"
2. Click "Connect Platform"
3. Select "Facebook"
4. Provide:
   - App ID: Your Facebook App ID
   - App Secret: Your Facebook App Secret
   - Business Account ID: Your Facebook Page ID
   - Access Token: Facebook Page Access Token

5. Repeat for Instagram

**Via API:**
```bash
curl -X POST http://localhost:8000/api/v1/platform-credentials \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "platform_id": "facebook_uuid",
    "business_account_id": "PAGE_ID",
    "business_account_name": "My Business Page",
    "access_token": "EAAB...",
    "scope": "pages_read_engagement,pages_manage_metadata"
  }'
```

### 5. Verify Webhook Configuration

Ensure your webhooks are configured:

**Facebook/Instagram:**
1. Go to App Dashboard → Messenger → Settings
2. Configure Callback URL:
   - Local: Use ngrok (see below)
   - Production: `https://yourdomain.com/webhooks/social-media/facebook`
3. Set Verify Token: Use `.env` WEBHOOK_VERIFY_TOKEN
4. Subscribe to events: messages, comments, etc.

**Using ngrok for local testing:**
```bash
# Install ngrok
# Download from https://ngrok.com/

# Start tunnel
ngrok http 8000

# Use forwarding URL in Facebook webhook settings
# https://abc123.ngrok.io/webhooks/social-media/facebook
```

---

## Production Deployment

### AWS Deployment (Recommended)

#### Architecture
```
API Gateway → ALB → ECS Fargate → RDS PostgreSQL
           ↓
        S3 (Frontend)
```

#### Step 1: Prepare Docker Images

```bash
# 1. Build backend image
docker build -f deployment/Dockerfile -t social-crm-backend:latest .

# 2. Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com

docker tag social-crm-backend:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/social-crm-backend:latest

docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/social-crm-backend:latest
```

#### Step 2: Create RDS Database

```bash
aws rds create-db-instance \
  --db-instance-identifier social-crm-prod-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username crm_admin \
  --master-user-password ChangeMe123! \
  --allocated-storage 20 \
  --publicly-accessible false \
  --db-name social_media_crm
```

#### Step 3: Deploy to ECS Fargate

Create task definition (social-crm-task.json):
```json
{
  "family": "social-crm-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "social-crm-backend",
      "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/social-crm-backend:latest",
      "portMappings": [{"containerPort": 8000}],
      "environment": [
        {"name": "ENVIRONMENT", "value": "production"},
        {"name": "DEBUG", "value": "false"},
        {"name": "DATABASE_URL", "value": "postgresql://..."}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/social-crm",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://social-crm-task.json

# Create ECS cluster
aws ecs create-cluster --cluster-name social-crm-prod

# Create ECS service
aws ecs create-service \
  --cluster social-crm-prod \
  --service-name social-crm-backend \
  --task-definition social-crm-backend \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=DISABLED}"
```

#### Step 4: Deploy Frontend to S3

```bash
# Build frontend (create deployment bundle)
cd frontend

# Upload to S3
aws s3 sync . s3://social-crm-prod-frontend/

# Enable static website hosting
aws s3 website s3://social-crm-prod-frontend/ \
  --index-document login.html \
  --error-document login.html
```

#### Step 5: Configure CloudFront CDN

```bash
aws cloudfront create-distribution \
  --origin-domain-name social-crm-prod-frontend.s3-website-us-east-1.amazonaws.com \
  --default-root-object login.html
```

#### Step 6: Setup Domain & SSL

```bash
# Request ACM certificate
aws acm request-certificate \
  --domain-name yourdomain.com \
  --subject-alternative-names "*.yourdomain.com"

# Update Route53
aws route53 create-hosted-zone --name yourdomain.com --caller-reference "2024-01-01"
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# Check backend health
curl http://localhost:8000/health

# Check API health
curl http://localhost:8000/api/health

# View logs
docker logs social-crm-backend
docker logs social-crm-db
```

### Database Backups

```bash
# Local backup
pg_dump -U crm_user -d social_media_crm > backup_$(date +%Y%m%d).sql

# AWS RDS automated backups (enabled by default)
# Manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier social-crm-prod-db \
  --db-snapshot-identifier social-crm-backup-$(date +%Y%m%d)
```

### Auto-scaling (AWS)

```bash
# Setup auto-scaling for ECS service
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/social-crm-prod/social-crm-backend \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10

# Create scaling policy
aws application-autoscaling put-scaling-policy \
  --policy-name cpu-scaling \
  --service-namespace ecs \
  --resource-id service/social-crm-prod/social-crm-backend \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration TargetValue=70,PredefinedMetricSpecification={PredefinedMetricType=ECSServiceAverageCPUUtilization}
```

---

## Troubleshooting

### Services won't start

```bash
# Check logs
docker-compose logs backend
docker-compose logs postgres

# Common issues:
# 1. Port already in use
#    Solution: Change port in docker-compose.yml
# 2. Database connection failed
#    Solution: Ensure postgres service is healthy (wait a few seconds)
# 3. Out of memory
#    Solution: Allocate more memory to Docker
```

### Cannot access dashboard

```bash
# Check if backend is running
curl http://localhost:8000/health

# Check if frontend is served
curl http://localhost/login.html

# Check CORS settings in config.py
# Ensure your domain is in CORS_ORIGINS
```

### Database migrations

```bash
# If schema is not automatically applied:
psql -U crm_user -d social_media_crm < database/schema.sql

# Or use Docker exec:
docker exec -i social-crm-db psql -U crm_user -d social_media_crm < database/schema.sql
```

---

## Security Checklist

- [ ] Change all default passwords
- [ ] Enable HTTPS/SSL in production
- [ ] Set strong SECRET_KEY in .env
- [ ] Update CORS_ORIGINS for production domain
- [ ] Enable database encryption (RDS/managed service)
- [ ] Use environment variables for all secrets
- [ ] Enable API rate limiting
- [ ] Configure firewall rules
- [ ] Enable audit logging
- [ ] Regular security updates for dependencies
- [ ] Backup database regularly
- [ ] Monitor API logs for suspicious activity

---

## Performance Tuning

**Database:**
- Enable connection pooling
- Add indexes on frequently queried columns (already done in schema.sql)
- Monitor slow queries: `log_min_duration_statement = 1000`

**Backend:**
- Use Redis caching for interactions
- Implement pagination (default 20 items)
- Add CDN for static assets

**Frontend:**
- Minify CSS/JS
- Enable gzip compression
- Use service workers for offline support
