"""
Core Application
---------------
This app provides essential functionality for user management,
authentication, and base structures for the entire project.
"""

default_app_config = "core.apps.CoreConfig"

# Import models
from core.models import User, AbstractBaseModel, OneTimePassword

# Import controllers
from core.controllers import AuthController, UserController

__all__ = [
    "User",
    "AbstractBaseModel",
    "OneTimePassword",
    "AuthController",
    "UserController",
]
