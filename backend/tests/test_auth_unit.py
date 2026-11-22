import pytest
import pytest_asyncio
from datetime import timedelta

from services.async_auth_service import async_auth_service
from schemas import UserCreate


class TestAsyncAuthService:
    """Unit tests for AsyncAuthService"""

    def test_password_hashing(self):
        password = "test_password_123"
        hashed = async_auth_service.get_password_hash(password)

        assert hashed is not None
        assert hashed != password
        assert async_auth_service.verify_password(password, hashed) is True
        assert async_auth_service.verify_password("wrong_password", hashed) is False

    def test_jwt_token_creation_and_verification(self):
        token, jti, _expires_at = async_auth_service.create_access_token("testuser", "123")
        assert token
        payload = async_auth_service.verify_token(token)
        assert payload["sub"] == "testuser"
        assert payload["user_id"] == "123"
        assert payload["jti"] == jti

        invalid_payload = async_auth_service.verify_token("invalid_token")
        assert invalid_payload is None

    @pytest_asyncio.fixture
    async def test_user_in_db(self, test_db):
        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            full_name="Test User"
        )
        user = await async_auth_service.create_user(test_db, user_data)
        return user

    @pytest.mark.asyncio
    async def test_register_and_login_user_async(self, test_db, sample_user_data):
        user_data = UserCreate(**sample_user_data)
        token_response, refresh_token, expires_in = await async_auth_service.register_user(test_db, user_data)
        assert token_response.access_token
        assert refresh_token
        assert expires_in > 0

    @pytest.mark.asyncio
    async def test_authenticate_user_async(self, test_db, test_user_in_db):
        user = await async_auth_service.authenticate_user(test_db, "test@example.com", "testpass123")
        assert user is not None

    @pytest.mark.asyncio
    async def test_expired_auth_tokens_have_ttl_indexes(self, test_db, monkeypatch):
        from database import init_db

        monkeypatch.setattr("database.get_database", lambda: test_db)
        await init_db()

        for collection in (
            test_db.refresh_tokens,
            test_db.email_verification_tokens,
            test_db.password_reset_tokens,
        ):
            info = await collection.index_information()
            assert any(spec.get("expireAfterSeconds") == 0 for spec in info.values())

    @pytest.mark.asyncio
    async def test_registration_never_grants_admin(self, test_db, sample_user_data, sample_user_data_2):
        first = await async_auth_service.create_user(test_db, UserCreate(**sample_user_data))
        second = await async_auth_service.create_user(test_db, UserCreate(**sample_user_data_2))
        assert first["is_admin"] is False
        assert second["is_admin"] is False


def _production_settings(**overrides):
    from config import Settings

    values = {
        "_env_file": None,
        "ENVIRONMENT": "production",
        "DEBUG": False,
        "COOKIE_SECURE": True,
        "ALLOWED_ORIGINS": "https://app.example.com",
        "GROQ_API_KEY": "test-groq-key",
        "JWT_SECRET_KEY": "a" * 48,
    }
    values.update(overrides)
    return Settings(**values)


class TestProductionSettings:
    def test_production_settings_accept_a_complete_config(self):
        settings = _production_settings()
        assert settings.is_production is True
        assert settings.allowed_origin_list == ["https://app.example.com"]

    def test_production_rejects_placeholder_jwt(self):
        with pytest.raises(ValueError, match="placeholder"):
            _production_settings(JWT_SECRET_KEY="change-me-in-production")

    def test_production_rejects_debug_and_insecure_cookies(self):
        with pytest.raises(ValueError, match="DEBUG must be false"):
            _production_settings(DEBUG=True)
        with pytest.raises(ValueError, match="COOKIE_SECURE"):
            _production_settings(COOKIE_SECURE=False)

    def test_production_rejects_wildcard_origins(self):
        with pytest.raises(ValueError, match="ALLOWED_ORIGINS"):
            _production_settings(ALLOWED_ORIGINS="")
        with pytest.raises(ValueError, match="\\*"):
            _production_settings(ALLOWED_ORIGINS="*")
