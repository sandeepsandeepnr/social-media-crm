import hashlib
import hmac
import json
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DEBUG"] = "True"
os.environ["SECRET_KEY"] = "local-test-key-that-is-at-least-thirty-two-characters"
os.environ["WEBHOOK_VERIFY_TOKEN"] = "local-webhook-verify"

import httpx
import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.database import SessionLocal, init_db
from app.models import TicketInteraction
from config import settings
from main import app


@pytest.fixture
def crm():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as client:
        admin = client.post("/api/v1/auth/register", json={
            "username": "admin", "email": "admin@example.test", "password": "GoodPass123!"
        }).json()
        headers = {"Authorization": f"Bearer {admin['access_token']}"}
        platform = next(p for p in client.get("/api/v1/platforms", headers=headers).json()["data"]
                        if p["name"] == "facebook")
        accounts = []
        for number in (1, 2):
            result = client.post("/api/v1/platform-credentials", headers=headers, json={
                "platform_id": platform["id"], "business_account_id": f"page-{number}",
                "business_account_name": f"Page {number}", "access_token": f"token-{number}",
            })
            assert result.status_code == 201, result.text
            accounts.append(result.json())
        yield client, headers, accounts


def webhook(client, account, interaction, parent=None, customer="customer"):
    value = {"comment_id": interaction, "from": {"id": customer}, "message": interaction}
    if parent:
        value["parent_id"] = parent
    return client.post("/webhooks/social-media/facebook", json={
        "entry": [{"id": account, "changes": [{"field": "feed", "value": value}]}]
    })


def interaction(client, headers, content):
    rows = client.get("/api/v1/interactions", headers=headers).json()["data"]
    return next(row for row in rows if row["content"] == content)


def test_automatic_tickets_follow_only_same_account_reference(crm):
    client, headers, _ = crm
    assert webhook(client, "page-1", "first").status_code == 200
    assert webhook(client, "page-1", "followup", parent="first").status_code == 200
    assert webhook(client, "page-2", "first").status_code == 409
    assert webhook(client, "page-2", "other-account", parent="first").status_code == 200
    assert webhook(client, "page-1", "unrelated").status_code == 200
    assert webhook(client, "page-1", "followup", parent="first").status_code == 200
    first = interaction(client, headers, "first")
    assert first["ticket_id"] == interaction(client, headers, "followup")["ticket_id"]
    assert first["ticket_id"] != interaction(client, headers, "other-account")["ticket_id"]
    assert first["ticket_id"] != interaction(client, headers, "unrelated")["ticket_id"]
    assert client.get("/api/v1/tickets", headers=headers).json()["total"] == 3
    assert webhook(client, "", "missing-account").status_code == 400
    assert webhook(client, "not-connected", "unknown-account").status_code == 503


def test_account_owner_setting_and_manual_capture(crm):
    client, headers, _ = crm
    second = client.post("/api/v1/auth/register", json={
        "username": "admin2", "email": "admin2@example.test", "password": "GoodPass123!"
    }).json()
    assert client.put(f"/api/v1/users/{second['id']}", headers=headers, json={"role": "admin"}).status_code == 200
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    platform = next(p for p in client.get("/api/v1/platforms", headers=headers).json()["data"]
                    if p["name"] == "facebook")
    assert client.post("/api/v1/platform-credentials", headers=second_headers, json={
        "platform_id": platform["id"], "business_account_id": "page-3",
        "business_account_name": "Page 3", "access_token": "token-3",
    }).status_code == 201
    assert client.put("/api/v1/settings", headers=headers, json={"auto_create_tickets": False}).status_code == 200
    assert webhook(client, "page-1", "disabled").status_code == 200
    assert webhook(client, "page-3", "enabled").status_code == 200
    assert interaction(client, headers, "disabled")["ticket_id"] is None
    assert interaction(client, headers, "enabled")["ticket_id"] is not None
    manual = client.post("/api/v1/interactions", headers=headers, json={
        "platform": "facebook", "business_account_id": "page-3",
        "platform_interaction_id": "manual", "platform_user_id": "customer",
        "interaction_type": "comment", "content": "manual",
    })
    assert manual.status_code == 201, manual.text
    assert manual.json()["ticket_id"] is not None
    manual = client.post("/api/v1/interactions", headers=headers, json={
        "platform": "facebook", "business_account_id": "missing",
        "platform_interaction_id": "bad", "platform_user_id": "customer",
        "interaction_type": "comment",
    })
    assert manual.status_code == 400


def test_publish_routes_to_origin_and_rejects_ambiguous_or_inactive_accounts(crm, monkeypatch):
    client, headers, accounts = crm
    calls = []

    async def publish(self, url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, json={"id": "published"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", publish)
    assert webhook(client, "page-1", "original").status_code == 200
    row = interaction(client, headers, "original")

    def draft(ticket_id, target):
        response = client.post("/api/v1/responses", headers=headers, json={
            "ticket_id": ticket_id, "responding_to_interaction_id": target, "content": "Reply"
        })
        assert response.status_code == 201, response.text
        return response.json()["id"]

    response_id = draft(row["ticket_id"], row["id"])
    sent = client.post(f"/api/v1/responses/{response_id}/send", headers=headers)
    assert sent.status_code == 200, sent.text
    assert calls[-1][1]["headers"]["Authorization"] == "Bearer token-1"
    assert "/original/comments" in calls[-1][0]
    assert client.put(f"/api/v1/platform-credentials/{accounts[0]['id']}", headers=headers,
                      json={"is_active": False}).status_code == 200
    response_id = draft(row["ticket_id"], row["id"])
    assert client.post(f"/api/v1/responses/{response_id}/send", headers=headers).status_code == 503
    assert len(calls) == 1
    assert client.put(f"/api/v1/platform-credentials/{accounts[0]['id']}", headers=headers,
                      json={"is_active": True}).status_code == 200

    manual = client.post("/api/v1/interactions", headers=headers, json={
        "platform": "facebook", "platform_interaction_id": "legacy",
        "platform_user_id": "customer", "interaction_type": "comment", "content": "legacy",
    }).json()
    ticket = client.post("/api/v1/tickets", headers=headers,
                         json={"primary_interaction_id": manual["id"]}).json()
    response_id = draft(ticket["id"], manual["id"])
    assert client.post(f"/api/v1/responses/{response_id}/send", headers=headers).status_code == 409
    assert len(calls) == 1
    assert client.put(f"/api/v1/platform-credentials/{accounts[1]['id']}", headers=headers,
                      json={"is_active": False}).status_code == 200
    assert client.post(f"/api/v1/responses/{response_id}/send", headers=headers).status_code == 200
    assert calls[-1][1]["headers"]["Authorization"] == "Bearer token-1"
    assert client.delete(f"/api/v1/platform-credentials/{accounts[0]['id']}", headers=headers).status_code == 204
    response_id = draft(row["ticket_id"], row["id"])
    assert client.post(f"/api/v1/responses/{response_id}/send", headers=headers).status_code == 503
    platform = next(p for p in client.get("/api/v1/platforms", headers=headers).json()["data"]
                    if p["name"] == "facebook")
    assert client.post("/api/v1/platform-credentials", headers=headers, json={
        "platform_id": platform["id"], "business_account_id": "page-1",
        "business_account_name": "Reconnected", "access_token": "new-token",
    }).status_code == 201
    assert client.post(f"/api/v1/responses/{response_id}/send", headers=headers).status_code == 200
    assert calls[-1][1]["headers"]["Authorization"] == "Bearer new-token"


def test_signed_webhook_can_verify_legacy_account(crm, monkeypatch):
    client, headers, _ = crm
    manual = client.post("/api/v1/interactions", headers=headers, json={
        "platform": "facebook", "platform_interaction_id": "legacy-id",
        "platform_user_id": "customer", "interaction_type": "comment", "content": "legacy",
    })
    assert manual.status_code == 201
    invalid_claim = client.post("/api/v1/interactions", headers=headers, json={
        "platform": "facebook", "business_account_id": "page-1",
        "platform_interaction_id": "legacy-id", "platform_user_id": "customer",
        "interaction_type": "comment", "content": "legacy",
    })
    assert invalid_claim.status_code == 409
    monkeypatch.setattr(settings, "FACEBOOK_APP_SECRET", "test-app-secret")
    payload = {"entry": [{"id": "page-1", "changes": [{"field": "feed", "value": {
        "comment_id": "legacy-id", "from": {"id": "customer"}, "message": "legacy"
    }}]}]}
    body = json.dumps(payload).encode()
    signature = hmac.new(b"test-app-secret", body, hashlib.sha256).hexdigest()
    assert client.post("/webhooks/social-media/facebook", content=body,
                       headers={"X-Hub-Signature-256": "sha256=invalid"}).status_code == 401
    assert client.post("/webhooks/social-media/facebook", content=body,
                       headers={"X-Hub-Signature-256": f"sha256={signature}"}).status_code == 200
    row = interaction(client, headers, "legacy")
    assert row["ticket_id"] is not None
    with SessionLocal() as db:
        from app.models import Interaction
        stored = db.query(Interaction).filter_by(platform_interaction_id="legacy-id").one()
        assert stored.platform_metadata["business_account_id"] == "page-1"


def test_private_message_encoding_and_uncertain_delivery(crm, monkeypatch):
    client, headers, _ = crm
    payload = {"entry": [{"id": "page-1", "messaging": [
        {"sender": {"id": "customer"}, "message": {"mid": "dm-1", "text": "hello"}},
        {"sender": {"id": "page-1"}, "message": {"mid": "echo", "text": "outgoing", "is_echo": True}},
    ]}]}
    assert client.post("/webhooks/social-media/facebook", json=payload).status_code == 200
    rows = client.get("/api/v1/interactions", headers=headers).json()["data"]
    assert len(rows) == 1
    response = client.post("/api/v1/responses", headers=headers, json={
        "ticket_id": rows[0]["ticket_id"], "responding_to_interaction_id": rows[0]["id"],
        "content": "reply", "is_private_message": True,
    }).json()
    calls = []

    async def timeout(self, url, **kwargs):
        calls.append((url, kwargs))
        raise httpx.ReadTimeout("timeout", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", timeout)
    assert client.post(f"/api/v1/responses/{response['id']}/send", headers=headers).status_code == 502
    assert calls[0][1]["json"] == {
        "recipient": {"id": "customer"}, "message": {"text": "reply"}, "messaging_type": "RESPONSE"
    }
    assert calls[0][1]["headers"]["Authorization"] == "Bearer token-1"
    assert client.get(f"/api/v1/responses/{response['id']}", headers=headers).json()["status"] == "unknown"
    assert client.post(f"/api/v1/responses/{response['id']}/send", headers=headers).status_code == 409
    assert len(calls) == 1


def test_followup_to_published_reply_uses_the_same_ticket(crm, monkeypatch):
    client, headers, _ = crm

    async def publish(self, url, **kwargs):
        return httpx.Response(200, json={"id": "agent-reply"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", publish)
    assert webhook(client, "page-1", "customer-comment").status_code == 200
    first = interaction(client, headers, "customer-comment")
    draft = client.post("/api/v1/responses", headers=headers, json={
        "ticket_id": first["ticket_id"], "responding_to_interaction_id": first["id"], "content": "reply"
    }).json()
    assert client.post(f"/api/v1/responses/{draft['id']}/send", headers=headers).status_code == 200
    assert webhook(client, "page-1", "customer-reply", parent="agent-reply").status_code == 200
    assert interaction(client, headers, "customer-reply")["ticket_id"] == first["ticket_id"]


def test_unsupported_feed_changes_do_not_create_tickets(crm):
    client, headers, _ = crm
    payload = {"entry": [{"id": "page-1", "changes": [
        {"field": "feed", "value": {"item": "comment", "verb": "remove", "comment_id": "deleted",
                                     "from": {"id": "customer"}}},
        {"field": "feed", "value": {"item": "post", "verb": "add", "id": "post",
                                     "from": {"id": "customer"}}},
        {"field": "feed", "value": {"item": "comment", "verb": "add", "comment_id": "own",
                                     "from": {"id": "page-1"}}},
    ]}]}
    result = client.post("/webhooks/social-media/facebook", json=payload)
    assert result.status_code == 200
    assert result.json()["captured"] == 0
    assert client.get("/api/v1/tickets", headers=headers).json()["total"] == 0


def test_duplicate_legacy_links_block_index_migration(crm):
    client, headers, _ = crm
    assert webhook(client, "page-1", "one").status_code == 200
    assert webhook(client, "page-1", "two").status_code == 200
    index = next(i for i in TicketInteraction.__table__.indexes if i.name == "uq_ticket_interaction_single_ticket")
    index.drop(engine)
    with SessionLocal() as db:
        links = db.query(TicketInteraction).all()
        db.add(TicketInteraction(ticket_id=links[1].ticket_id, interaction_id=links[0].interaction_id, sequence_number=2))
        db.commit()
    with pytest.raises(RuntimeError, match="resolve duplicate ticket links"):
        init_db()


def test_monitoring_terms_and_literal_captured_content_search(crm):
    client, headers, _ = crm
    agent = client.post("/api/v1/auth/register", json={
        "username": "agent", "email": "agent@example.test", "password": "GoodPass123!"
    }).json()
    agent_headers = {"Authorization": f"Bearer {agent['access_token']}"}
    assert client.post("/api/v1/monitoring/terms", headers=agent_headers,
                       json={"term": "brand"}).status_code == 403
    term = client.post("/api/v1/monitoring/terms", headers=headers, json={"term": "  #Brand  "})
    assert term.status_code == 201
    assert term.json()["term"] == "#Brand"
    assert client.post("/api/v1/monitoring/terms", headers=headers,
                       json={"term": "#brand"}).status_code == 409
    assert client.post("/api/v1/monitoring/terms", headers=headers,
                       json={"term": "  "}).status_code == 422
    for interaction_id, name, content in (
        ("m1", "Customer", "A #BRAND issue is 50% off"),
        ("m2", "50% customer", "Unrelated text"),
        ("m3", "Customer", "Some 50x text"),
    ):
        assert client.post("/api/v1/interactions", headers=headers, json={
            "platform": "facebook", "platform_interaction_id": interaction_id,
            "platform_user_id": interaction_id, "customer_name": name,
            "interaction_type": "comment", "content": content,
        }).status_code == 201
    response = client.get("/api/v1/interactions", headers=agent_headers,
                          params={"content_search": "50%"})
    assert response.status_code == 200
    assert [row["content"] for row in response.json()["data"]] == ["A #BRAND issue is 50% off"]
    response = client.get("/api/v1/interactions", headers=agent_headers,
                          params={"content_search": "#brand"})
    assert response.json()["total"] == 1
    assert client.get("/api/v1/monitoring/terms", headers=agent_headers).json()["data"][0]["id"] == term.json()["id"]
    assert client.delete(f"/api/v1/monitoring/terms/{term.json()['id']}", headers=agent_headers).status_code == 403
    assert client.delete(f"/api/v1/monitoring/terms/{term.json()['id']}", headers=headers).status_code == 204
    assert client.get("/api/v1/interactions", headers=headers).json()["total"] == 3


def test_instagram_hashtag_search_and_account_verification(crm, monkeypatch):
    client, headers, _ = crm
    platform = next(p for p in client.get("/api/v1/platforms", headers=headers).json()["data"]
                    if p["name"] == "instagram")
    connected = client.post("/api/v1/platform-credentials", headers=headers, json={
        "platform_id": platform["id"], "business_account_id": "12345",
        "business_account_name": "Instagram", "access_token": "page-token",
    })
    assert connected.status_code == 201
    account_id = connected.json()["id"]
    token_url = f"/api/v1/monitoring/instagram-accounts/{account_id}/hashtag-token"
    search_url = "/api/v1/monitoring/instagram-hashtags/search"
    assert client.post(search_url, headers=headers, json={
        "credential_id": account_id, "hashtag": "#brand"
    }).status_code == 400
    assert client.put(token_url, headers=headers, json={"access_token": "user-token"}).json() == {"configured": True}
    listing = client.get("/api/v1/monitoring/instagram-accounts", headers=headers).json()
    assert listing["data"][0]["hashtag_token_configured"] is True
    assert "user-token" not in json.dumps(listing)
    calls = []

    async def get(self, url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/ig_hashtag_search"):
            result = {"data": [{"id": "456"}]}
        elif url.endswith("/456/recent_media"):
            result = {"data": [{"id": "789", "caption": "hello #brand", "permalink": "https://instagram.com/p/789"}],
                      "paging": {"next": "https://example.test/ignored"}}
        else:
            result = {"id": "12345"}
        return httpx.Response(200, json=result, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", get)
    response = client.post(search_url, headers=headers, json={"credential_id": account_id, "hashtag": "#brand"})
    assert response.status_code == 200, response.text
    assert response.json()["data"][0]["id"] == "789"
    assert response.json()["has_more"] is True
    assert len(calls) == 2
    assert calls[0][1]["params"] == {"user_id": "12345", "q": "brand"}
    assert calls[0][1]["headers"]["Authorization"] == "Bearer user-token"
    assert calls[1][1]["headers"]["Authorization"] == "Bearer user-token"
    assert client.post(search_url, headers=headers, json={"credential_id": account_id, "hashtag": "#bad tag"}).status_code == 422
    verified = client.post(f"/api/v1/monitoring/accounts/{account_id}/verify", headers=headers)
    assert verified.status_code == 200
    assert "not verified" in verified.json()["scope"]
    assert calls[-1][1]["headers"]["Authorization"] == "Bearer page-token"
    assert client.delete(f"/api/v1/platform-credentials/{account_id}", headers=headers).status_code == 204
    assert client.get("/api/v1/monitoring/instagram-accounts", headers=headers).json()["data"] == []


def test_hashtag_failures_are_explicit_and_do_not_leak_tokens(crm, monkeypatch):
    client, headers, _ = crm
    platform = next(p for p in client.get("/api/v1/platforms", headers=headers).json()["data"]
                    if p["name"] == "instagram")
    account = client.post("/api/v1/platform-credentials", headers=headers, json={
        "platform_id": platform["id"], "business_account_id": "123",
        "business_account_name": "Instagram", "access_token": "page-token",
    }).json()
    url = f"/api/v1/monitoring/instagram-accounts/{account['id']}/hashtag-token"
    assert client.put(url, headers=headers, json={"access_token": "sensitive-token"}).status_code == 200

    async def reject(self, url, **kwargs):
        return httpx.Response(429, json={"error": {"message": "sensitive-token"}}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", reject)
    result = client.post("/api/v1/monitoring/instagram-hashtags/search", headers=headers,
                         json={"credential_id": account["id"], "hashtag": "brand"})
    assert result.status_code == 502
    assert "429" in result.text
    assert "sensitive-token" not in result.text


def test_hashtag_and_credential_access_guards(crm, monkeypatch):
    client, headers, _ = crm
    agent = client.post("/api/v1/auth/register", json={
        "username": "agent", "email": "agent@example.test", "password": "GoodPass123!"
    }).json()
    agent_headers = {"Authorization": f"Bearer {agent['access_token']}"}
    assert client.get("/api/v1/monitoring/instagram-accounts", headers=agent_headers).status_code == 403
    assert client.post("/api/v1/monitoring/instagram-hashtags/search", headers=agent_headers,
                       json={"credential_id": "00000000-0000-0000-0000-000000000001",
                             "hashtag": "brand"}).status_code == 403
    platform = next(p for p in client.get("/api/v1/platforms", headers=headers).json()["data"]
                    if p["name"] == "instagram")
    monkeypatch.setattr(settings, "SECRET_KEY", "your-secret-key-change-in-production")
    login = client.post("/api/v1/auth/login", json={"email": "admin@example.test", "password": "GoodPass123!"})
    default_key_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    result = client.post("/api/v1/platform-credentials", headers=default_key_headers, json={
        "platform_id": platform["id"], "business_account_id": "123",
        "business_account_name": "Instagram", "access_token": "token",
    })
    assert result.status_code == 503
    assert "SECRET_KEY" in result.text


def test_webhook_timestamps_support_milliseconds_and_timezone_offsets(crm):
    client, headers, _ = crm
    payload = {"entry": [{"id": "page-1", "messaging": [
        {"sender": {"id": "customer"}, "timestamp": 1735689600000,
         "message": {"mid": "timestamped", "text": "millisecond message"}}
    ], "changes": [
        {"field": "feed", "value": {"comment_id": "offset", "from": {"id": "customer"},
                                     "created_time": "2025-01-01T05:30:00+05:30", "message": "offset comment"}}
    ]}]}
    assert client.post("/webhooks/social-media/facebook", json=payload).status_code == 200
    rows = client.get("/api/v1/interactions", headers=headers).json()["data"]
    assert {row["captured_at"] for row in rows} == {"2025-01-01T00:00:00"}
    payload["entry"][0]["messaging"][0]["timestamp"] = "invalid"
    assert client.post("/webhooks/social-media/facebook", json=payload).status_code == 400
