import pytest
from jwt import PyJWTError as JWTError
from web.auth.jwt import create_access_token, decode_access_token


class TestJWT:
    def test_create_and_decode_token(self):
        token = create_access_token(
            user_id="123456",
            username="TestUser",
            secret="testsecret",
            expiry_hours=1,
        )
        payload = decode_access_token(token, secret="testsecret")
        assert payload["sub"] == "123456"
        assert payload["username"] == "TestUser"
        assert "exp" in payload

    def test_expired_token_raises(self):
        token = create_access_token(
            user_id="123",
            username="User",
            secret="s",
            expiry_hours=-1,  # already expired
        )
        with pytest.raises(JWTError):
            decode_access_token(token, secret="s")

    def test_invalid_secret_raises(self):
        token = create_access_token(user_id="123", username="User", secret="correct", expiry_hours=1)
        with pytest.raises(JWTError):
            decode_access_token(token, secret="wrong")

    def test_tampered_token_raises(self):
        token = create_access_token(user_id="123", username="User", secret="s", expiry_hours=1)
        # Flip a character in the payload section
        parts = token.split(".")
        parts[1] = parts[1][:-1] + ("A" if parts[1][-1] != "A" else "B")
        tampered = ".".join(parts)
        with pytest.raises(JWTError):
            decode_access_token(tampered, secret="s")
