from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings


class Base(DeclarativeBase):
    pass


engine_options = {"pool_pre_ping": True}
database_url = make_url(settings.DATABASE_URL)
if database_url.drivername == "postgresql":
    database_url = database_url.set(drivername="postgresql+psycopg")
elif database_url.drivername == "postgresql+psycopg2":
    database_url = database_url.set(drivername="postgresql+psycopg")
if database_url.get_backend_name() == "sqlite":
    engine_options["connect_args"] = {"check_same_thread": False}
    if settings.DATABASE_URL in {"sqlite://", "sqlite:///:memory:"}:
        engine_options["poolclass"] = StaticPool
engine = create_engine(database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    from app.models import TicketInteraction

    try:
        next(
            index
            for index in TicketInteraction.__table__.indexes
            if index.name == "uq_ticket_interaction_single_ticket"
        ).create(bind=engine, checkfirst=True)
    except IntegrityError as exc:
        raise RuntimeError(
            "Cannot enforce single-ticket interactions: resolve duplicate ticket links before restarting."
        ) from exc
    with SessionLocal() as db:
        from app.models import Platform

        defaults = (
            ("facebook", "Facebook", 63206, True),
            ("instagram", "Instagram", 2200, True),
            ("twitter", "X (Twitter)", 280, True),
            ("youtube", "YouTube", 10000, True),
            ("linkedin", "LinkedIn", 3000, True),
        )
        for name, display_name, max_length, supports_media in defaults:
            platform = db.query(Platform).filter_by(name=name).one_or_none()
            if platform is None:
                db.add(
                    Platform(
                        name=name,
                        display_name=display_name,
                        is_active=name in {"facebook", "instagram"},
                        max_message_length=max_length,
                        supports_media=supports_media,
                    )
                )
        db.commit()
