# Aura Spa Backend (FastAPI)

Backend REST en FastAPI, alineado con el frontend adjunto. Incluye autenticacion JWT, roles, CRUD de servicios y profesionales, citas, disponibilidad, panel admin y datos de configuracion de la empresa.

**Stack:** FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic, passlib[bcrypt], JWT, Uvicorn.

## Instalacion
1. Crear entorno virtual:
```
python -m venv .venv
.\.venv\Scripts\activate
```
2. Instalar dependencias:
```
pip install -r requirements.txt
```

## Variables de entorno
- `DATABASE_URL` (default: `postgresql+psycopg://postgres:argus@localhost:5432/aura_spa`)
- `SECRET_KEY` (default: `CHANGE_ME`)
- `ACCESS_TOKEN_EXPIRE_MINUTES` (default: `10`)
- `BACKEND_CORS_ORIGINS` (default: `http://localhost:4200`)
- `FRONTEND_APP_URL` (default: `http://localhost:4200`)
- `MEDIA_ROOT` (default: `media`)
- `MEDIA_URL` (default: `/media`)
- `SEED_ON_STARTUP` (default: `true`)
- `AUTO_CREATE_TABLES` (default: `false`)

Puedes crear un `.env` en la raiz con estos valores.

Para PostgreSQL local (usuario `postgres`):
```
postgresql+psycopg://postgres:TU_PASSWORD@localhost:5432/aura_spa
```

## Migraciones
```
alembic upgrade head
```

## Ejecutar servidor
```
uvicorn app.main:app --reload
```

## Documentacion interactiva
- `http://localhost:8000/docs`

## Credenciales demo (seed)
- Admin: `admin@auraspa.com` / `admin123`
- Cliente: `cliente@email.com` / `cliente123`
- Profesional: `valentina@auraspa.com` / `valentina123`

## Notas
- El seeder es idempotente y toma los mismos datos iniciales que el frontend (servicios, profesionales y usuarios).
- CORS acepta `BACKEND_CORS_ORIGINS` y adicionalmente agrega `FRONTEND_APP_URL` automaticamente.
- Las imagenes de servicios se guardan en `MEDIA_ROOT` y se sirven en `MEDIA_URL` (por defecto `/media/services/...`).

## Endpoints principales
Base URL: `http://localhost:8000/api/v1`

**Auth**
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `POST /auth/forgot-password` (deshabilitado, responde 501)
- `POST /auth/reset-password` (deshabilitado, responde 501)
- `GET /auth/me`

**Services**
- `GET /services`
- `GET /services/{id}`
- `POST /services` (admin)
- `PUT /services/{id}` (admin)
- `DELETE /services/{id}` (admin)
- `POST /services/{id}/image` (admin, multipart file)
- `DELETE /services/{id}/image` (admin)

**Professionals**
- `GET /professionals`
- `GET /professionals/{id}`
- `POST /professionals` (admin)
- `PUT /professionals/{id}` (admin)

**Availability**
- `GET /availability?service_id=..&professional_id=..&date=YYYY-MM-DD`

**Appointments**
- `POST /appointments` (cliente)
- `GET /appointments/my` (cliente)
- `GET /appointments` (admin)
- `GET /appointments/{id}`
- `POST /appointments/{id}/confirm` (admin)
- `POST /appointments/{id}/cancel` (cliente o admin)
- `POST /appointments/{id}/attend` (admin o professional)
- `POST /appointments/{id}/reschedule` (admin)

**Admin**
- `GET /admin/summary?date=YYYY-MM-DD`
- `GET /admin/company` / `PUT /admin/company` (admin)
- `GET /admin/branding` / `PUT /admin/branding` (admin)

**Public**
- `GET /company`
- `GET /branding`
- `POST /contact` (recibe y confirma; no envia correo)

**Users**
- `GET /users` (admin)
- `POST /users` (admin)
- `PUT /users/{id}` (admin)
- `DELETE /users/{id}` (admin)
- `GET /users/me`
- `PUT /users/me`
- `POST /users/me/password`
