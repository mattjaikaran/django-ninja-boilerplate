"""Legacy user schemas — kept for backwards compatibility only.

These schemas use an integer ``id`` and minimal fields. New code should
import from ``core.schemas.user_schema`` (or the ``core.schemas`` package)
which provides the full ``UserSchema`` with UUID primary key and extended
profile fields.
"""

from ninja import Schema


class UserSchema(Schema):
    """Minimal legacy user read schema with integer primary key.

    Attributes:
        id: Integer primary key (legacy; new schema uses UUID).
        username: The user's unique username.
        email: The user's email address.
        first_name: The user's given name.
        last_name: The user's family name.
    """

    id: int
    username: str
    email: str
    first_name: str
    last_name: str


class UserSignupSchema(Schema):
    """Legacy schema for user registration payloads.

    Attributes:
        username: Desired username.
        email: User's email address.
        password: Plain-text password (hashed before storage).
        first_name: User's given name.
        last_name: User's family name.
    """

    username: str
    email: str
    password: str
    first_name: str
    last_name: str


class UserLoginSchema(Schema):
    """Legacy schema for username/password login payloads.

    Attributes:
        username: The user's username.
        password: The user's plain-text password.
    """

    username: str
    password: str


class UserLogoutSchema(Schema):
    """Legacy schema for logout response.

    Attributes:
        message: Human-readable confirmation message.
    """

    message: str


class UserUpdateSchema(Schema):
    """Legacy schema for user profile update payloads.

    All fields are required in this legacy schema; prefer the
    ``UserUpdateSchema`` in ``core.schemas.user_schema`` which makes
    all fields optional for partial updates.

    Attributes:
        username: New username.
        email: New email address.
        first_name: New given name.
        last_name: New family name.
    """

    username: str
    email: str
    first_name: str
    last_name: str


class UserDeleteSchema(Schema):
    """Legacy schema for user deletion response.

    Attributes:
        message: Human-readable confirmation message.
    """

    message: str
