from fastapi import APIRouter

from app.api.v1.routers import (
    account_cancellation,
    admin,
    appointments,
    audit,
    auth,
    availability,
    chatbot,
    company,
    professionals,
    services,
    settlements,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(services.router, prefix="/services", tags=["services"])
api_router.include_router(professionals.router, prefix="/professionals", tags=["professionals"])
api_router.include_router(availability.router, prefix="/availability", tags=["availability"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
api_router.include_router(settlements.router, prefix="/settlements", tags=["settlements"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(audit.router, prefix="/audit-logs", tags=["audit"])
api_router.include_router(account_cancellation.router, prefix="/account-cancellation-requests", tags=["account"])
api_router.include_router(chatbot.router, prefix="/chatbot", tags=["chatbot"])
api_router.include_router(company.router, tags=["public"])
