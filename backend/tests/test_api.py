import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DEBUG"] = "True"
os.environ["CORS_ORIGINS"] = '["http://localhost:8080"]'
os.environ["SECRET_KEY"] = "local-test-key-that-is-at-least-thirty-two-characters"
os.environ["WEBHOOK_VERIFY_TOKEN"] = "local-webhook-verify"

from fastapi.testclient import TestClient

from app.database import Base, engine
from main import app


def test_local_phase_one_api_flow():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as client:
        invalid_registration = client.post(
            "/api/v1/auth/register",
            json={"username": "bad", "email": "not-an-email", "password": "short"},
        )
        assert invalid_registration.status_code == 422
        assert invalid_registration.json()["error"] == "VALIDATION_ERROR"

        registration = client.post(
            "/api/v1/auth/register",
            json={
                "username": "firstadmin",
                "email": "admin@example.test",
                "password": "GoodPass123!",
                "role": "agent",
            },
        )
        assert registration.status_code == 201, registration.text
        admin_data = registration.json()
        assert admin_data["role"] == "admin"
        admin_token = admin_data["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        agent_registration = client.post(
            "/api/v1/auth/register",
            json={
                "username": "agentone",
                "email": "agent@example.test",
                "password": "AgentPass123!",
            },
        )
        assert agent_registration.status_code == 201, agent_registration.text
        agent_headers = {
            "Authorization": f"Bearer {agent_registration.json()['access_token']}"
        }
        assert client.get("/api/v1/users", headers=agent_headers).status_code == 403
        assert client.get("/api/v1/settings", headers=agent_headers).status_code == 403
        assert (
            client.get("/api/v1/users/me", headers=agent_headers).json()["username"]
            == "agentone"
        )
        updated_user = client.put(
            f"/api/v1/users/{agent_registration.json()['id']}",
            headers=admin_headers,
            json={"first_name": "Updated"},
        )
        assert updated_user.status_code == 200
        assert updated_user.json()["first_name"] == "Updated"
        self_demotion = client.put(
            f"/api/v1/users/{admin_data['id']}",
            headers=admin_headers,
            json={"role": "agent"},
        )
        assert self_demotion.status_code == 400

        platforms = client.get("/api/v1/platforms", headers=agent_headers)
        assert platforms.status_code == 200
        facebook = next(
            row for row in platforms.json()["data"] if row["name"] == "facebook"
        )

        connected = client.post(
            "/api/v1/platform-credentials",
            headers=admin_headers,
            json={
                "platform_id": facebook["id"],
                "business_account_id": "page-1",
                "business_account_name": "Test Page",
                "access_token": "do-not-return-or-store-plaintext",
            },
        )
        assert connected.status_code == 201, connected.text
        assert "access_token" not in connected.json()
        credential_id = connected.json()["id"]
        listed_credentials = client.get(
            "/api/v1/platform-credentials", headers=admin_headers
        )
        assert listed_credentials.status_code == 200
        assert "access_token" not in listed_credentials.json()["data"][0]
        paused_credential = client.put(
            f"/api/v1/platform-credentials/{credential_id}",
            headers=admin_headers,
            json={"is_active": False},
        )
        assert paused_credential.status_code == 200
        assert paused_credential.json()["sync_status"] == "paused"
        resumed_credential = client.put(
            f"/api/v1/platform-credentials/{credential_id}",
            headers=admin_headers,
            json={"is_active": True},
        )
        assert resumed_credential.status_code == 200
        assert resumed_credential.json()["sync_status"] == "active"

        interaction_response = client.post(
            "/api/v1/interactions",
            headers=agent_headers,
            json={
                "platform": "facebook",
                "platform_interaction_id": "comment-1",
                "platform_user_id": "customer-1",
                "customer_name": "Jane",
                "interaction_type": "comment",
                "content": "Can you help me?",
            },
        )
        assert interaction_response.status_code == 201, interaction_response.text
        interaction_id = interaction_response.json()["id"]
        filtered_interactions = client.get(
            "/api/v1/interactions?status=unprocessed&search=help&platform=facebook",
            headers=agent_headers,
        )
        assert filtered_interactions.status_code == 200
        assert filtered_interactions.json()["total"] == 1

        ticket_response = client.post(
            "/api/v1/tickets",
            headers=agent_headers,
            json={
                "primary_interaction_id": interaction_id,
                "subject": "Product question",
            },
        )
        assert ticket_response.status_code == 201, ticket_response.text
        ticket_id = ticket_response.json()["id"]
        ticket_update = client.put(
            f"/api/v1/tickets/{ticket_id}",
            headers=agent_headers,
            json={"priority": "high", "status": "in_progress", "tags": ["question"]},
        )
        assert ticket_update.status_code == 200, ticket_update.text
        assert ticket_update.json()["priority"] == "high"
        assert ticket_update.json()["status"] == "in_progress"
        ticket_detail = client.get(
            f"/api/v1/tickets/{ticket_id}", headers=agent_headers
        )
        assert ticket_detail.status_code == 200
        assert ticket_detail.json()["conversation"][0]["content"] == "Can you help me?"

        draft = client.post(
            "/api/v1/responses",
            headers=agent_headers,
            json={"ticket_id": ticket_id, "content": "Thanks for reaching out!"},
        )
        assert draft.status_code == 201, draft.text
        assert draft.json()["status"] == "draft"
        updated_draft = client.put(
            f"/api/v1/responses/{draft.json()['id']}",
            headers=agent_headers,
            json={"content": "Thanks for reaching out. We will help."},
        )
        assert updated_draft.status_code == 200, updated_draft.text
        ticket_responses = client.get(
            f"/api/v1/tickets/{ticket_id}/responses", headers=agent_headers
        )
        assert (
            ticket_responses.json()["data"][0]["content"]
            == "Thanks for reaching out. We will help."
        )

        customer_id = interaction_response.json()["id"]
        interaction_details = client.get(
            f"/api/v1/interactions/{customer_id}", headers=agent_headers
        )
        assert interaction_details.status_code == 200
        actual_customer_id = interaction_details.json()["customer"]["id"]
        customers = client.get("/api/v1/customers", headers=agent_headers)
        assert customers.status_code == 200
        assert customers.json()["data"][0]["total_interactions"] == 1
        assert (
            client.get(
                f"/api/v1/customers/{actual_customer_id}", headers=agent_headers
            ).status_code
            == 200
        )

        assert (
            client.get("/api/v1/dashboard/metrics", headers=agent_headers).status_code
            == 200
        )
        assert (
            client.get(
                "/api/v1/analytics/platforms?date_from=2026-01-01&date_to=2026-12-31",
                headers=agent_headers,
            ).status_code
            == 200
        )
        updated_settings = client.put(
            "/api/v1/settings",
            headers=admin_headers,
            json={"auto_create_tickets": False, "platform_sync_interval_minutes": 10},
        )
        assert updated_settings.status_code == 200, updated_settings.text
        assert updated_settings.json()["data"]["auto_create_tickets"] is False
        assert client.get("/api/v1/users", headers=admin_headers).json()["total"] == 2

        webhook = client.post(
            "/webhooks/social-media/facebook",
            json={
                "entry": [
                    {
                        "id": "page-1",
                        "changes": [
                            {
                                "field": "feed",
                                "value": {
                                    "comment_id": "comment-from-webhook",
                                    "from": {
                                        "id": "customer-2",
                                        "name": "Webhook User",
                                    },
                                    "message": "A webhook comment",
                                },
                            }
                        ],
                    }
                ]
            },
        )
        assert webhook.status_code == 200, webhook.text
        assert webhook.json()["captured"] == 1
        verification = client.get(
            "/webhooks/social-media/facebook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "local-webhook-verify",
                "hub.challenge": "12345",
            },
        )
        assert verification.status_code == 200
        assert verification.text == "12345"

        schema = client.get("/api/openapi.json").json()
        required_paths = {
            "/api/v1/auth/register",
            "/api/v1/users/{user_id}",
            "/api/v1/platform-credentials",
            "/api/v1/interactions",
            "/api/v1/tickets/{ticket_id}/resolve",
            "/api/v1/responses/{response_id}/send",
            "/api/v1/customers/{customer_id}",
            "/api/v1/dashboard/metrics",
            "/api/v1/analytics/platforms",
            "/api/v1/settings",
            "/webhooks/social-media/{platform}",
        }
        assert required_paths.issubset(schema["paths"])

        refresh = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": admin_data["refresh_token"]},
        )
        assert refresh.status_code == 200, refresh.text
        replay = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": admin_data["refresh_token"]},
        )
        assert replay.status_code == 401
        logout = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {refresh.json()['access_token']}"},
            json={"refresh_token": refresh.json()["refresh_token"]},
        )
        assert logout.status_code == 200, logout.text
        assert (
            client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {refresh.json()['access_token']}"},
            ).status_code
            == 401
        )
        logged_out_refresh = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh.json()["refresh_token"]},
        )
        assert logged_out_refresh.status_code == 401
