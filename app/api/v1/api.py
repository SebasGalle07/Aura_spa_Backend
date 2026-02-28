from fastapi import APIRouter

from app.api.v1.routers import auth, services, professionals, appointments, availability, admin, users, company

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(services.router, prefix="/services", tags=["services"])
api_router.include_router(professionals.router, prefix="/professionals", tags=["professionals"])
api_router.include_router(availability.router, prefix="/availability", tags=["availability"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(company.router, tags=["public"])
