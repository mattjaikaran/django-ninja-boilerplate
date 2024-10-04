from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from ninja_extra.testing import TestClient

from api.urls import api  # Import NinjaExtraAPI instance


User = get_user_model()

user_data = {
    "email": "test@gmail.com",
    "username": "test",
    "first_name": "Test",
    "last_name": "User",
    "password": "testpassword123",
}


class UserControllerTest(TestCase):
    def setUp(self):
        self.client = TestClient(api)
        self.user_data = user_data
