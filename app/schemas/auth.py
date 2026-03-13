from pydantic import ConfigDict, EmailStr

from app.schemas.common import BaseSchema
from app.schemas.user import UserOut


class LoginRequest(BaseSchema):
    model_config = ConfigDict(populate_by_name=True)
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseSchema):
    model_config = ConfigDict(populate_by_name=True)
    id_token: str


class Token(BaseSchema):
    model_config = ConfigDict(populate_by_name=True)
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserOut


class RegisterResponse(BaseSchema):
    ok: bool = True
    email_verification_required: bool = True


class RefreshRequest(BaseSchema):
    refresh_token: str


class ForgotPasswordRequest(BaseSchema):
    email: EmailStr


class ForgotPasswordResponse(BaseSchema):
    ok: bool = True
    reset_token: str | None = None


class ResetPasswordRequest(BaseSchema):
    token: str
    new_password: str


class ResendVerificationRequest(BaseSchema):
    email: EmailStr


class VerifyEmailRequest(BaseSchema):
    token: str


class VerifyEmailResponse(BaseSchema):
    ok: bool = True
