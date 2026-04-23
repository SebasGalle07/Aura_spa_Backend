"""Unit tests for account reactivation (re-registration after cancellation)."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_unit.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only-32chars")
os.environ.setdefault("GROQ_API_KEY", "")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.core.security import get_password_hash, verify_password
from app.crud.user import create_user, get_user_by_email
from app.models.user import User
from app.schemas.user import UserRegister


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine("sqlite:///./test_reactivation.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db(test_engine):
    Session = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    session = Session()
    yield session
    session.rollback()
    session.close()


def _make_user(db, email="test@example.com", name="Test User", phone="3001234567", active=True):
    user = User(
        email=email,
        hashed_password=get_password_hash("OldPass1!"),
        role="client",
        name=name,
        phone=phone,
        email_verified=True,
        is_active=active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Active user — cannot re-register (duplicate email)
# ---------------------------------------------------------------------------

def test_active_user_email_already_exists(db):
    user = _make_user(db, email="active@example.com")
    existing = get_user_by_email(db, "active@example.com")
    assert existing is not None
    assert existing.is_active is True
    # An active, verified user means registration should be rejected
    assert existing.email_verified is True


# ---------------------------------------------------------------------------
# Inactive user — can be reactivated with new credentials
# ---------------------------------------------------------------------------

def test_reactivate_inactive_account(db):
    user = _make_user(db, email="inactive@example.com", active=False)
    user.email_verified = True
    user.deactivated_at = None
    db.add(user)
    db.commit()

    existing = get_user_by_email(db, "inactive@example.com")
    assert existing is not None
    assert existing.is_active is False

    # Simulate reactivation logic from auth.py
    existing.hashed_password = get_password_hash("NewPass1!")
    existing.name = "New Name"
    existing.phone = "3009876543"
    existing.is_active = True
    existing.deactivated_at = None
    existing.email_verified = False
    db.add(existing)
    db.commit()
    db.refresh(existing)

    assert existing.is_active is True
    assert existing.email_verified is False
    assert existing.name == "New Name"
    assert verify_password("NewPass1!", existing.hashed_password) is True
    assert verify_password("OldPass1!", existing.hashed_password) is False


def test_reactivated_user_old_password_rejected(db):
    user = _make_user(db, email="pwcheck@example.com", active=False)
    existing = get_user_by_email(db, "pwcheck@example.com")

    new_hashed = get_password_hash("BrandNew99!")
    existing.hashed_password = new_hashed
    existing.is_active = True
    db.add(existing)
    db.commit()

    assert verify_password("OldPass1!", existing.hashed_password) is False
    assert verify_password("BrandNew99!", existing.hashed_password) is True


# ---------------------------------------------------------------------------
# Newly created user has expected defaults
# ---------------------------------------------------------------------------

def test_create_user_defaults(db):
    reg = UserRegister(email="fresh@example.com", password="Fresh1234!", name="Fresh User", phone="3001234567")
    user = create_user(db, reg, role="client", email_verified=False)

    assert user.id is not None
    assert user.email == "fresh@example.com"
    assert user.role == "client"
    assert user.is_active is True
    assert user.email_verified is False


# ---------------------------------------------------------------------------
# Deactivated user is_active flag
# ---------------------------------------------------------------------------

def test_deactivated_user_is_inactive(db):
    user = _make_user(db, email="deactivate@example.com")
    from app.core.time import utc_now
    user.is_active = False
    user.deactivated_at = utc_now()
    db.add(user)
    db.commit()

    reloaded = get_user_by_email(db, "deactivate@example.com")
    assert reloaded.is_active is False
    assert reloaded.deactivated_at is not None
