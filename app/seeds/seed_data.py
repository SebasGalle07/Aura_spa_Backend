from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models import CompanyData, Professional, Service, User


def seed_data(db):
    users_seed = [
        {
            "email": "admin@auraspa.com",
            "password": "admin123",
            "role": "admin",
            "name": "Administrador",
            "phone": "3001112233",
            "created_at": "2024-01-15",
        },
        {
            "email": "cliente@email.com",
            "password": "cliente123",
            "role": "client",
            "name": "Cliente Demo",
            "phone": "3009998877",
            "created_at": "2024-03-20",
        },
        {
            "email": "valentina@auraspa.com",
            "password": "valentina123",
            "role": "professional",
            "name": "Valentina Torres",
            "phone": "3115556677",
            "created_at": "2024-02-10",
        },
    ]

    for u in users_seed:
        existing = db.scalar(select(User).where(User.email == u["email"]))
        if existing:
            continue
        db.add(
            User(
                email=u["email"],
                hashed_password=get_password_hash(u["password"]),
                role=u["role"],
                name=u["name"],
                phone=u["phone"],
                email_verified=True,
                created_at=u["created_at"],
            )
        )

    services_seed = [
        {"name": "Masaje Relajante", "category": "Masajes", "duration": 60, "price": 120000, "active": True, "image": None},
        {"name": "Masaje Descontracturante", "category": "Masajes", "duration": 90, "price": 160000, "active": True, "image": None},
        {"name": "Manicure Clasico", "category": "Manicure", "duration": 45, "price": 35000, "active": True, "image": None},
        {"name": "Pedicure Spa", "category": "Pedicure", "duration": 60, "price": 55000, "active": True, "image": None},
        {"name": "Depilacion Piernas", "category": "Depilacion", "duration": 45, "price": 70000, "active": True, "image": None},
        {"name": "Facial Hidratante", "category": "Facial", "duration": 60, "price": 95000, "active": True, "image": None},
    ]

    for s in services_seed:
        existing = db.scalar(select(Service).where(Service.name == s["name"]))
        if existing:
            continue
        db.add(Service(**s))

    professionals_seed = [
        {"name": "Valentina Torres", "specialty": "Masajes y Facial", "schedule_start": "08:00", "schedule_end": "17:00", "active": True},
        {"name": "Camila Ruiz", "specialty": "Manicure y Pedicure", "schedule_start": "09:00", "schedule_end": "18:00", "active": True},
        {"name": "Laura Gomez", "specialty": "Depilacion", "schedule_start": "10:00", "schedule_end": "19:00", "active": True},
    ]

    for p in professionals_seed:
        existing = db.scalar(select(Professional).where(Professional.name == p["name"]))
        if existing:
            continue
        db.add(Professional(**p))

    company = db.scalar(select(CompanyData).limit(1))
    if not company:
        db.add(
            CompanyData(
                business_name="Aura Spa",
                legal_name="Aura Spa S.A.S",
                nit="9999999999-9",
                address="Cra. 14 #21-35\nCentro, Armenia, Quindio, Colombia",
                phone="+57 300 593 9785",
                email="elizabeth.mayao@uqvirtual.edu.co",
                city="Armenia",
                state="Quindio",
                week_start="09:00",
                week_end="20:00",
                sat_start="09:00",
                sat_end="18:00",
                sun_start="10:00",
                sun_end="17:00",
                instagram=None,
                facebook=None,
                whatsapp=None,
                welcome_msg="Bienvenido a Aura Spa",
                sp_logo=None,
                landing_section1=None,
                landing_section2=None,
                landing_section3=None,
            )
        )

    db.commit()


def seed_data_if_needed():
    db = SessionLocal()
    try:
        seed_data(db)
    except Exception as exc:
        db.rollback()
        print(f"Seed skipped: {exc}")
    finally:
        db.close()
