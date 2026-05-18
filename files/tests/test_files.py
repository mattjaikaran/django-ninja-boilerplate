import json

import pytest
from django.contrib.auth import get_user_model
from ninja_jwt.tokens import RefreshToken

from core.tests.factories import UserFactory
from files.models import FileUpload
from files.schemas import ConfirmUploadSchema, GeneratePresignedUrlSchema
from files.services import FileService

User = get_user_model()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def auth_headers(user):
    refresh = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}


@pytest.fixture
def service():
    return FileService()


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFileUploadModel:
    def test_create_file_upload(self, user):
        fu = FileUpload.objects.create(
            user=user,
            key="uploads/test/uuid/file.jpg",
            filename="file.jpg",
            content_type="image/jpeg",
        )
        assert fu.filename == "file.jpg"
        assert not fu.is_confirmed
        assert str(fu) == "file.jpg"

    def test_s3_url_none_when_not_confirmed(self, user):
        fu = FileUpload.objects.create(
            user=user,
            key="uploads/test/uuid/file.jpg",
            filename="file.jpg",
            content_type="image/jpeg",
        )
        assert fu.s3_url is None

    def test_ordering_newest_first(self, user):
        from datetime import timedelta

        from django.utils import timezone

        fu1 = FileUpload.objects.create(
            user=user, key="a", filename="a.jpg", content_type="image/jpeg"
        )
        fu2 = FileUpload.objects.create(
            user=user, key="b", filename="b.jpg", content_type="image/jpeg"
        )
        FileUpload.objects.filter(id=fu1.id).update(
            created_at=timezone.now() - timedelta(hours=1)
        )
        records = list(FileUpload.objects.filter(user=user))
        assert records[0].id == fu2.id


# ---------------------------------------------------------------------------
# Service tests — generate presigned URL (local-dev fallback)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGeneratePresignedUrl:
    def test_local_dev_fallback(self, user, service):
        data = GeneratePresignedUrlSchema(
            filename="test file.jpg",
            content_type="image/jpeg",
            size=1024,
        )
        result = service.generate_presigned_upload_url(user, data)

        assert "file_id" in result
        assert "key" in result
        assert result["expires_in"] == 3600
        assert "upload_url" in result

        fu = FileUpload.objects.get(id=result["file_id"])
        assert fu.user == user
        assert not fu.is_confirmed
        assert fu.content_type == "image/jpeg"
        assert "test_file.jpg" in fu.key

    def test_filename_sanitized(self, user, service):
        data = GeneratePresignedUrlSchema(
            filename="my bad/../../../file name.pdf",
            content_type="application/pdf",
        )
        result = service.generate_presigned_upload_url(user, data)
        fu = FileUpload.objects.get(id=result["file_id"])
        assert ".." not in fu.key
        assert " " not in fu.key

    def test_custom_folder(self, user, service):
        data = GeneratePresignedUrlSchema(
            filename="avatar.png",
            content_type="image/png",
            folder="avatars",
        )
        result = service.generate_presigned_upload_url(user, data)
        assert result["key"].startswith("avatars/")


# ---------------------------------------------------------------------------
# Service tests — confirm upload
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConfirmUpload:
    def test_confirm_sets_flags(self, user, service):
        gen_data = GeneratePresignedUrlSchema(
            filename="doc.pdf", content_type="application/pdf"
        )
        gen_result = service.generate_presigned_upload_url(user, gen_data)
        file_id = gen_result["file_id"]

        confirm_data = ConfirmUploadSchema(size=5000)
        fu = service.confirm_upload(file_id, user, confirm_data)

        assert fu.is_confirmed
        assert fu.confirmed_at is not None
        assert fu.size == 5000

    def test_confirm_without_size(self, user, service):
        gen_data = GeneratePresignedUrlSchema(
            filename="doc.pdf", content_type="application/pdf"
        )
        gen_result = service.generate_presigned_upload_url(user, gen_data)
        fu = service.confirm_upload(gen_result["file_id"], user, ConfirmUploadSchema())
        assert fu.is_confirmed

    def test_confirm_wrong_user_raises(self, service):
        from django.http import Http404

        other_user = UserFactory()
        owner = UserFactory()

        gen_data = GeneratePresignedUrlSchema(
            filename="secret.jpg", content_type="image/jpeg"
        )
        gen_result = service.generate_presigned_upload_url(owner, gen_data)

        with pytest.raises(Http404):
            service.confirm_upload(gen_result["file_id"], other_user)


# ---------------------------------------------------------------------------
# Service tests — list files
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestListFiles:
    def test_list_returns_only_confirmed(self, user, service):
        gen_data = GeneratePresignedUrlSchema(
            filename="visible.jpg", content_type="image/jpeg"
        )
        gen_result = service.generate_presigned_upload_url(user, gen_data)

        service.generate_presigned_upload_url(
            user,
            GeneratePresignedUrlSchema(
                filename="hidden.jpg", content_type="image/jpeg"
            ),
        )

        service.confirm_upload(gen_result["file_id"], user, ConfirmUploadSchema())

        files = list(service.list_files(user, confirmed_only=True))
        assert len(files) == 1
        assert files[0].filename == "visible.jpg"

    def test_list_all_includes_unconfirmed(self, user, service):
        for name in ("a.jpg", "b.jpg"):
            service.generate_presigned_upload_url(
                user,
                GeneratePresignedUrlSchema(filename=name, content_type="image/jpeg"),
            )
        files = list(service.list_files(user, confirmed_only=False))
        assert len(files) == 2


# ---------------------------------------------------------------------------
# API endpoint tests — using the registered global api
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFilesAPI:
    def test_list_files_endpoint(self, api_client, auth_headers):
        response = api_client.get("/api/files/", **auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_presigned_url_endpoint(self, api_client, auth_headers):
        payload = json.dumps(
            {"filename": "photo.jpg", "content_type": "image/jpeg", "size": 2048}
        )
        response = api_client.post(
            "/api/files/presigned-url",
            data=payload,
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert "file_id" in data

    def test_confirm_upload_endpoint(self, api_client, auth_headers, user, service):
        gen_data = GeneratePresignedUrlSchema(
            filename="test.jpg", content_type="image/jpeg"
        )
        gen_result = service.generate_presigned_upload_url(user, gen_data)
        file_id = gen_result["file_id"]

        response = api_client.post(
            f"/api/files/{file_id}/confirm",
            data=json.dumps({"size": 1024}),
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("isConfirmed") is True or data.get("is_confirmed") is True
