from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from ninja_extra import NinjaExtraAPI
from ninja_jwt.controller import NinjaJWTDefaultController
from core.api import UserController
from todos.api import TodoController
from ninja import Redoc
from debug_toolbar.toolbar import debug_toolbar_urls

# admin site settings
admin.site.site_header = "Django Ninja Boilerplate Admin"
admin.site.site_title = "Django Ninja Boilerplate Panel"
admin.site.index_title = "Welcome to Django Ninja Boilerplate Panel"
admin.site.site_url = "/api/docs"

# Instantiate the server
"""
normally for django-ninja it looks like - 
api = NinjaAPI()

ninja extra normally looks like -
api = NinjaExtraAPI()

Below we are adding in Swagger/OpenAPI params
seen at http://localhost:8000/api/docs
"""

api = NinjaExtraAPI(
    # csrf=True,  # this line is to enable CSRF protection
    openapi_extra={
        "info": {
            "termsOfService": "https://example.com/terms/",
        }
    },
    version=0.1,
    title="Django Ninja Boilerplate API",
    description="API documentation for the Django Ninja Boilerplate API",
    urls_namespace="boilerplate_api",
    # docs=Redoc(),  # this line is to use ReDoc instead of Swagger
)


# Register controllers
# The order of the controllers matches the order in the API Docs (Swager or ReDoc)
# http://localhost:8000/api/docs
api.register_controllers(
    NinjaJWTDefaultController,  # JWT Auth. If you want to use JWT, you must include this https://github.com/eadwinCode/django-ninja-jwt
    # core app
    UserController,  # User Controller
    # todos app
    TodoController,  # Todo Controller
    # Add more controllers here
)

# add the urls to the urlpatterns
urlpatterns = [
    path("admin/", admin.site.urls),
    # this includes all of the endpoints defined in the controllers (api.register_controllers)
    # and adds a /api prefix to the urls
    path("api/", api.urls),
] + debug_toolbar_urls()  # this is for the debug toolbar.

# this is for the static files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
