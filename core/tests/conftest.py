import pytest
from ninja_jwt.tokens import RefreshToken


@pytest.fixture
def auth_token(test_user):
    """Get JWT token for test user"""
    refresh = RefreshToken.for_user(test_user)
    return str(refresh.access_token)


@pytest.fixture
def auth_headers(auth_token):
    """Get headers with JWT token"""
    return {"HTTP_AUTHORIZATION": f"Bearer {auth_token}"}
