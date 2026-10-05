"""Verify pagination on registered user and audit list endpoints."""

from typing import cast

import pytest
from django.contrib.auth.models import AbstractBaseUser
from django.test import Client
from ninja_jwt.tokens import AccessToken

from core.audit.models import AuditAction, AuditLog
from core.tests.factories import UserFactory


@pytest.mark.django_db
class TestAdminListPagination:
    def test_users_list_has_page_envelope_and_distinct_pages(self):
        staff = UserFactory(is_staff=True)
        users = UserFactory.create_batch(3)
        token = AccessToken.for_user(cast("AbstractBaseUser", staff))
        client = Client(HTTP_COOKIE=f"access_token={token}")

        first = client.get("/api/users/?page_size=2")
        second = client.get("/api/users/?page_size=2&page=2")
        assert first.status_code == second.status_code == 200
        first_body, second_body = first.json(), second.json()
        assert set(first_body) == {"count", "next", "previous", "results"}
        assert first_body["count"] == second_body["count"] == 4
        assert len(first_body["results"]) == len(second_body["results"]) == 2
        assert first_body["next"] is not None
        assert second_body["previous"] is not None
        assert {item["id"] for item in first_body["results"]}.isdisjoint(
            item["id"] for item in second_body["results"]
        )
        assert {
            item["id"] for item in first_body["results"] + second_body["results"]
        } == {str(user.id) for user in [staff, *users]}

    @pytest.mark.parametrize(
        ("path", "staff_only"),
        [("/api/users/staff", True), ("/api/users/active", False)],
    )
    def test_filtered_user_lists_paginate(self, path, staff_only):
        staff = UserFactory(is_staff=True)
        UserFactory.create_batch(2, is_staff=staff_only)
        UserFactory(is_active=False, is_staff=False)
        token = AccessToken.for_user(cast("AbstractBaseUser", staff))
        client = Client(HTTP_COOKIE=f"access_token={token}")

        first = client.get(f"{path}?page_size=2")
        second = client.get(f"{path}?page_size=2&page=2")
        assert first.status_code == second.status_code == 200
        first_body, second_body = first.json(), second.json()
        assert first_body["count"] == second_body["count"] == 3
        assert len(first_body["results"]) == 2
        assert len(second_body["results"]) == 1
        assert first_body["next"] is not None
        assert second_body["previous"] is not None
        assert {item["id"] for item in first_body["results"]}.isdisjoint(
            item["id"] for item in second_body["results"]
        )

    def test_audit_list_has_page_envelope_and_distinct_pages(self):
        staff = UserFactory(is_staff=True)
        logs = [
            AuditLog.objects.create(action=AuditAction.CUSTOM, user=staff)
            for _ in range(3)
        ]
        token = AccessToken.for_user(cast("AbstractBaseUser", staff))
        client = Client(HTTP_COOKIE=f"access_token={token}")

        first = client.get("/api/audit/?action=CUSTOM&page_size=2")
        second = client.get("/api/audit/?action=CUSTOM&page_size=2&page=2")
        assert first.status_code == second.status_code == 200
        first_body, second_body = first.json(), second.json()
        assert set(first_body) == {"count", "next", "previous", "results"}
        assert first_body["count"] == second_body["count"] == 3
        assert len(first_body["results"]) == 2
        assert len(second_body["results"]) == 1
        assert first_body["next"] is not None
        assert second_body["previous"] is not None
        assert {
            item["id"] for item in first_body["results"] + second_body["results"]
        } == {str(log.id) for log in logs}
