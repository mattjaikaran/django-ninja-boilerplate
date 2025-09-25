"""Core Application
---------------
This app provides essential functionality for user management,
authentication, and base structures for the entire project.
"""

default_app_config = "core.apps.CoreConfig"

# Import models
# Import controllers
from core.controllers import AuthController, UserController
from core.models import AbstractBaseModel, OneTimePassword, User

__all__ = [
    "AbstractBaseModel",
    "AuthController",
    "OneTimePassword",
    "User",
    "UserController",
]
