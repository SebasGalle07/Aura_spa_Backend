from app.schemas.common import BaseSchema


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
    pass


class LandingImages(BaseSchema):
    section1: str | None = None
    section2: str | None = None
    section3: str | None = None


class Branding(BaseSchema):
    sp_logo: str | None = None
    landing_images: LandingImages | None = None


class BrandingUpdate(Branding):
    pass
