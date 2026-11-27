# Social Media CRM - Phase-1a API Specifications

## Base URL
```
http://localhost:8000/api/v1
```

## Local Development Behavior

- The first account registered on a new local database becomes the administrator. Further public registrations are always agents; the submitted `role` cannot grant elevated access.
- The backend uses SQLite by default for local development. Set `DATABASE_URL` in `backend/.env` to a PostgreSQL connection string when running against a local PostgreSQL instance.
- Platform access tokens are encrypted before storage and are never included in credential responses.
- Publishing a response requires an active Facebook or Instagram account with the appropriate platform permissions. Without a real connected account, drafts can be created and edited, but publishing returns an explicit error.
- Webhook GET verification uses `WEBHOOK_VERIFY_TOKEN`. POST signatures are checked with `FACEBOOK_APP_SECRET` when configured; unsigned webhooks are accepted only in development mode.

---

## 1. AUTHENTICATION ENDPOINTS

### 1.1 User Registration
**POST** `/auth/register`
```json
Request:
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "SecurePassword123!",
  "first_name": "John",
  "last_name": "Doe",
  "role": "agent"
}

Response (201):
{
  "id": "uuid",
  "username": "john_doe",
  "email": "john@example.com",
  "role": "agent",
  "created_at": "2024-11-19T22:00:00Z",
  "token": "jwt_token"
}
```

### 1.2 User Login
**POST** `/auth/login`
```json
Request:
{
  "email": "john@example.com",
  "password": "SecurePassword123!"
}

Response (200):
{
  "token": "jwt_token",
  "user": {
    "id": "uuid",
    "username": "john_doe",
    "email": "john@example.com",
    "role": "agent"
  }
}
```

### 1.3 Token Refresh
**POST** `/auth/refresh`
```json
Request:
{
  "refresh_token": "refresh_token"
}

Response (200):
{
  "token": "new_jwt_token"
}
```

### 1.4 Logout
**POST** `/auth/logout`
```
Headers: Authorization: Bearer {token}

Response (200):
{
  "message": "Logged out successfully"
}
```

---

## 2. USER MANAGEMENT ENDPOINTS (Admin Only)

### 2.1 Get All Users
**GET** `/users?role=agent&limit=10&offset=0`
```
Headers: Authorization: Bearer {token}

Response (200):
{
  "data": [
    {
      "id": "uuid",
      "username": "john_doe",
      "email": "john@example.com",
      "role": "agent",
      "is_active": true,
      "created_at": "2024-11-19T22:00:00Z"
    }
  ],
  "total": 50,
  "limit": 10,
  "offset": 0
}
```

### 2.2 Get User by ID
**GET** `/users/{user_id}`
```
Headers: Authorization: Bearer {token}

Response (200):
{
  "id": "uuid",
  "username": "john_doe",
  "email": "john@example.com",
  "role": "agent",
  "first_name": "John",
  "last_name": "Doe",
  "is_active": true,
  "timezone": "UTC",
  "created_at": "2024-11-19T22:00:00Z"
}
```

### 2.3 Update User
**PUT** `/users/{user_id}`
```json
Request:
{
  "first_name": "John",
  "last_name": "Doe",
  "timezone": "UTC",
  "is_active": true
}

Response (200): Updated user object
```

### 2.4 Delete User
**DELETE** `/users/{user_id}`
```
Response (204): No Content
```

---

## 3. PLATFORM INTEGRATION ENDPOINTS (Admin Only)

### 3.1 Get Available Platforms
**GET** `/platforms`
```
Response (200):
{
  "data": [
    {
      "id": "uuid",
      "name": "facebook",
      "display_name": "Facebook",
      "is_active": true,
      "supports_media": true,
      "max_message_length": 63206
    },
    {
      "id": "uuid",
      "name": "instagram",
      "display_name": "Instagram",
      "is_active": true,
      "supports_media": true,
      "max_message_length": 2200
    }
  ]
}
```

### 3.2 Connect Platform Account
**POST** `/platform-credentials`
```json
Request:
{
  "platform_id": "uuid",
  "business_account_id": "facebook_page_id_123",
  "business_account_name": "My Business Page",
  "access_token": "EAAxxxxxxxxxx",
  "scope": "pages_read_engagement,pages_manage_metadata"
}

Response (201):
{
  "id": "uuid",
  "platform_id": "uuid",
  "business_account_id": "facebook_page_id_123",
  "business_account_name": "My Business Page",
  "is_active": true,
  "sync_status": "active",
  "last_sync_at": null,
  "created_at": "2024-11-19T22:00:00Z"
}
```

### 3.3 Get Platform Credentials
**GET** `/platform-credentials?platform=facebook`
```
Headers: Authorization: Bearer {token}

Response (200):
{
  "data": [
    {
      "id": "uuid",
      "platform": "facebook",
      "business_account_name": "My Business Page",
      "is_active": true,
      "sync_status": "active",
      "last_sync_at": "2024-11-19T22:00:00Z"
    }
  ]
}
```

### 3.4 Update Platform Credentials
**PUT** `/platform-credentials/{credential_id}`
```json
Request:
{
  "access_token": "new_EAAxxxxxxxxxx",
  "is_active": true
}

Response (200): Updated credential object
```

### 3.5 Disconnect Platform
**DELETE** `/platform-credentials/{credential_id}`
```
Response (204): No Content
```

---

## 4. INTERACTIONS ENDPOINTS

### 4.1 Get All Interactions (Unified Inbox)
**GET** `/interactions?status=unprocessed&limit=20&sort=created_at&order=desc`
```
Headers: Authorization: Bearer {token}

Response (200):
{
  "data": [
    {
      "id": "uuid",
      "platform": "facebook",
      "customer_name": "Jane Smith",
      "customer_avatar": "https://...",
      "interaction_type": "comment",
      "content": "Great product! When can I get it?",
      "post_url": "https://facebook.com/...",
      "captured_at": "2024-11-19T22:00:00Z",
      "ticket_id": "uuid or null",
      "is_public": true
    }
  ],
  "total": 150,
  "unprocessed_count": 45
}
```

### 4.2 Get Interaction Details
**GET** `/interactions/{interaction_id}`
```
Headers: Authorization: Bearer {token}

Response (200):
{
  "id": "uuid",
  "platform": "facebook",
  "customer": {
    "id": "uuid",
    "name": "Jane Smith",
    "avatar": "https://...",
    "follower_count": 500
  },
  "interaction_type": "comment",
  "content": "Great product! When can I get it?",
  "media_urls": [],
  "post_url": "https://facebook.com/...",
  "conversation_thread": [
    {
      "id": "uuid",
      "type": "customer",
      "content": "Great product!",
      "timestamp": "2024-11-19T22:00:00Z"
    }
  ],
  "captured_at": "2024-11-19T22:00:00Z",
  "ticket": {
    "id": "uuid",
    "ticket_number": "TKT-001",
    "status": "open"
  }
}
```

### 4.3 Mark Interaction as Processed
**PATCH** `/interactions/{interaction_id}`
```json
Request:
{
  "is_processed": true
}

Response (200): Updated interaction object
```

### 4.4 Webhook Receiver for Real-time Interactions
**POST** `/webhooks/social-media/{platform}`
```json
Request (from Facebook/Instagram webhook):
{
  "entry": [{
    "changes": [{
      "value": {
        "from": {
          "name": "Jane Smith",
          "id": "123456"
        },
        "message": "Great product!",
        "post_id": "pos_123",
        "created_time": 1234567890
      }
    }]
  }]
}

Response (200):
{
  "status": "received"
}
```

---

## 5. TICKETS ENDPOINTS

### 5.1 Get All Tickets
**GET** `/tickets?status=open&platform=facebook&limit=20&sort=opened_at&order=desc`
```
Headers: Authorization: Bearer {token}

Response (200):
{
  "data": [
    {
      "id": "uuid",
      "ticket_number": "TKT-001",
      "customer_name": "Jane Smith",
      "platform": "facebook",
      "subject": "Product inquiry",
      "status": "open",
      "priority": "medium",
      "assigned_to": "john_doe",
      "opened_at": "2024-11-19T22:00:00Z",
      "first_response_at": null,
      "response_time_minutes": null
    }
  ],
  "total": 150,
  "by_status": {
    "open": 45,
    "in_progress": 30,
    "pending": 15,
    "resolved": 50,
    "closed": 10
  }
}
```

### 5.2 Get Ticket Details
**GET** `/tickets/{ticket_id}`
```
Headers: Authorization: Bearer {token}

Response (200):
{
  "id": "uuid",
  "ticket_number": "TKT-001",
  "customer": {
    "id": "uuid",
    "name": "Jane Smith",
    "avatar": "https://...",
    "follower_count": 500
  },
  "platform": "facebook",
  "subject": "Product inquiry",
  "description": "Customer asking about product availability",
  "status": "open",
  "priority": "medium",
  "assigned_to": {
    "id": "uuid",
    "username": "john_doe",
    "name": "John Doe"
  },
  "tags": ["product", "inquiry"],
  "conversation": [
    {
      "id": "uuid",
      "type": "customer",
      "content": "Great product! When can I get it?",
      "timestamp": "2024-11-19T22:00:00Z",
      "platform_url": "https://facebook.com/..."
    },
    {
      "id": "uuid",
      "type": "agent",
      "content": "Thank you for your interest!",
      "timestamp": "2024-11-19T22:05:00Z",
      "sent_at": "2024-11-19T22:05:00Z"
    }
  ],
  "opened_at": "2024-11-19T22:00:00Z",
  "first_response_at": "2024-11-19T22:05:00Z",
  "resolved_at": null,
  "internal_notes": "Customer is high-value client",
  "created_at": "2024-11-19T22:00:00Z"
}
```

### 5.3 Create Ticket (Auto-create from Interaction)
**POST** `/tickets`
```json
Request:
{
  "primary_interaction_id": "uuid",
  "subject": "Product inquiry",
  "priority": "medium"
}

Response (201):
{
  "id": "uuid",
  "ticket_number": "TKT-001",
  "status": "open",
  "created_at": "2024-11-19T22:00:00Z"
}
```

### 5.4 Update Ticket
**PUT** `/tickets/{ticket_id}`
```json
Request:
{
  "status": "in_progress",
  "priority": "high",
  "assigned_to_agent_id": "uuid",
  "internal_notes": "Customer is high-value",
  "tags": ["product", "urgent"]
}

Response (200): Updated ticket object
```

### 5.5 Resolve Ticket
**PUT** `/tickets/{ticket_id}/resolve`
```json
Request:
{
  "resolution_summary": "Product availability confirmed for next week"
}

Response (200):
{
  "id": "uuid",
  "status": "resolved",
  "resolved_at": "2024-11-19T22:30:00Z",
  "resolution_summary": "Product availability confirmed for next week"
}
```

### 5.6 Link Interaction to Ticket
**POST** `/tickets/{ticket_id}/interactions`
```json
Request:
{
  "interaction_id": "uuid"
}

Response (201): Link created successfully
```

---

## 6. RESPONSE MANAGEMENT ENDPOINTS

### 6.1 Draft Response
**POST** `/responses`
```json
Request:
{
  "ticket_id": "uuid",
  "responding_to_interaction_id": "uuid",
  "content": "Thank you for your interest! Our product will be available next week.",
  "is_private_message": false
}

Response (201):
{
  "id": "uuid",
  "ticket_id": "uuid",
  "status": "draft",
  "content": "Thank you for your interest!",
  "created_at": "2024-11-19T22:00:00Z"
}
```

### 6.2 Get Draft Response
**GET** `/responses/{response_id}`
```
Headers: Authorization: Bearer {token}

Response (200):
{
  "id": "uuid",
  "ticket_id": "uuid",
  "content": "Thank you for your interest!",
  "status": "draft",
  "platform": "facebook",
  "character_count": 42,
  "max_characters": 63206,
  "created_at": "2024-11-19T22:00:00Z"
}
```

### 6.3 Update Draft Response
**PUT** `/responses/{response_id}`
```json
Request:
{
  "content": "Thank you for your interest! Our product will be available next week."
}

Response (200): Updated response object
```

### 6.4 Send Response to Social Platform
**POST** `/responses/{response_id}/send`
```json
Request:
{}

Response (200):
{
  "id": "uuid",
  "status": "published",
  "platform_post_id": "cmt_123456",
  "sent_at": "2024-11-19T22:05:00Z"
}
```

### 6.5 Get Response History for Ticket
**GET** `/tickets/{ticket_id}/responses`
```
Headers: Authorization: Bearer {token}

Response (200):
{
  "data": [
    {
      "id": "uuid",
      "content": "Thank you for your interest!",
      "status": "published",
      "agent": "john_doe",
      "sent_at": "2024-11-19T22:05:00Z"
    }
  ]
}
```

---

## 7. DASHBOARD & ANALYTICS ENDPOINTS

### 7.1 Get Dashboard Metrics
**GET** `/dashboard/metrics`
```
Headers: Authorization: Bearer {token}

Response (200):
{
  "total_interactions_today": 45,
  "unprocessed_interactions": 12,
  "open_tickets": 30,
  "avg_first_response_time_minutes": 15,
  "tickets_by_status": {
    "open": 30,
    "in_progress": 20,
    "pending": 10,
    "resolved": 50,
    "closed": 10
  },
  "tickets_by_platform": {
    "facebook": 60,
    "instagram": 50
  },
  "agent_workload": [
    {
      "agent": "john_doe",
      "open_tickets": 8,
      "unresponded": 2
    }
  ]
}
```

### 7.2 Get Platform Statistics
**GET** `/analytics/platforms?date_from=2024-11-01&date_to=2024-11-19`
```
Headers: Authorization: Bearer {token}

Response (200):
{
  "data": [
    {
      "platform": "facebook",
      "total_interactions": 150,
      "total_tickets": 100,
      "avg_response_time_minutes": 15,
      "avg_resolution_time_minutes": 240
    },
    {
      "platform": "instagram",
      "total_interactions": 120,
      "total_tickets": 80,
      "avg_response_time_minutes": 20,
      "avg_resolution_time_minutes": 300
    }
  ]
}
```

---

## 8. CUSTOMER PROFILE ENDPOINTS

### 8.1 Get Customer Profile
**GET** `/customers/{customer_id}`
```
Headers: Authorization: Bearer {token}

Response (200):
{
  "id": "uuid",
  "name": "Jane Smith",
  "platform": "facebook",
  "platform_user_id": "123456",
  "avatar": "https://...",
  "follower_count": 500,
  "is_verified": false,
  "first_interaction_at": "2024-11-15T10:00:00Z",
  "last_interaction_at": "2024-11-19T22:00:00Z",
  "total_interactions": 5,
  "open_tickets": 1,
  "sentiment_summary": {
    "positive": 3,
    "neutral": 1,
    "negative": 1
  },
  "interaction_history": [
    {
      "id": "uuid",
      "type": "comment",
      "content": "Great product!",
      "timestamp": "2024-11-19T22:00:00Z"
    }
  ]
}
```

---

## 9. SYSTEM SETTINGS (Admin Only)

### 9.1 Get Settings
**GET** `/settings`
```
Headers: Authorization: Bearer {token}

Response (200):
{
  "data": {
    "platform_sync_interval_minutes": 5,
    "auto_create_tickets": true,
    "ticket_auto_assign": true,
    "require_response_approval": false
  }
}
```

### 9.2 Update Settings
**PUT** `/settings`
```json
Request:
{
  "platform_sync_interval_minutes": 10,
  "auto_create_tickets": true
}

Response (200): Updated settings object
```

---

## ERROR RESPONSES

### 400 Bad Request
```json
{
  "error": "Invalid request",
  "details": "Field 'email' is required"
}
```

### 401 Unauthorized
```json
{
  "error": "Unauthorized",
  "details": "Invalid or missing token"
}
```

### 403 Forbidden
```json
{
  "error": "Forbidden",
  "details": "You don't have permission to access this resource"
}
```

### 404 Not Found
```json
{
  "error": "Not found",
  "details": "Resource not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error",
  "details": "An unexpected error occurred"
}
```

---

## AUTHENTICATION HEADER

All endpoints (except `/auth/register` and `/auth/login`) require:
```
Authorization: Bearer {jwt_token}
```

---

## PAGINATION

Supported on list endpoints:
```
?limit=20&offset=0
?limit=50&offset=50
```

Default limit: 20, Max limit: 100

---

## SORTING & FILTERING

**Sorting:**
```
?sort=created_at&order=desc
?sort=opened_at&order=asc
```

**Filtering:**
```
?status=open
?platform=facebook
?priority=high
?assigned_to={user_id}
```

---

## RATE LIMITING

- 1000 requests per hour per API key
- 10 requests per second burst limit

Response headers:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1234567890
```
