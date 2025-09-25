from ninja import Schema
from pydantic import EmailStr, validator


class UserSchema(Schema):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    username: str
    is_staff: bool = False
    is_superuser: bool = False
    date_joined: str = None

    class Config:
        from_attributes = True


class UserSignupSchema(Schema):
    first_name: str
    last_name: str
    email: EmailStr
    username: str
    password: str
    is_staff: bool = False
    is_superuser: bool = False


class UserLoginSchema(Schema):
    username: str
    password: str


class UserLogoutSchema(Schema):
    message: str


class UserUpdateSchema(Schema):
    first_name: str = None
    last_name: str = None
    email: EmailStr = None
    username: str = None

    @validator("*", pre=True)
    def empty_str_to_none(cls, v):
        if v == "":
            return None
        return v

    class Config:
        from_attributes = True


class UserDeleteSchema(Schema):
    message: str
