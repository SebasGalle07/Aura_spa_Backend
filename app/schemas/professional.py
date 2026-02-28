from app.schemas.common import BaseSchema


class ProfessionalBase(BaseSchema):
    name: str
    specialty: str
    schedule_start: str
    schedule_end: str
    active: bool = True


class ProfessionalCreate(ProfessionalBase):
    pass


class ProfessionalUpdate(BaseSchema):
    name: str | None = None
    specialty: str | None = None
    schedule_start: str | None = None
    schedule_end: str | None = None
    active: bool | None = None


class ProfessionalOut(ProfessionalBase):
    id: int
