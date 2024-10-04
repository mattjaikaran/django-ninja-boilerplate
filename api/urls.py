"""
URL configuration for api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from ninja import Redoc
from ninja_extra import NinjaExtraAPI
from ninja_jwt.controller import NinjaJWTDefaultController
from core.api import UserController
from todos.api import TodoController
from debug_toolbar.toolbar import debug_toolbar_urls

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
    csrf=True,
    openapi_extra={
        "info": {
            "termsOfService": "https://example.com/terms/",
        }
    },
    version=0.1,
    title="Django Ninja Boilerplate API",
    description="API documentation for the Django Ninja Boilerplate API",
    urls_namespace="api",
)


# Register controllers
# The order of the controllers matches the order in the docs
# http://localhost:8000/api/docs
api.register_controllers(
    NinjaJWTDefaultController,  # JWT Auth
    UserController,  # User Controller
    TodoController,  # Todo Controller
)

# add the urls to the urlpatterns
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
