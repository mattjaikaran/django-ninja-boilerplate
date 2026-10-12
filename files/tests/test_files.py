import io
import json
import re

import pytest
from django.contrib.auth import get_user_model
from ninja_jwt.tokens import RefreshToken

from api.exceptions import ValidationError
from core.tests.factories import UserFactory
from files.models import FileUpload
from files.schemas import ConfirmUploadSchema, GeneratePresignedUrlSchema
from files.services import FileService, file_service

User = get_user_model()

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


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
# Service tests — generate presigned URL (local-dev fallback)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGeneratePresignedUrl:
    def test_custom_folder(self, user, service):
        data = GeneratePresignedUrlSchema(
            filename="avatar.png",
            content_type="image/png",
            folder="avatars",
        )
        result = service.generate_presigned_upload_url(user, data)
        assert result["key"].startswith(f"users/{user.id}/avatars/")


# ---------------------------------------------------------------------------
# Service tests — confirm upload
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConfirmUpload:
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
        assert "fileId" in data

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


# ---------------------------------------------------------------------------
# Upload validation — size, content type, magic bytes, filenames
# ---------------------------------------------------------------------------


def _presign(service: FileService, user: object, **overrides: object) -> FileUpload:
    fields = {"filename": "pic.png", "content_type": "image/png", **overrides}
    result = service.generate_presigned_upload_url(
        user, GeneratePresignedUrlSchema(**fields)
    )
    return FileUpload.objects.get(id=result["file_id"])


class _FakeS3:
    def __init__(self, size: int, content_type: str, head: bytes) -> None:
        self._head = {"ContentLength": size, "ContentType": content_type}
        self._body = head
        self.deleted: list[str] = []

    def head_object(self, Bucket: str, Key: str) -> dict:
        return self._head

    def get_object(self, Bucket: str, Key: str, Range: str) -> dict:
        return {"Body": io.BytesIO(self._body)}

    def delete_object(self, Bucket: str, Key: str) -> None:
        self.deleted.append(Key)


@pytest.mark.django_db
class TestUploadValidation:
    def test_rejects_content_type_outside_allow_list(self, user, service):
        with pytest.raises(ValidationError):
            _presign(service, user, filename="x.html", content_type="text/html")

    def test_rejects_declared_size_over_limit(self, user, service, settings):
        settings.FILES_MAX_UPLOAD_BYTES = 100
        with pytest.raises(ValidationError):
            _presign(service, user, size=101)

    @pytest.mark.parametrize(
        "filename",
        [
            "../../etc/passwd.png",
            "..\\..\\windows\\evil.png",
            "/var/www/static/x.png",
            "a\x00b\nc.png",
            "..",
        ],
    )
    def test_traversal_filename_never_reaches_storage_key(
        self, user, service, filename
    ):
        fu = _presign(service, user, filename=filename)

        prefix, owner, folder, name = fu.key.split("/")
        assert (prefix, owner, folder) == ("users", str(user.id), "uploads")
        assert re.fullmatch(r"[0-9a-f]{32}\.png", name)
        assert not re.search(r"[/\\\x00-\x1f]", fu.filename)
        assert not fu.filename.startswith(".")
        assert fu.metadata["original_filename"] == re.sub(r"[\x00-\x1f]", "", filename)

    def test_local_upload_rejects_oversize_file(
        self, user, service, settings, temp_media
    ):
        settings.FILES_MAX_UPLOAD_BYTES = 16
        fu = _presign(service, user)
        with pytest.raises(ValidationError):
            service.handle_local_upload(str(fu.id), user, PNG_BYTES)
        assert not list(temp_media.rglob("*.png"))

    @pytest.mark.parametrize(
        "data",
        [b"<html><script>alert(1)</script></html>", b"\xff\xd8\xff\xe0jpeg-data"],
    )
    def test_local_upload_rejects_mismatched_magic_bytes(
        self, user, service, temp_media, data
    ):
        fu = _presign(service, user)  # declared image/png
        with pytest.raises(ValidationError):
            service.handle_local_upload(str(fu.id), user, data)
        fu.refresh_from_db()
        assert not fu.is_confirmed
        assert not list(temp_media.rglob("*.png"))

    def test_local_upload_stores_valid_file_under_media_root(
        self, user, service, temp_media
    ):
        fu = service.handle_local_upload(
            str(_presign(service, user).id), user, PNG_BYTES
        )
        assert (temp_media / fu.key).read_bytes() == PNG_BYTES
        assert fu.is_confirmed
        assert fu.size == len(PNG_BYTES)

    @pytest.mark.parametrize(
        ("size", "content_type", "head"),
        [
            (10 * 1024 * 1024 + 1, "image/png", PNG_BYTES),
            (len(PNG_BYTES), "text/html", PNG_BYTES),
            (len(PNG_BYTES), "image/png", b"<html>not a png</html>"),
        ],
    )
    def test_s3_confirm_rejects_and_deletes_invalid_object(
        self, user, service, monkeypatch, settings, size, content_type, head
    ):
        fu = _presign(service, user)
        fake = _FakeS3(size, content_type, head)
        settings.AWS_STORAGE_BUCKET_NAME = "bucket"
        monkeypatch.setattr(file_service, "_s3_configured", lambda: True)
        monkeypatch.setattr(file_service, "_s3_client", lambda: fake)

        with pytest.raises(ValidationError):
            service.confirm_upload(str(fu.id), user, ConfirmUploadSchema(size=1))

        assert fake.deleted == [fu.key]
        fu.refresh_from_db()
        assert not fu.is_confirmed

    def test_s3_confirm_records_stored_size_not_client_size(
        self, user, service, monkeypatch, settings
    ):
        fu = _presign(service, user)
        fake = _FakeS3(len(PNG_BYTES), "image/png", PNG_BYTES[:16])
        settings.AWS_STORAGE_BUCKET_NAME = "bucket"
        monkeypatch.setattr(file_service, "_s3_configured", lambda: True)
        monkeypatch.setattr(file_service, "_s3_client", lambda: fake)

        confirmed = service.confirm_upload(
            str(fu.id), user, ConfirmUploadSchema(size=1)
        )

        assert confirmed.is_confirmed
        assert confirmed.size == len(PNG_BYTES)
        assert fake.deleted == []
