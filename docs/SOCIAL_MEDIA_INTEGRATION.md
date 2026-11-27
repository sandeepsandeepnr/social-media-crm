# Social Media Integration Guides - Phase-1a

> Historical guide: endpoint examples and rate-limit figures below have not
> been validated against current Meta APIs. Use the monitoring and Meta
> verification section in [README.md](../README.md) and current Meta
> documentation for supported behavior and permissions.

## Table of Contents
1. [Facebook Integration](#facebook-integration)
2. [Instagram Integration](#instagram-integration)
3. [Webhook Configuration](#webhook-configuration)
4. [Testing Integrations](#testing-integrations)

---

## Facebook Integration

### Prerequisites
- Facebook Business Account
- Facebook App (or create new)
- Facebook Page access
- API credentials (App ID, App Secret)

### Step 1: Create/Configure Facebook App

1. Go to [Facebook Developers](https://developers.facebook.com)
2. Navigate to "My Apps" → Create App
3. Choose "Business" type
4. Fill in app details:
   - App Name: "Social Media CRM"
   - App Contact Email: your@email.com
   - App Purpose: Customer engagement

### Step 2: Get API Credentials

1. In App Settings → Basic, copy:
   - **App ID**: Store in `.env` as `FACEBOOK_APP_ID`
   - **App Secret**: Store in `.env` as `FACEBOOK_APP_SECRET`

2. Navigate to "Products" → Add Products → "Messenger"

### Step 3: Configure Webhook

1. Go to Messenger → Settings
2. Under "Webhooks", set:
   - **Callback URL**: `https://yourdomain.com/webhooks/social-media/facebook`
   - **Verify Token**: Use value from `.env` `WEBHOOK_VERIFY_TOKEN`

3. Subscribe to webhook fields:
   - `messages`
   - `messaging_postbacks`
   - `feed` (for comments)

### Step 4: Get Page Access Token

```bash
# 1. Get a temporary user access token from:
# https://developers.facebook.com/tools/explorer/

# 2. Exchange for page access token:
curl -X GET "https://graph.facebook.com/me/accounts?access_token=USER_ACCESS_TOKEN"

# 3. Response will include page_access_token for your page
```

### Step 5: Store Credentials in CRM

Use the Admin Dashboard to connect your Facebook account:

```
POST /api/v1/platform-credentials

{
  "platform_id": "facebook_uuid",
  "business_account_id": "PAGE_ID",
  "business_account_name": "Your Business Page",
  "access_token": "PAGE_ACCESS_TOKEN",
  "scope": "pages_read_engagement,pages_manage_metadata,pages_read_user_content"
}
```

### Facebook API Endpoints Used

**Get Page Comments:**
```
GET https://graph.facebook.com/v18.0/{page-id}/feed
?fields=comments.limit(10).summary(true)
&access_token={page-access-token}
```

**Get Direct Messages:**
```
GET https://graph.facebook.com/v18.0/{page-id}/conversations
?fields=senders,message
&access_token={page-access-token}
```

**Send Reply:**
```
POST https://graph.facebook.com/v18.0/{comment-id}/private_replies
{
  "message": "Your reply message",
  "access_token": "{page-access-token}"
}
```

### Rate Limits
- Standard: 200 calls per hour
- Webhook: 1000 calls/sec per page

---

## Instagram Integration

### Prerequisites
- Instagram Business Account (linked to Facebook Page)
- Facebook App with Instagram Graph API
- API credentials

### Step 1: Link Instagram to Facebook

1. Go to [Instagram Settings](https://www.instagram.com/settings/)
2. Account → Linked accounts → Facebook
3. Link your Instagram Business Account to Facebook Page

### Step 2: Get Instagram Access

1. In Facebook App → Products → Instagram
2. Configure the same webhook as Facebook (shared)
3. Subscribe to fields:
   - `comments`
   - `messages`

### Step 3: Get Instagram Access Token

The page access token from Facebook Step 4 also works for Instagram API.

### Step 4: Store Credentials

```
POST /api/v1/platform-credentials

{
  "platform_id": "instagram_uuid",
  "business_account_id": "INSTAGRAM_BUSINESS_ACCOUNT_ID",
  "business_account_name": "Your Instagram Business",
  "access_token": "PAGE_ACCESS_TOKEN",
  "scope": "instagram_basic,instagram_manage_messages"
}
```

### Instagram API Endpoints Used

**Get Comments:**
```
GET https://graph.instagram.com/v18.0/{ig-media-id}/comments
?fields=from,text,timestamp
&access_token={access-token}
```

**Get Direct Messages:**
```
GET https://graph.instagram.com/v18.0/{ig-business-account-id}/conversations
?fields=participants,senders,latest_message
&access_token={access-token}
```

**Send Reply:**
```
POST https://graph.instagram.com/v18.0/{ig-comment-id}/replies
{
  "message": "Your reply message",
  "access_token": "{access-token}"
}
```

### Rate Limits
- Standard: 200 calls per hour
- Webhook: 1000 calls/sec

---

## Webhook Configuration

### Webhook Structure

Both Facebook and Instagram send webhooks to:
```
POST /webhooks/social-media/{platform}
```

**Example Facebook Webhook Payload:**

```json
{
  "object": "page",
  "entry": [
    {
      "id": "PAGE_ID",
      "time": 1234567890,
      "messaging": [
        {
          "sender": {
            "id": "USER_ID"
          },
          "recipient": {
            "id": "PAGE_ID"
          },
          "timestamp": 1234567890,
          "message": {
            "mid": "MID",
            "text": "Customer message here",
            "attachments": []
          }
        }
      ]
    }
  ]
}
```

**Example Instagram Comment Webhook:**

```json
{
  "object": "instagram",
  "entry": [
    {
      "id": "IG_BUSINESS_ACCOUNT_ID",
      "changes": [
        {
          "field": "comments",
          "value": {
            "from": {
              "username": "customer_username",
              "id": "COMMENTER_ID"
            },
            "text": "Great product!",
            "timestamp": 1234567890,
            "id": "COMMENT_ID"
          }
        }
      ]
    }
  ]
}
```

### Webhook Verification

When you first add a webhook, platforms send a verification request:

```
GET /webhooks/social-media/{platform}
?hub.mode=subscribe
&hub.challenge=CHALLENGE_VALUE
&hub.verify_token=VERIFY_TOKEN
```

**Expected Response:**
```
200 OK
{hub.challenge}
```

### Testing Webhooks Locally

For local development without exposing your machine to the internet:

1. **Use ngrok** (creates public URL tunneling to localhost):
```bash
ngrok http 8000
```

2. Configure webhook callback URL:
```
https://xyz.ngrok.io/webhooks/social-media/facebook
```

3. Test webhook with curl:
```bash
curl -X POST http://localhost:8000/webhooks/social-media/facebook \
  -H "Content-Type: application/json" \
  -d '{
    "object": "page",
    "entry": [{
      "messaging": [{
        "sender": {"id": "123"},
        "message": {"text": "Test message"}
      }]
    }]
  }'
```

---

## Testing Integrations

### Test Platform Connection

```bash
# 1. Add platform credentials via UI or API
# 2. Check sync status

curl -X GET http://localhost:8000/api/v1/platform-credentials \
  -H "Authorization: Bearer {token}"

# Should show:
# "sync_status": "active"
# "last_sync_at": recent timestamp
```

### Test Webhook Receiver

```bash
# Send test interaction via webhook
curl -X POST http://localhost:8000/webhooks/social-media/facebook \
  -H "Content-Type: application/json" \
  -d '{
    "object": "page",
    "entry": [{
      "messaging": [{
        "sender": {"id": "test_user_123"},
        "timestamp": '$(date +%s)',
        "message": {"text": "Test customer message"}
      }]
    }]
  }'

# Check if interaction was created
curl -X GET "http://localhost:8000/api/v1/interactions" \
  -H "Authorization: Bearer {token}"
```

### Test API Response

```bash
# 1. Get a ticket
curl -X GET "http://localhost:8000/api/v1/tickets?limit=1" \
  -H "Authorization: Bearer {token}"

# 2. Send a response
curl -X POST "http://localhost:8000/api/v1/responses" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "ticket_uuid",
    "responding_to_interaction_id": "interaction_uuid",
    "content": "Thank you for your message!",
    "is_private_message": false
  }'

# 3. Publish response
curl -X POST "http://localhost:8000/api/v1/responses/{response_id}/send" \
  -H "Authorization: Bearer {token}"
```

### Common Issues & Solutions

**Issue: Webhook not receiving events**
- ✅ Check webhook URL is publicly accessible
- ✅ Verify VERIFY_TOKEN matches configuration
- ✅ Ensure app has required permissions
- ✅ Check Firebase/Server logs for 403/401 errors

**Issue: "Invalid access token"**
- ✅ Verify token hasn't expired
- ✅ Regenerate access token from Facebook/Instagram
- ✅ Check app permissions are correct

**Issue: "Rate limit exceeded"**
- ✅ Wait before retrying (exponential backoff)
- ✅ Upgrade to higher API tier (requires business review)
- ✅ Optimize batch queries

---

## Next Phase Integrations

For Phase-1b, add:
- **X (Twitter)** API v2
- **YouTube** Data API
- **LinkedIn** API

Each follows similar pattern:
1. Create app credentials
2. Configure webhook endpoints
3. Store credentials in CRM
4. Implement integration service layer
