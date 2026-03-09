from pydantic import field_validator

from app.schemas.common import BaseSchema


def _validate_digits_phone(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    if not clean:
        return None
    if not clean.isdigit():
        raise ValueError("El telefono solo permite numeros.")
    return clean


class CompanyData(BaseSchema):
    business_name: str | None = None
    legal_name: str | None = None
    nit: str | None = None

    address: str | None = None
    city: str | None = None
    state: str | None = None

    phone: str | None = None
    email: str | None = None

    week_start: str | None = None
    week_end: str | None = None
    sat_start: str | None = None
    sat_end: str | None = None
    sun_start: str | None = None
    sun_end: str | None = None

    instagram: str | None = None
    facebook: str | None = None
    whatsapp: str | None = None
    welcome_msg: str | None = None


class CompanyUpdate(CompanyData):
    @field_validator("phone", "whatsapp")
    @classmethod
    def validate_phone_fields(cls, value: str | None) -> str | None:
        return _validate_digits_phone(value)


class LandingImages(BaseSchema):
    section1: str | None = None
    section2: str | None = None
    section3: str | None = None


class Branding(BaseSchema):
    sp_logo: str | None = None
    landing_images: LandingImages | None = None


class BrandingUpdate(Branding):
    pass
