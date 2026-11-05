from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/api/integrations/abha", tags=["ABHA/ABDM connector"])


@router.get("")
def abha_status(_user: User = Depends(get_current_user), _db: Session = Depends(get_db)):
    return {
        "connection_status": "externally_blocked",
        "live_calls_enabled": False,
        "sandbox_credentials_configured": False,
        "consent_status": "not_started",
        "message": (
            "ABDM sandbox onboarding, credentials, permitted workflow specifications, and "
            "application validation are required before linking is enabled."
        ),
    }


@router.post("/connect")
def abha_connect(_user: User = Depends(get_current_user)):
    raise HTTPException(
        503,
        "Live ABHA linking is unavailable until official sandbox onboarding and credentials "
        "are supplied",
    )
