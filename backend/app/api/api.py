from fastapi import APIRouter

from app.api.routes import auth, onboarding, system, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(onboarding.router)
api_router.include_router(system.router)
