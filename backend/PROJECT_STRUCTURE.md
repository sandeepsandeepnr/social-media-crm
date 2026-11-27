# Social Media CRM Backend - Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app initialization
│   ├── config.py               # Configuration management
│   ├── constants.py            # App constants
│   │
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── platform.py
│   │   ├── user.py
│   │   ├── customer.py
│   │   ├── interaction.py
│   │   ├── ticket.py
│   │   └── response.py
│   │
│   ├── schemas/                # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── platform.py
│   │   ├── interaction.py
│   │   ├── ticket.py
│   │   ├── customer.py
│   │   └── response.py
│   │
│   ├── api/                    # API route handlers
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── platforms.py
│   │   ├── interactions.py
│   │   ├── tickets.py
│   │   ├── responses.py
│   │   ├── customers.py
│   │   ├── dashboard.py
│   │   ├── webhooks.py
│   │   └── settings.py
│   │
│   ├── services/               # Business logic layer
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── platform_service.py
│   │   ├── interaction_service.py
│   │   ├── ticket_service.py
│   │   ├── response_service.py
│   │   ├── customer_service.py
│   │   └── webhook_service.py
│   │
│   ├── integrations/           # External platform integrations
│   │   ├── __init__.py
│   │   ├── base_integration.py
│   │   ├── facebook_integration.py
│   │   └── instagram_integration.py
│   │
│   ├── middleware/             # Custom middleware
│   │   ├── __init__.py
│   │   ├── auth_middleware.py
│   │   └── logging_middleware.py
│   │
│   ├── utils/                  # Utility functions
│   │   ├── __init__.py
│   │   ├── auth_utils.py
│   │   ├── validators.py
│   │   ├── decorators.py
│   │   └── exceptions.py
│   │
│   ├── database/               # Database configuration
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   └── session.py
│   │
│   └── migrations/             # Alembic migrations
│       └── versions/
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_interactions.py
│   ├── test_tickets.py
│   └── test_responses.py
│
├── .env.example                # Environment variables template
├── .env                        # Environment variables (DO NOT COMMIT)
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container configuration
├── docker-compose.yml          # Docker Compose for local dev
├── main.py                     # Entry point
└── README.md                   # Project documentation
```
