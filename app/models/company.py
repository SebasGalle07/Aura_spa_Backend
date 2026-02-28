from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CompanyData(Base):
    __tablename__ = "company_data"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nit: Mapped[str | None] = mapped_column(String(50), nullable=True)

    address: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)

    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    week_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    week_end: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sat_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sat_end: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sun_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sun_end: Mapped[str | None] = mapped_column(String(10), nullable=True)

    instagram: Mapped[str | None] = mapped_column(String(255), nullable=True)
    facebook: Mapped[str | None] = mapped_column(String(255), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(50), nullable=True)
    welcome_msg: Mapped[str | None] = mapped_column(String, nullable=True)

    sp_logo: Mapped[str | None] = mapped_column(String, nullable=True)
    landing_section1: Mapped[str | None] = mapped_column(String, nullable=True)
    landing_section2: Mapped[str | None] = mapped_column(String, nullable=True)
    landing_section3: Mapped[str | None] = mapped_column(String, nullable=True)
