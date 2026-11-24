from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.system import PlatformInfoResponse, SystemSettingResponse
from app.services.system_service import SystemService

router = APIRouter(prefix="/system", tags=["System & Platform Foundation"])
service = SystemService()


@router.get(
    "/info",
    response_model=PlatformInfoResponse,
    summary="Platform Status & Foundation Metadata",
)
def get_platform_info(db: Session = Depends(get_db)):
    """
    Returns platform metadata, targeted geography (India / INR),
    and verified database connectivity.
    """
    return service.get_platform_info(db)


@router.get(
    "/settings",
    response_model=list[SystemSettingResponse],
    summary="List Foundation System Settings",
)
def list_system_settings(db: Session = Depends(get_db)):
    """
    Retrieves system configuration entities persisted in PostgreSQL.
    """
    return service.repository.list_settings(db)
