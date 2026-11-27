# Social Media Customer Engagement & Reputation Management CRM

**Version**: 1.0.0-alpha (Phase-1a)  
**Status**: Phase-1a MVP Development  
**Last Updated**: November 19, 2024

---

## 📋 Overview

A unified **Social Media Handling CRM** designed to help organizations monitor, manage, respond to and resolve customer interactions across multiple social media platforms through a centralized interface.

**Phase-1a** currently includes a local unified inbox, ticket workflows,
account-aware webhook ingestion, and response drafts. Facebook and Instagram
integration paths have been tested with mocked APIs, not live accounts.

---

## 🚀 Quick Start

### Local Development (Windows PowerShell)
```powershell
# Terminal 1: Backend
cd D:\social-media-crm\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# The example uses a local SQLite database. Set a private SECRET_KEY in backend\.env.
python main.py

# Terminal 2: Frontend
cd D:\social-media-crm\frontend
py -m http.server 8080
```

The static frontend uses Tailwind's browser CDN for a shadcn-inspired visual
theme, so no React or Node.js/npm build is required. Bootstrap remains in place
for existing modal and form behavior. An internet connection is needed for the
CDN stylesheets; this browser-based Tailwind setup is for local development,
and deployment can use compiled assets when that work is planned.

Open the frontend at http://localhost:8080/login.html and the API docs at
http://localhost:8000/api/docs. The first account registered becomes the local
administrator; further self-registered accounts receive the agent role. No
pre-seeded credentials are required.

Dashboard, inbox, monitoring, tickets, customers, and analytics each have their own HTML
page. Administrators can open the Admin page for separate Team, Integrations,
and Settings pages. Admin API operations require an administrator account.
Team management includes profile editing and account roles/status; integrations
support editing account metadata and replacing an access token.
Automatic ticket creation follows the connected account owner's setting. It
applies to webhook events and manual captures that specify an active
`business_account_id`; manual captures without an account remain unprocessed.
Webhook follow-ups are linked only when a parent reference identifies an
interaction or published reply for the same account and customer, exactly one
ticket matches, and that ticket is still active. Otherwise a new ticket is
created. Automated sync, assignment, and response approval settings are not
yet enforced.

Publishing uses the interaction's originating account. For older interactions
without an origin, publishing is allowed only if exactly one active account
exists for that platform. A signed webhook redelivery can establish the origin
of a legacy interaction. Disconnected or paused origin accounts cannot publish.
Supported publishing paths are public comment replies and private message
replies; private replies to comments and other interaction types are not yet
implemented. Instagram messaging with Facebook Login requires the linked Page
token and the relevant Meta permissions. Meta messaging windows and access
requirements apply.

### Monitoring and Meta verification

Administrators can add saved keywords, hashtags, and brand terms on the
Monitoring page. Agents can select a term to view matching captured
interaction content; the page refreshes periodically. Matching is literal
substring matching, not platform-wide keyword search or alerting. SQLite's
case-insensitive matching is limited for non-ASCII text.

Administrators can manually search public Instagram recent media by hashtag
on the same page. This requires an active connected Instagram professional
account, Meta's `instagram_basic` permission and Instagram Public Content
Access approval, plus a separate Facebook **user** access token with access to
the connected Page. Save that token in Monitoring; it is encrypted and never
returned by the API. Configure a private, persistent `SECRET_KEY` before
connecting real accounts or saving tokens. Changing the key makes existing
encrypted credentials unreadable.

Each explicit search may count toward Meta's limit of 30 unique hashtags per
account in a rolling seven days. Only the first page of recent public media is
displayed, typically from the preceding 24 hours; searches are not scheduled,
and results are not saved as interactions or tickets. Meta does not allow
replies via hashtag discovery. See [Meta's hashtag search documentation](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login/hashtag-search/)
and [recent media reference](https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-hashtag/recent-media/).

The Integrations page's **Verify access** action checks only that Meta allows
the configured token to read the account ID. It does not validate webhook
delivery, messaging, comment publishing, or granted permissions. Those require
an authorized test account and live testing; webhook delivery also needs a
public HTTPS callback. The default Graph API version is v27.0 and can be
overridden with `FACEBOOK_API_VERSION`. No live account was available during
local validation.

Responses with an unknown delivery outcome or left in `sending` after an
interruption must be checked on the social platform before any new response is
sent. They are not automatically retried. Set `FACEBOOK_APP_SECRET` for signed
webhooks; unsigned webhooks are accepted only in local debug mode.

On startup an index enforces one ticket per interaction. Existing duplicate
links cause startup to fail without deleting data; resolve those duplicates
deliberately before restarting. Back up the database before schema changes.

On macOS/Linux, use `python3 -m venv .venv`, activate `.venv/bin/activate`,
and run `python3 -m http.server 8080` in the frontend directory.

The local database is created automatically at `backend/social_media_crm.db`.
PostgreSQL connection URLs are also supported for local development.

---

## 📁 Project Structure

```
social-media-crm/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── models.py          # SQLAlchemy ORM models
│   │   ├── schemas.py         # Pydantic request/response schemas
│   │   ├── api/               # Route handlers
│   │   ├── security.py        # JWT, password, credential helpers
│   │   └── database.py        # Local DB session and initialization
│   ├── requirements.txt
│   ├── config.py
│   ├── main.py
│   └── .env.example
│
├── frontend/                   # HTML/CSS/JavaScript
│   ├── login.html
│   ├── dashboard.html, inbox.html, tickets.html
│   ├── customers.html, analytics.html
│   ├── admin.html, team.html, integrations.html, settings.html
│   ├── dashboard.js, layout.js
│   └── dashboard.css, theme.js
│
├── database/
│   └── schema.sql             # PostgreSQL schema
│
├── deployment/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── nginx.conf
│
└── docs/
    ├── API_SPECIFICATION.md
    ├── SOCIAL_MEDIA_INTEGRATION.md
    └── DEPLOYMENT_GUIDE.md
```

---

## 📚 Documentation

### API Documentation
- **OpenAPI/Swagger**: http://localhost:8000/api/docs
- **Full API Spec**: [API_SPECIFICATION.md](docs/API_SPECIFICATION.md)

### Setup & Deployment
- **Quick Start**: This README
- **Detailed Deployment**: [DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)
- **Social Integration Setup**: [SOCIAL_MEDIA_INTEGRATION.md](docs/SOCIAL_MEDIA_INTEGRATION.md)

---

## 🔑 Key Features (Phase-1a)

### 1. Social Media Integration
- Facebook and Instagram comment and message webhook parsing (live permissions
  and payloads require validation)
- Account-specific routing and duplicate-event detection
- Saved literal matching for captured interactions and manual Instagram hashtag
  discovery; live permissions and provider behavior remain unverified
- Other platforms, historical retrieval, reviews and platform-wide keyword
  discovery remain unimplemented or unverified

### 2. Unified Inbox
- Centralized view of all interactions
- Filter by platform and status
- Search customer interactions
- Interaction details with conversation history

### 3. Ticket Management
- Automatic ticket creation from interactions
- Ticket lifecycle: Open → In Progress → Pending → Resolved → Closed
- Ticket assignment to agents
- Internal notes

### 4. Response Management
- Draft and send responses via CRM
- Support for text responses
- Response status tracking
- Conversation threading

### 5. Dashboard & Metrics
- Real-time metrics (interactions, open tickets, etc.)
- Average response time
- Platform-wise breakdown
- Agent workload overview

### 6. User Management
- Role-based access (Admin, Team Leader, Agent)
- User creation & management (Admin only)
- Secure JWT authentication
- Activity audit logging

---

## 🛠 Technology Stack

### Backend
- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL 15
- **Cache**: Redis (optional)
- **Auth**: JWT + bcrypt
- **Deployment**: Docker + Docker Compose

### Frontend
- **HTML5**, **CSS3**, **JavaScript ES6+**
- **Bootstrap 5** (UI framework)
- **Fetch API** (HTTP requests)
- **AJAX** for dynamic updates

### Infrastructure
- **Containerization**: Docker
- **Orchestration**: Docker Compose (dev), AWS ECS (prod)
- **Database**: RDS PostgreSQL (prod)
- **Storage**: S3 (frontend assets)
- **CDN**: CloudFront

---

## 📖 API Endpoints

### Authentication
```
POST   /api/v1/auth/register          Register new user
POST   /api/v1/auth/login             User login
POST   /api/v1/auth/refresh           Refresh token
POST   /api/v1/auth/logout            Logout
```

### Interactions
```
GET    /api/v1/interactions           Get all interactions
GET    /api/v1/interactions/{id}      Get interaction details
PATCH  /api/v1/interactions/{id}      Mark as processed
POST   /webhooks/social-media/{type}  Webhook receiver
```

### Tickets
```
GET    /api/v1/tickets                Get all tickets
GET    /api/v1/tickets/{id}           Get ticket details
POST   /api/v1/tickets                Create ticket
PUT    /api/v1/tickets/{id}           Update ticket
PUT    /api/v1/tickets/{id}/resolve   Resolve ticket
```

### Responses
```
POST   /api/v1/responses              Draft response
GET    /api/v1/responses/{id}         Get response
PUT    /api/v1/responses/{id}         Update response
POST   /api/v1/responses/{id}/send    Send to platform
```

### Platforms
```
GET    /api/v1/platforms              Get available platforms
POST   /api/v1/platform-credentials   Connect platform account
GET    /api/v1/platform-credentials   Get connected accounts
DELETE /api/v1/platform-credentials   Disconnect account
```

### Dashboard
```
GET    /api/v1/dashboard/metrics      Get metrics
GET    /api/v1/analytics/platforms    Get platform analytics
```

[Full API Spec →](docs/API_SPECIFICATION.md)

---

## 🔐 Security

### Authentication
- JWT tokens with 30-minute expiry
- Refresh tokens for extended sessions
- bcrypt password hashing
- Secure token storage in localStorage

### Authorization
- Role-based access control (RBAC)
- Admin-only endpoints for sensitive operations
- Audit logging for all changes

### Data Protection
- PostgreSQL encryption support
- HTTPS/TLS in production
- Secure webhook verification
- CORS configuration
- SQL injection prevention via ORM

---

## 🧪 Testing

### Manual Testing
```bash
# Test backend health
curl http://localhost:8000/health

# Test API endpoint
curl -H "Authorization: Bearer {token}" \
     http://localhost:8000/api/v1/interactions

# Test webhook
curl -X POST http://localhost:8000/webhooks/social-media/facebook \
     -H "Content-Type: application/json" \
     -d '{"object":"page","entry":[...]}'
```

### Automated Tests
```bash
cd backend
pytest                          # Run all tests
pytest -v                       # Verbose output
pytest --cov                    # Coverage report
pytest tests/test_auth.py       # Specific test file
```

---

## 🚦 Workflow

```
1. Customer interacts on social media (Facebook/Instagram)
   ↓
2. CRM receives webhook event
   ↓
3. Interaction stored in database
   ↓
4. Agent views in unified inbox
   ↓
5. Agent creates ticket & assigns priority
   ↓
6. Agent drafts response in CRM
   ↓
7. Agent sends response back to platform
   ↓
8. Conversation tracked in ticket
   ↓
9. Agent resolves ticket
   ↓
10. Analytics updated
```

---

## 📊 Database Schema

### Core Tables
- **users** - System users (agents, team leads, admins)
- **platforms** - Supported social platforms
- **platform_credentials** - Connected platform accounts
- **customers** - Social media users/customers
- **interactions** - Raw social media posts/comments/messages
- **tickets** - Support tickets created from interactions
- **responses** - Agent responses sent back to customers
- **audit_logs** - Activity logging

[Full Schema →](database/schema.sql)

---

## 🔄 Integration Setup

### Facebook
1. Create Facebook App
2. Configure Messenger webhook
3. Get page access token
4. Connect via Admin panel

[Detailed Guide →](docs/SOCIAL_MEDIA_INTEGRATION.md#facebook-integration)

### Instagram
1. Link Instagram to Facebook Page
2. Configure same webhook
3. Get access token
4. Connect via Admin panel

[Detailed Guide →](docs/SOCIAL_MEDIA_INTEGRATION.md#instagram-integration)

---

## 📈 Deployment Options

### Local Development
```bash
docker-compose -f deployment/docker-compose.yml up
```

### AWS (Production)
```bash
# Backend: ECS Fargate + RDS
# Frontend: S3 + CloudFront
# See: DEPLOYMENT_GUIDE.md
```

### Manual VPS
```bash
# Ubuntu 22.04 LTS
# Docker + Docker Compose
# Nginx reverse proxy
# SSL certificate via Let's Encrypt
```

---

## 🗂 Phase Roadmap

### ✅ Phase-1a (MVP - Current)
- Facebook + Instagram integration
- Unified inbox
- Ticket management
- Agent responses
- Basic analytics
- **Timeline**: 1-2 months

### 🔜 Phase-1b (Expansion)
- X (Twitter) integration
- YouTube integration
- LinkedIn integration
- Advanced ticket assignment
- SLA monitoring
- **Timeline**: Months 3-4

### 🎯 Phase-2 (AI & Advanced Features)
- Sentiment analysis
- AI response suggestions
- Automated FAQ responses
- Duplicate detection
- Escalation workflows
- Advanced analytics & KPIs
- **Timeline**: Months 5-8

---

## 🛠 Development

### Setting up development environment
```bash
# Clone repository
git clone https://github.com/yourusername/social-media-crm.git
cd social-media-crm

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with local credentials

# Start dev server
python main.py

# Frontend setup (new terminal)
cd frontend
python -m http.server 8080
```

### Code style
```bash
# Format code
black backend/

# Lint
flake8 backend/

# Type checking
mypy backend/
```

### Environment variables
See [backend/.env.example](backend/.env.example)

---

## 📞 Support & Contributions

### Issues & Bugs
1. Check existing issues
2. Create detailed bug report
3. Include logs and steps to reproduce

### Feature Requests
1. Describe use case
2. Expected vs actual behavior
3. Suggested implementation

### Pull Requests
1. Fork repository
2. Create feature branch (`git checkout -b feature/name`)
3. Commit changes with clear messages
4. Push to branch
5. Create pull request

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🤝 Authors & Contributors

- **Built with**: FastAPI, PostgreSQL, React, Docker
- **Maintained by**: Social Media CRM Team
- **Last Updated**: November 19, 2024

---

## 🎓 Learning Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Guide](https://docs.docker.com/)
- [Facebook Graph API](https://developers.facebook.com/docs/graph-api)
- [Instagram Graph API](https://developers.instagram.com/docs/instagram-api/)

---

## ✨ Next Steps

1. **Setup Local Environment**
   - Follow "Quick Start" section
   - Configure social platform credentials

2. **Connect Social Platforms**
   - Create Facebook App
   - Create Instagram Business Account
   - Configure webhooks

3. **Test Interactions**
   - Send test messages via Facebook/Instagram
   - Verify they appear in dashboard
   - Create test tickets

4. **Deploy to Production**
   - Follow [DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)
   - Configure custom domain
   - Setup SSL/TLS

---

**Questions or issues?** Check the docs or create an issue on GitHub!
