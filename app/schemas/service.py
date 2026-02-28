from app.schemas.common import BaseSchema


class ServiceBase(BaseSchema):
    name: str
    category: str
    duration: int
    price: int
    active: bool = True
    image: str | None = None


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseSchema):
    name: str | None = None
    category: str | None = None
    duration: int | None = None
    price: int | None = None
    active: bool | None = None
    image: str | None = None


class ServiceOut(ServiceBase):
    id: int
