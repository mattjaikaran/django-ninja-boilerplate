from ninja import Schema


class PasswordlessLoginRequest(Schema):
    email: str


class PasswordlessLoginVerify(Schema):
    token: str
