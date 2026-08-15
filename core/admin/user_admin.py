from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

User = get_user_model()


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    list_display = ["username", "email", "is_staff", "id"]
    search_fields = ["username", "email"]
    list_filter = ["is_staff"]

    # The custom User model sets date_joined (auto_now_add) and updated_at
    # (auto_now) to non-editable, and Django 5.2's base UserAdmin no longer
    # declares readonly_fields. Declare both explicitly or the change form
    # raises "cannot be specified ... non-editable field".
    readonly_fields = ["last_login", "date_joined", "updated_at"]

    fieldsets = (
        (None, {"fields": ("username", "email", "password")}),
        (
            _("Profile"),
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "avatar",
                    "bio",
                    "phone",
                    "location",
                    "website",
                    "timezone",
                )
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "is_verified",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            _("Preferences"),
            {"fields": ("email_notifications", "push_notifications", "metadata")},
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined", "updated_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "password1", "password2"),
            },
        ),
        (_("Profile"), {"fields": ("first_name", "last_name")}),
    )
