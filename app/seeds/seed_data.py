from datetime import date, timedelta
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.core.security import get_password_hash
from app.models import User, Service, Professional, Appointment, CompanyData


def seed_data(db):
    users_seed = [
        {
            "id": 1,
            "email": "admin@auraspa.com",
            "password": "admin123",
            "role": "admin",
            "name": "Administrador",
            "phone": "3001112233",
            "created_at": "2024-01-15",
        },
        {
            "id": 2,
            "email": "cliente@email.com",
            "password": "cliente123",
            "role": "client",
            "name": "Cliente Demo",
            "phone": "3009998877",
            "created_at": "2024-03-20",
        },
        {
            "id": 3,
            "email": "valentina@auraspa.com",
            "password": "val123",
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
                id=u["id"],
                email=u["email"],
                hashed_password=get_password_hash(u["password"]),
                role=u["role"],
                name=u["name"],
                phone=u["phone"],
                created_at=u["created_at"],
            )
        )

    services_seed = [
        {"id": 1, "name": "Masaje Relajante", "category": "Masajes", "duration": 60, "price": 120000, "active": True, "image": None},
        {"id": 2, "name": "Masaje Descontracturante", "category": "Masajes", "duration": 90, "price": 160000, "active": True, "image": None},
        {"id": 3, "name": "Manicure Clásico", "category": "Manicure", "duration": 45, "price": 35000, "active": True, "image": None},
        {"id": 4, "name": "Pedicure Spa", "category": "Pedicure", "duration": 60, "price": 55000, "active": True, "image": None},
        {"id": 5, "name": "Depilación Piernas", "category": "Depilación", "duration": 45, "price": 70000, "active": True, "image": None},
        {"id": 6, "name": "Facial Hidratante", "category": "Facial", "duration": 60, "price": 95000, "active": True, "image": None},
    ]

    for s in services_seed:
        if db.get(Service, s["id"]):
            continue
        db.add(Service(**s))

    pros_seed = [
        {"id": 1, "name": "Valentina Torres", "specialty": "Masajes & Facial", "schedule_start": "08:00", "schedule_end": "17:00", "active": True},
        {"id": 2, "name": "Camila Ruiz", "specialty": "Manicure & Pedicure", "schedule_start": "09:00", "schedule_end": "18:00", "active": True},
        {"id": 3, "name": "Laura Gómez", "specialty": "Depilación", "schedule_start": "10:00", "schedule_end": "19:00", "active": True},
    ]

    for p in pros_seed:
        if db.get(Professional, p["id"]):
            continue
        db.add(Professional(**p))

    # Ensure base entities are persisted before appointments (FK constraints)
    db.commit()

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    apts_seed = [
        {"id": 1, "client_name": "Ana Martínez", "client_email": "ana@email.com", "client_phone": "3001234567", "service_id": 1, "professional_id": 1, "date": today, "time": "09:00", "status": "confirmed", "notes": "", "history": []},
        {"id": 2, "client_name": "Sandra López", "client_email": "san@email.com", "client_phone": "3009876543", "service_id": 3, "professional_id": 2, "date": today, "time": "10:00", "status": "pending", "notes": "", "history": []},
        {"id": 3, "client_name": "María Jiménez", "client_email": "mar@email.com", "client_phone": "3115556677", "service_id": 5, "professional_id": 3, "date": today, "time": "11:00", "status": "attended", "notes": "Cliente puntual", "history": []},
        {"id": 4, "client_name": "Paola Castro", "client_email": "pao@email.com", "client_phone": "3204443322", "service_id": 6, "professional_id": 1, "date": tomorrow, "time": "14:00", "status": "confirmed", "notes": "", "history": []},
        {"id": 5, "client_name": "Juliana Vargas", "client_email": "jul@email.com", "client_phone": "3177778899", "service_id": 2, "professional_id": 1, "date": tomorrow, "time": "10:30", "status": "cancelled", "notes": "Canceló por viaje", "history": []},
    ]

    for a in apts_seed:
        if db.get(Appointment, a["id"]):
            continue
        db.add(Appointment(**a))

    company = db.get(CompanyData, 1)
    if not company:
        company = CompanyData(
            id=1,
            business_name="Aura Spa",
            legal_name="Aura Spa S.A.S",
            nit="9999999999-9",
            address="Cra. 5 #120-45\nBogota, Colombia\nZona Rosa - Chapinero",
            phone="+57 (300) 123-4567",
            email="info@auraspa.com",
            city="Bogotá",
            state="Bogotá",
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
        db.add(company)

    db.commit()

    # Keep sequences in sync with explicit IDs (PostgreSQL)
    if db.bind and db.bind.dialect.name == "postgresql":
        def _set_seq(table: str, column: str = "id"):
            seq = f"{table}_{column}_seq"
            db.execute(
                text(
                    f"SELECT setval('{seq}', (SELECT COALESCE(MAX({column}), 1) FROM {table}))"
                )
            )

        _set_seq("users")
        _set_seq("services")
        _set_seq("professionals")
        _set_seq("appointments")
        _set_seq("company_data")
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
