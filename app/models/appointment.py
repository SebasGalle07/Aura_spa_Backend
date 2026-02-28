from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_email: Mapped[str] = mapped_column(String(255), nullable=False)
    client_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id"), nullable=False)
    professional_id: Mapped[int] = mapped_column(Integer, ForeignKey("professionals.id"), nullable=False)

    date: Mapped[str] = mapped_column(String(10), nullable=False)
    time: Mapped[str] = mapped_column(String(5), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str] = mapped_column(String, nullable=False, default="")
    history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
