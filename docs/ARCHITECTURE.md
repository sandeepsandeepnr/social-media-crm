# System Architecture - Phase-1a

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           INTERNET                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │   Facebook   │  │  Instagram   │  │    nginx     │                   │
│  │   Graph API  │  │  Graph API   │  │   (Optional) │                   │
│  └──────────────┘  └──────────────┘  └──────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
                             ↓ Webhooks
                             ↓ API Calls
┌─────────────────────────────────────────────────────────────────────────┐
│                    DOCKER CONTAINER LAYER                               │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │ FastAPI Backend Application                                    │    │
│  │                                                                 │    │
│  │  ┌─────────────────────────────────────────────────────────┐  │    │
│  │  │ API Routes Layer                                        │  │    │
│  │  ├─ /api/v1/auth/*           Authentication Endpoints     │  │    │
│  │  ├─ /api/v1/users/*          User Management              │  │    │
│  │  ├─ /api/v1/platforms/*      Platform Integration         │  │    │
│  │  ├─ /api/v1/interactions/*   Interaction Management       │  │    │
│  │  ├─ /api/v1/tickets/*        Ticket Management            │  │    │
│  │  ├─ /api/v1/responses/*      Response Management          │  │    │
│  │  ├─ /api/v1/dashboard/*      Analytics & Metrics          │  │    │
│  │  └─ /webhooks/social-media/* Webhook Receivers            │  │    │
│  │  └─────────────────────────────────────────────────────────┘  │    │
│  │                                                                 │    │
│  │  ┌─────────────────────────────────────────────────────────┐  │    │
│  │  │ Services Layer                                          │  │    │
│  │  ├─ AuthService             JWT & Password Management     │  │    │
│  │  ├─ UserService             User CRUD Operations          │  │    │
│  │  ├─ InteractionService      Interaction Processing        │  │    │
│  │  ├─ TicketService           Ticket Management Logic       │  │    │
│  │  ├─ ResponseService         Response Publishing           │  │    │
│  │  ├─ WebhookService          Event Processing              │  │    │
│  │  └─ PlatformService         Integration Coordination      │  │    │
│  │  └─────────────────────────────────────────────────────────┘  │    │
│  │                                                                 │    │
│  │  ┌─────────────────────────────────────────────────────────┐  │    │
│  │  │ Integration Layer                                       │  │    │
│  │  ├─ FacebookIntegration    FB Graph API Wrapper            │  │    │
│  │  ├─ InstagramIntegration   IG Graph API Wrapper            │  │    │
│  │  └─ BaseIntegration        Common Integration Logic        │  │    │
│  │  └─────────────────────────────────────────────────────────┘  │    │
│  │                                                                 │    │
│  │  ┌─────────────────────────────────────────────────────────┐  │    │
│  │  │ Database Access Layer (SQLAlchemy ORM)                 │  │    │
│  │  └─────────────────────────────────────────────────────────┘  │    │
│  │                                                                 │    │
│  │  ┌─────────────────────────────────────────────────────────┐  │    │
│  │  │ Middleware & Utilities                                 │  │    │
│  │  ├─ Authentication Middleware    JWT Verification         │  │    │
│  │  ├─ Logging Middleware           Request/Response Logs    │  │    │
│  │  ├─ Error Handling               Custom Exceptions        │  │    │
│  │  └─ Utilities                    Common Functions          │  │    │
│  │  └─────────────────────────────────────────────────────────┘  │    │
│  │                                                                 │    │
│  └────────────────────────────────────────────────────────────────┘    │
│         ↓ SQL                              ↓ HTTP                       │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────┐  ┌──────────────────────┐                  │
│  │  PostgreSQL Database   │  │  Redis Cache         │                  │
│  │  - users               │  │  - Sessions          │                  │
│  │  - platforms           │  │  - Interactions      │                  │
│  │  - credentials         │  │  - Cached Queries    │                  │
│  │  - customers           │  └──────────────────────┘                  │
│  │  - interactions        │                                             │
│  │  - tickets             │                                             │
│  │  - responses           │                                             │
│  │  - audit_logs          │                                             │
│  └────────────────────────┘                                             │
└─────────────────────────────────────────────────────────────────────────┘
         ↑ SQL Connection                     ↑ Cache Connection
         │ Port: 5432                         │ Port: 6379
         │                                    │
         ↓ Volumes: postgres_data             ↓ Volumes: redis_data
```

---

## Application Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      CUSTOMER INTERACTION FLOW                       │
└─────────────────────────────────────────────────────────────────────┘

1. INTERACTION CAPTURE
   ┌──────────────┐
   │  Customer   │
   │   Posts on   │
   │  Facebook/  │
   │  Instagram  │
   └──────┬───────┘
          │
          └─→ [Social Platform stores interaction]
              │
              └─→ [Platform sends webhook to CRM]
                  │
                  ↓
   ┌──────────────────────────┐
   │ POST /webhooks/social-   │
   │ media/{platform}         │
   └──────────────────────────┘
              │
              ↓

2. INTERACTION PROCESSING
   ┌──────────────────────────┐
   │ WebhookService.process() │
   ├──────────────────────────┤
   │ 1. Parse webhook payload │
   │ 2. Verify authenticity   │
   │ 3. Extract customer info │
   │ 4. Store interaction     │
   │ 5. Create/update customer│
   └──────────────────────────┘
              │
              ↓

3. TICKET AUTO-CREATION (Optional)
   ┌──────────────────────────┐
   │ if auto_create_tickets:  │
   │   TicketService.create() │
   │   - Set status: OPEN     │
   │   - Set priority         │
   │   - Assign to agent      │
   └──────────────────────────┘
              │
              ↓

4. AGENT NOTIFICATION
   ┌──────────────────────────┐
   │ Dashboard Updates        │
   │ - New interaction badge  │
   │ - Unprocessed count      │
   │ - Appears in inbox       │
   └──────────────────────────┘
              │
              ↓

5. AGENT ACTION
   ┌──────────────────────────┐
   │ Agent opens interaction  │
   │ - Views customer profile │
   │ - Reads message/comments │
   │ - Views conversation     │
   │ - Decides response       │
   └──────────────────────────┘
              │
              ├─→ Create/Link Ticket
              │
              ├─→ Draft Response
              │   POST /api/v1/responses
              │
              └─→ Send Response
                  POST /api/v1/responses/{id}/send
                  │
                  ↓
   ┌──────────────────────────┐
   │ ResponseService.publish()│
   │ 1. Validate content      │
   │ 2. Format for platform   │
   │ 3. Call platform API     │
   │ 4. Store confirmation    │
   │ 5. Update ticket status  │
   └──────────────────────────┘
              │
              ↓

6. RESPONSE PUBLICATION
   ┌──────────────────────────┐
   │ POST to Social Platform  │
   │ /graph.facebook.com/...  │
   │ /graph.instagram.com/... │
   └──────────────────────────┘
              │
              ↓

7. CONVERSATION CONTINUATION
   ┌──────────────────────────┐
   │ Customer replies to      │
   │ agent's response         │
   └──────────────────────────┘
              │
              └─→ [New interaction]
                  └─→ [Link to same ticket]
                      └─→ [Update conversation]

8. TICKET CLOSURE
   ┌──────────────────────────┐
   │ Agent resolves ticket    │
   │ PUT /api/v1/tickets/{id}/│
   │ resolve                  │
   │ - Set status: RESOLVED   │
   │ - Add resolution summary │
   │ - Record close time      │
   └──────────────────────────┘
              │
              ↓

9. ANALYTICS UPDATE
   ┌──────────────────────────┐
   │ Dashboard metrics update │
   │ - Response time (FRT)    │
   │ - Resolution time (ART)  │
   │ - Agent productivity     │
   │ - Sentiment (Phase-2)    │
   └──────────────────────────┘
```

---

## Database Schema Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      USERS & AUTHENTICATION                     │
├─────────────────────────────────────────────────────────────────┤
│ users                                                            │
│ ├─ id (PK)                                                       │
│ ├─ username, email (UNIQUE)                                     │
│ ├─ password_hash                                                 │
│ ├─ role: 'admin' | 'team_leader' | 'agent'                     │
│ ├─ is_active, is_verified                                       │
│ └─ created_at, updated_at, last_login                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   PLATFORM INTEGRATION                          │
├─────────────────────────────────────────────────────────────────┤
│ platforms                                                        │
│ ├─ id (PK)                                                       │
│ ├─ name: 'facebook' | 'instagram' | ...                         │
│ ├─ display_name, icon_url                                       │
│ └─ supports_media, max_message_length                           │
│                                                                  │
│ platform_credentials (FK: users.id, platforms.id)               │
│ ├─ id (PK)                                                       │
│ ├─ business_account_id, business_account_name                   │
│ ├─ access_token, refresh_token                                  │
│ ├─ token_expires_at, scope                                      │
│ ├─ is_active, sync_status                                       │
│ └─ last_sync_at, error_message                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    CUSTOMERS & INTERACTIONS                     │
├─────────────────────────────────────────────────────────────────┤
│ customers (FK: platforms.id)                                     │
│ ├─ id (PK)                                                       │
│ ├─ platform_user_id                                              │
│ ├─ display_name, avatar_url, profile_url                        │
│ ├─ follower_count, is_verified_on_platform                      │
│ └─ first_interaction_at, last_interaction_at                    │
│                                                                  │
│ interactions (FK: platforms.id, customers.id)                   │
│ ├─ id (PK)                                                       │
│ ├─ platform_interaction_id (UNIQUE)                             │
│ ├─ interaction_type: 'comment'|'message'|'mention'|'review'    │
│ ├─ content, media_urls[]                                         │
│ ├─ parent_interaction_id (self-ref for threads)                 │
│ ├─ is_public, is_processed                                       │
│ ├─ captured_at, platform_metadata                               │
│ └─ post_url                                                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      TICKETS & RESPONSES                        │
├─────────────────────────────────────────────────────────────────┤
│ tickets (FK: customers.id, users.id, platforms.id,              │
│          interactions.id)                                        │
│ ├─ id (PK)                                                       │
│ ├─ ticket_number (UNIQUE)                                        │
│ ├─ status: 'open'|'in_progress'|'pending'|'resolved'|'closed'  │
│ ├─ priority: 'low'|'medium'|'high'|'urgent'                    │
│ ├─ subject, description                                         │
│ ├─ assigned_to_agent_id, assigned_to_team_lead_id              │
│ ├─ tags[], internal_notes                                       │
│ ├─ is_duplicate, duplicate_of_ticket_id                         │
│ ├─ opened_at, first_response_at, resolved_at, closed_at         │
│ └─ resolution_summary                                            │
│                                                                  │
│ ticket_interactions (FK: tickets.id, interactions.id)            │
│ ├─ id (PK)                                                       │
│ ├─ ticket_id, interaction_id                                     │
│ └─ sequence_number                                               │
│                                                                  │
│ responses (FK: tickets.id, users.id, platforms.id,              │
│            interactions.id)                                      │
│ ├─ id (PK)                                                       │
│ ├─ content, media_urls[]                                         │
│ ├─ response_type: 'manual'|'template'|'ai_suggested'           │
│ ├─ status: 'draft'|'submitted'|'published'|'failed'            │
│ ├─ is_private_message                                           │
│ ├─ platform_post_id                                              │
│ ├─ sent_at, platform_response                                    │
│ └─ error_message                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      AUDIT & SETTINGS                           │
├─────────────────────────────────────────────────────────────────┤
│ audit_logs (FK: users.id)                                        │
│ ├─ id (PK)                                                       │
│ ├─ action, entity_type, entity_id                               │
│ ├─ old_values, new_values (JSONB)                               │
│ ├─ ip_address, user_agent                                        │
│ └─ created_at                                                    │
│                                                                  │
│ system_settings (FK: users.id)                                   │
│ ├─ id (PK)                                                       │
│ ├─ setting_key, setting_value                                    │
│ ├─ setting_type: 'string'|'boolean'|'integer'|'json'           │
│ └─ description                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Call Flow Example

```
USER ACTION: Create Ticket from Interaction

Frontend                           Backend                    Database
   │                                 │                           │
   ├─ User clicks "Create Ticket"    │                           │
   │                                 │                           │
   ├─ POST /api/v1/tickets          │                           │
   │  {                              │                           │
   │   "primary_interaction_id"      │                           │
   │  }                              │                           │
   │────────────────────────────────→│                           │
   │                                 │                           │
   │                                 ├─ Verify JWT token         │
   │                                 │                           │
   │                                 ├─ Query interaction        │
   │                                 ├──────────────────────────→│
   │                                 │  SELECT * FROM interactions
   │                                 │                           │
   │                                 │←──────────────────────────┤
   │                                 │  Interaction data         │
   │                                 │                           │
   │                                 ├─ Create ticket           │
   │                                 ├─ Generate ticket_number   │
   │                                 ├─ Set initial status       │
   │                                 │                           │
   │                                 ├─ INSERT into tickets      │
   │                                 ├──────────────────────────→│
   │                                 │  INSERT INTO tickets...   │
   │                                 │                           │
   │                                 │←──────────────────────────┤
   │                                 │  ticket_id, ticket_number │
   │                                 │                           │
   │                                 ├─ Link interaction        │
   │                                 ├──────────────────────────→│
   │                                 │  INSERT INTO              │
   │                                 │  ticket_interactions...   │
   │                                 │                           │
   │                                 │←──────────────────────────┤
   │                                 │  Link created             │
   │                                 │                           │
   │                                 ├─ Update audit log        │
   │                                 ├──────────────────────────→│
   │                                 │  INSERT INTO audit_logs   │
   │                                 │                           │
   │                                 │←──────────────────────────┤
   │                                 │                           │
   │  200 OK                         │                           │
   │  {                              │                           │
   │   "id": "ticket_uuid",          │                           │
   │   "ticket_number": "TKT-123456"│                           │
   │  }                              │                           │
   │←────────────────────────────────│                           │
   │                                 │                           │
   ├─ Update UI with new ticket     │                           │
   │  - Refresh interactions list    │                           │
   │  - Show success message         │                           │
   │  - Redirect to ticket view      │                           │
   │                                 │                           │
   └─────────────────────────────────────────────────────────────│
```

---

## Deployment Architecture (AWS)

```
┌─────────────────────────────────────────────────────────────────┐
│                        AWS CLOUD                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │                       Route53 (DNS)                     │    │
│  │                 yourdomain.com → CloudFront            │    │
│  └────────────────────────────────────────────────────────┘    │
│                            ↓                                    │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  CloudFront (CDN)                                      │    │
│  │  - Caches static assets                                │    │
│  │  - SSL/TLS termination                                 │    │
│  │  - Cache invalidation on deployment                    │    │
│  └────────────────────────────────────────────────────────┘    │
│           ↓                           ↓                         │
│  ┌────────────────────┐    ┌────────────────────────────┐      │
│  │  S3 (Frontend)     │    │  Application Load Balancer │      │
│  │  - login.html      │    │  - Distributes traffic     │      │
│  │  - dashboard.html  │    │  - SSL/TLS                 │      │
│  │  - CSS, JS         │    │  - Health checks           │      │
│  └────────────────────┘    └────────────────────────────┘      │
│                                       ↓                         │
│  ┌─────────────────────────────────────────────────────┐       │
│  │          ECS Fargate (Containerized Backend)        │       │
│  │  ┌────────────────────────────────────────────┐    │       │
│  │  │  Task 1: FastAPI Container (Port 8000)   │    │       │
│  │  │  - Processes requests                     │    │       │
│  │  │  - Handles webhooks                       │    │       │
│  │  │  - API endpoints                          │    │       │
│  │  └────────────────────────────────────────────┘    │       │
│  │  ┌────────────────────────────────────────────┐    │       │
│  │  │  Task 2: FastAPI Container (Port 8000)   │    │       │
│  │  │  - Redundancy                             │    │       │
│  │  │  - Load distribution                      │    │       │
│  │  └────────────────────────────────────────────┘    │       │
│  │  ┌────────────────────────────────────────────┐    │       │
│  │  │  Task N: FastAPI Containers               │    │       │
│  │  │  - Auto-scaling based on CPU/Memory       │    │       │
│  │  └────────────────────────────────────────────┘    │       │
│  └─────────────────────────────────────────────────────┘       │
│         ↓ SQL Connection              ↓ Cache Connection      │
│  ┌────────────────────┐    ┌──────────────────────┐           │
│  │ RDS PostgreSQL     │    │ ElastiCache (Redis)  │           │
│  │                    │    │                      │           │
│  │ - Multi-AZ         │    │ - Session cache      │           │
│  │ - Automated backup │    │ - Query cache        │           │
│  │ - Read replicas    │    │ - Rate limiting      │           │
│  │ - Encryption       │    │                      │           │
│  └────────────────────┘    └──────────────────────┘           │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  CloudWatch (Monitoring & Logging)                    │  │
│  │  - Application logs                                   │  │
│  │  - Performance metrics                                │  │
│  │  - Alarms & Alerts                                    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Secrets Manager                                      │  │
│  │  - API keys                                            │  │
│  │  - Database credentials                               │  │
│  │  - Social platform tokens                             │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Security Architecture

```
SECURITY LAYERS
├── External (CDN & WAF)
│   └── CloudFront + AWS WAF
│       ├── DDoS protection
│       ├── SQL injection blocking
│       └── Rate limiting
│
├── Network Layer
│   └── VPC + Security Groups
│       ├── Private subnets for DB
│       ├── Restricted access
│       └── Encrypted traffic (TLS)
│
├── Application Layer
│   ├── JWT Authentication
│   │   └── Token verification on every request
│   ├── Authorization (RBAC)
│   │   └── Role-based access control
│   ├── Input Validation
│   │   └── Sanitize all user inputs
│   └── Error Handling
│       └── Don't expose internals
│
├── Data Layer
│   ├── Database Encryption
│   │   └── At-rest encryption (RDS)
│   ├── Connection Pooling
│   │   └── Secure connections
│   ├── SQL Injection Prevention
│   │   └── Parameterized queries (ORM)
│   └── Audit Logging
│       └── Track all changes
│
└── Secrets Management
    └── AWS Secrets Manager
        ├── API credentials
        ├── Database passwords
        └── Encryption keys
```

This completes your comprehensive **Phase-1a MVP development package**!
