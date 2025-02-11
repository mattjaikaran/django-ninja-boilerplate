from ninja import Schema


class UserSchema(Schema):
    id: int
    username: str
    email: str
    first_name: str
    last_name: str


class UserSignupSchema(Schema):
    username: str
    email: str
    password: str
    first_name: str
    last_name: str


class UserLoginSchema(Schema):
    username: str
    password: str


class UserLogoutSchema(Schema):
    message: str


class UserUpdateSchema(Schema):
    username: str
    email: str
    first_name: str
    last_name: str


class UserDeleteSchema(Schema):
    message: str
