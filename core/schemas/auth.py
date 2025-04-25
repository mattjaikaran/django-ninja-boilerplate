from ninja import Schema
from pydantic import EmailStr


class PasswordlessLoginRequest(Schema):
    email: EmailStr


class PasswordlessLoginVerify(Schema):
    email: EmailStr
    token: str
