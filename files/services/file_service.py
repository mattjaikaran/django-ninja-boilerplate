import logging
import re
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.http import Http404
from django.utils import timezone

from files.models import FileUpload
from files.schemas import ConfirmUploadSchema, GeneratePresignedUrlSchema

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    name = name.replace(" ", "_")
    name = re.sub(r"[^\w.\-]", "", name)
    return name or "upload"


def _s3_configured() -> bool:
    bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")
    key_id = getattr(settings, "AWS_ACCESS_KEY_ID", "")
    return bool(bucket and key_id)


class FileService:
    def generate_presigned_upload_url(
        self, user: object, data: GeneratePresignedUrlSchema
    ) -> dict:
        safe_name = sanitize_filename(data.filename)
        key = f"{data.folder}/{user.id}/{uuid4()}/{safe_name}"

        file_upload = FileUpload.objects.create(
            user=user,
            key=key,
            filename=data.filename,
            content_type=data.content_type,
            size=data.size,
            is_public=data.is_public,
            is_confirmed=False,
        )
        file_id = str(file_upload.id)

        if _s3_configured():
            import boto3

            region = getattr(settings, "AWS_S3_REGION_NAME", "us-east-1")
            bucket = settings.AWS_STORAGE_BUCKET_NAME
            client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=region,
            )

            conditions: list = [["content-type", data.content_type]]
            if data.is_public:
                conditions.append({"acl": "public-read"})

            presigned = client.generate_presigned_post(
                Bucket=bucket,
                Key=key,
                Conditions=conditions,
                ExpiresIn=3600,
            )
            return {
                "upload_url": presigned["url"],
                "upload_fields": presigned["fields"],
                "file_id": file_id,
                "key": key,
                "expires_in": 3600,
            }

        return {
            "upload_url": f"/api/files/{file_id}/local-upload",
            "upload_fields": {},
            "file_id": file_id,
            "key": key,
            "expires_in": 3600,
        }

    def confirm_upload(
        self,
        file_id: str,
        user: object,
        data: ConfirmUploadSchema | None = None,
    ) -> FileUpload:
        try:
            file_upload = FileUpload.objects.get(id=file_id, user=user)
        except FileUpload.DoesNotExist:
            raise Http404("File not found")

        file_upload.is_confirmed = True
        file_upload.confirmed_at = timezone.now()
        if data and data.size is not None:
            file_upload.size = data.size
        file_upload.save()
        return file_upload

    def generate_download_url(
        self, file_id: str, user: object, expires_in: int = 3600
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
            import boto3

            region = getattr(settings, "AWS_S3_REGION_NAME", "us-east-1")
            client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=region,
            )
            url = client.generate_presigned_url(
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

    def list_files(self, user: object, confirmed_only: bool = True):
        qs = FileUpload.objects.filter(user=user)
        if confirmed_only:
            qs = qs.filter(is_confirmed=True)
        return qs

    def delete_file(self, file_id: str, user: object) -> None:
        try:
            file_upload = FileUpload.objects.get(id=file_id, user=user)
        except FileUpload.DoesNotExist:
            raise Http404("File not found")

        if _s3_configured() and file_upload.is_confirmed:
            try:
                import boto3

                region = getattr(settings, "AWS_S3_REGION_NAME", "us-east-1")
                client = boto3.client(
                    "s3",
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=region,
                )
                client.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=file_upload.key,
                )
            except Exception:
                logger.exception("Failed to delete S3 object: %s", file_upload.key)

        file_upload.delete()

    def handle_local_upload(
        self,
        file_id: str,
        user: object,
        file_data: bytes,
        content_type: str,
    ) -> FileUpload:
        try:
            file_upload = FileUpload.objects.get(id=file_id, user=user)
        except FileUpload.DoesNotExist:
            raise Http404("File not found")

        dest_path = Path(settings.MEDIA_ROOT) / file_upload.key
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(file_data)

        file_upload.is_confirmed = True
        file_upload.confirmed_at = timezone.now()
        file_upload.size = len(file_data)
        file_upload.content_type = content_type
        file_upload.save()
        return file_upload
