import logging
import re
import unicodedata
from pathlib import Path
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.db.models import QuerySet
from django.http import Http404
from django.utils import timezone
from django.utils.text import get_valid_filename

from api.exceptions import ValidationError
from files.models import FileUpload
from files.schemas import ConfirmUploadSchema, GeneratePresignedUrlSchema

logger = logging.getLogger(__name__)

# Every storage key starts with "<KEY_PREFIX>/<owner id>/".
KEY_PREFIX = "users"
# Bytes read from the start of an upload to identify its type.
SNIFF_BYTES = 16
PRESIGNED_EXPIRES_IN = 3600

# Storage extension for each type that magic-byte sniffing can identify.
# A content type outside this map is never accepted.
EXTENSIONS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}


def sniff_content_type(head: bytes) -> str | None:
    """Return the content type that the leading bytes identify, if any."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def max_upload_bytes() -> int:
    return int(getattr(settings, "FILES_MAX_UPLOAD_BYTES", 10 * 1024 * 1024))


def _require_allowed_type(content_type: str) -> str:
    allowed = getattr(settings, "FILES_ALLOWED_CONTENT_TYPES", list(EXTENSIONS))
    normalized = content_type.strip().lower()
    if normalized not in EXTENSIONS or normalized not in allowed:
        raise ValidationError(
            f"Content type {content_type!r} is not allowed.",
            code="unsupported_content_type",
        )
    return normalized


def _require_size_within_limit(size: int) -> None:
    if size > max_upload_bytes():
        raise ValidationError(
            f"File exceeds the {max_upload_bytes()} byte limit.",
            code="file_too_large",
        )


def _strip_control(text: str) -> str:
    """Remove control and format characters (NUL, newlines, bidi overrides)."""
    return "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")


def sanitize_filename(filename: str) -> str:
    """Return a display-safe base name. The name never becomes a storage path."""
    name = unicodedata.normalize("NFKC", filename).replace("\\", "/")
    name = _strip_control(name.rsplit("/", 1)[-1])
    try:
        name = get_valid_filename(name).lstrip(".")
    except SuspiciousFileOperation:
        name = ""
    name = re.sub(r"[^\w.\-]", "", name)[:255]
    return name or "upload"


def _s3_configured() -> bool:
    bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")
    key_id = getattr(settings, "AWS_ACCESS_KEY_ID", "")
    return bool(bucket and key_id)


def _s3_client() -> Any:
    import boto3

    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=getattr(settings, "AWS_S3_REGION_NAME", "us-east-1"),
    )


def _verify_s3_object(file_upload: FileUpload) -> int:
    """Check the uploaded object's size, type, and magic bytes; return its size.

    Deletes the object and raises ValidationError when a check fails.
    """
    from botocore.exceptions import ClientError

    client = _s3_client()
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    try:
        head = client.head_object(Bucket=bucket, Key=file_upload.key)
    except ClientError as exc:
        raise ValidationError(
            "Uploaded object not found.", code="upload_missing"
        ) from exc

    size = int(head.get("ContentLength", 0))
    problem = ""
    if size < 1 or size > max_upload_bytes():
        problem = "Uploaded object size is not within the allowed range."
    elif head.get("ContentType", "").lower() != file_upload.content_type:
        problem = "Uploaded object content type does not match the request."
    else:
        obj = client.get_object(
            Bucket=bucket, Key=file_upload.key, Range=f"bytes=0-{SNIFF_BYTES - 1}"
        )
        if sniff_content_type(obj["Body"].read()) != file_upload.content_type:
            problem = "Uploaded object content does not match its content type."
    if problem:
        client.delete_object(Bucket=bucket, Key=file_upload.key)
        raise ValidationError(problem, code="invalid_upload")
    return size


class FileService:
    def generate_presigned_upload_url(
        self, user: Any, data: GeneratePresignedUrlSchema
    ) -> dict:
        content_type = _require_allowed_type(data.content_type)
        if data.size is not None:
            _require_size_within_limit(data.size)
        # Server-generated key under a per-owner prefix. The original name is
        # kept only as display metadata in FileUpload.filename.
        key = (
            f"{KEY_PREFIX}/{user.id}/{data.folder}/"
            f"{uuid4().hex}{EXTENSIONS[content_type]}"
        )

        file_upload = FileUpload.objects.create(
            user=user,
            key=key,
            filename=sanitize_filename(data.filename),
            # Raw client name for display only. Postgres JSON rejects NUL.
            metadata={"original_filename": _strip_control(data.filename)},
            content_type=content_type,
            size=data.size,
            is_public=data.is_public,
            is_confirmed=False,
        )
        file_id = str(file_upload.id)

        if _s3_configured():
            fields = {"Content-Type": content_type}
            conditions: list = [
                {"Content-Type": content_type},
                ["content-length-range", 1, max_upload_bytes()],
            ]
            if data.is_public:
                fields["acl"] = "public-read"
                conditions.append({"acl": "public-read"})

            presigned = _s3_client().generate_presigned_post(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=key,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=PRESIGNED_EXPIRES_IN,
            )
            return {
                "upload_url": presigned["url"],
                "upload_fields": presigned["fields"],
                "file_id": file_id,
                "key": key,
                "expires_in": PRESIGNED_EXPIRES_IN,
            }

        return {
            "upload_url": f"/api/files/{file_id}/local-upload",
            "upload_fields": {},
            "file_id": file_id,
            "key": key,
            "expires_in": PRESIGNED_EXPIRES_IN,
        }

    def confirm_upload(
        self,
        file_id: str,
        user: Any,
        data: ConfirmUploadSchema | None = None,
    ) -> FileUpload:
        try:
            file_upload = FileUpload.objects.get(id=file_id, user=user)
        except FileUpload.DoesNotExist:
            raise Http404("File not found")

        if _s3_configured():
            # Trust the stored object, not the client-reported size.
            file_upload.size = _verify_s3_object(file_upload)
        elif data and data.size is not None:
            _require_size_within_limit(data.size)
            file_upload.size = data.size
        file_upload.is_confirmed = True
        file_upload.confirmed_at = timezone.now()
        file_upload.save()
        return file_upload

    def generate_download_url(
        self, file_id: str, user: Any, expires_in: int = 3600
    ) -> dict:
        try:
            file_upload = FileUpload.objects.get(
                id=file_id, user=user, is_confirmed=True
            )
        except FileUpload.DoesNotExist:
            raise Http404("File not found")

        if file_upload.is_public and file_upload.s3_url:
            return {"download_url": file_upload.s3_url, "expires_in": 0}

        if _s3_configured():
            url = _s3_client().generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": file_upload.key,
                },
                ExpiresIn=expires_in,
            )
            return {"download_url": url, "expires_in": expires_in}

        media_url = settings.MEDIA_URL + file_upload.key
        return {"download_url": media_url, "expires_in": expires_in}

    def list_files(
        self, user: Any, confirmed_only: bool = True
    ) -> QuerySet[FileUpload]:
        qs = FileUpload.objects.filter(user=user)
        if confirmed_only:
            qs = qs.filter(is_confirmed=True)
        return qs

    def delete_file(self, file_id: str, user: Any) -> None:
        try:
            file_upload = FileUpload.objects.get(id=file_id, user=user)
        except FileUpload.DoesNotExist:
            raise Http404("File not found")

        if _s3_configured() and file_upload.is_confirmed:
            try:
                _s3_client().delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=file_upload.key,
                )
            except Exception:
                logger.exception("Failed to delete S3 object: %s", file_upload.key)

        file_upload.delete()

    def handle_local_upload(
        self,
        file_id: str,
        user: Any,
        file_data: bytes,
    ) -> FileUpload:
        """Store a local-dev upload after the size and magic-byte checks.

        The declared type from the presign step is authoritative; the
        multipart Content-Type that the client sends is ignored.
        """
        try:
            file_upload = FileUpload.objects.get(id=file_id, user=user)
        except FileUpload.DoesNotExist:
            raise Http404("File not found")

        _require_size_within_limit(len(file_data))
        if sniff_content_type(file_data[:SNIFF_BYTES]) != file_upload.content_type:
            raise ValidationError(
                "File content does not match its content type.",
                code="invalid_upload",
            )

        media_root = Path(settings.MEDIA_ROOT).resolve()
        dest_path = (media_root / file_upload.key).resolve()
        if not dest_path.is_relative_to(media_root):
            raise ValidationError("Invalid storage key.", code="invalid_upload")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(file_data)

        file_upload.is_confirmed = True
        file_upload.confirmed_at = timezone.now()
        file_upload.size = len(file_data)
        file_upload.save()
        return file_upload
