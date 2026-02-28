from pydantic import EmailStr, ConfigDict

from app.schemas.common import BaseSchema
from app.schemas.user import UserOut


class LoginRequest(BaseSchema):
    model_config = ConfigDict(populate_by_name=True)
    email: EmailStr
    password: str


class Token(BaseSchema):
    model_config = ConfigDict(populate_by_name=True)
    access_token: str
    token_type: str = "bearer"
    user: UserOut
