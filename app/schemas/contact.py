from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


class ContactMessageIn(BaseSchema):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    message: str = Field(min_length=5, max_length=2000)


class ContactMessageOut(BaseSchema):
    ok: bool = True
