import logging

from ninja import File, UploadedFile
from ninja_extra import api_controller, http_delete, http_get, http_post
from ninja_jwt.authentication import JWTAuth

from files.schemas import (
    ConfirmUploadSchema,
    DownloadUrlResponseSchema,
    FileUploadSchema,
    GeneratePresignedUrlSchema,
    PresignedUrlResponseSchema,
)
from files.services import FileService

logger = logging.getLogger(__name__)

_FILE_REQUIRED = File(...)  # module-level to satisfy B008 (no function call in default)


@api_controller("/files", tags=["Files"], auth=JWTAuth())
class FileController:
    def __init__(self) -> None:
        self.service = FileService()

    @http_get("/", response={200: list[FileUploadSchema]})
    def list_files(self, request):
        files = self.service.list_files(request.user)
        return 200, list(files)

    @http_post("/presigned-url", response={201: PresignedUrlResponseSchema})
    def generate_presigned_url(self, request, payload: GeneratePresignedUrlSchema):
        result = self.service.generate_presigned_upload_url(request.user, payload)
        return 201, result

    @http_post("/{file_id}/confirm", response={200: FileUploadSchema})
    def confirm_upload(self, request, file_id: str, payload: ConfirmUploadSchema):
        file_upload = self.service.confirm_upload(file_id, request.user, payload)
        return 200, file_upload

    @http_get("/{file_id}/download-url", response={200: DownloadUrlResponseSchema})
    def get_download_url(self, request, file_id: str, expires_in: int = 3600):
        result = self.service.generate_download_url(file_id, request.user, expires_in)
        return 200, result

    @http_post("/{file_id}/local-upload", response={200: FileUploadSchema})
    def local_upload(
        self,
        request,
        file_id: str,
        file: UploadedFile = _FILE_REQUIRED,
    ):
        file_data = file.read()
        content_type = file.content_type or "application/octet-stream"
        file_upload = self.service.handle_local_upload(
            file_id, request.user, file_data, content_type
        )
        return 200, file_upload

    @http_delete("/{file_id}", response={204: None})
    def delete_file(self, request, file_id: str):
        self.service.delete_file(file_id, request.user)
        return 204, None
