from ninja import Schema
from pydantic import EmailStr


class PasswordlessLoginRequest(Schema):
    email: EmailStr


class PasswordlessLoginVerify(Schema):
    token: str


class UserSignupSchema(Schema):
    username: str
    email: EmailStr
    password: str
    first_name: str
    last_name: str


class UserLoginSchema(Schema):
    username: str
    password: str
