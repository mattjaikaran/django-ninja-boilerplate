from django.contrib import admin
from unfold.admin import ModelAdmin

from files.models import FileUpload


@admin.register(FileUpload)
class FileUploadAdmin(ModelAdmin):
    list_display = [
        "filename",
        "user",
        "content_type",
        "size",
        "is_confirmed",
        "created_at",
    ]
    list_filter = ["is_confirmed", "is_public"]
    search_fields = ["filename", "key", "user__username", "user__email"]
    readonly_fields = ["id", "created_at", "updated_at", "confirmed_at"]
