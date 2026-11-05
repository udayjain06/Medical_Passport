from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import AuditEvent, PatientProfile, User
from app.rate_limit import auth_rate_limiter
from app.schemas import AuthResponse, LoginRequest, RegisterRequest, UserRead
from app.security import COOKIE_NAME, create_session_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["authentication"])
_DUMMY_HASH = hash_password("not-a-real-user-password")


def _rate_limit(request: Request, action: str) -> None:
    host = request.client.host if request.client else "unknown"
    auth_rate_limiter.check(
        f"{action}:{host}",
        settings.auth_rate_limit_count,
        settings.auth_rate_limit_window_seconds,
    )


def _set_session_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session_token(user.id, user.session_version),
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> AuthResponse:
    _rate_limit(request, "register")
    email = str(payload.email).strip().lower()
    user = User(email=email, password_hash=hash_password(payload.password))
    user.profiles.append(PatientProfile(full_name=payload.full_name, is_primary=True))
    db.add(user)
    try:
        db.flush()
        db.add(
            AuditEvent(
                user_id=user.id, action="account.registered", target_type="user", target_id=user.id
            )
        )
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        ) from None
    _set_session_cookie(response, user)
    return AuthResponse(user=UserRead.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> AuthResponse:
    _rate_limit(request, "login")
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    stored_hash = user.password_hash if user else _DUMMY_HASH
    password_matches = verify_password(payload.password, stored_hash)
    if user is None or not password_matches:
        raise HTTPException(status_code=401, detail="Email or password is incorrect")

    db.add(
        AuditEvent(
            user_id=user.id, action="auth.login.succeeded", target_type="user", target_id=user.id
        )
    )
    db.commit()
    db.refresh(user)
    _set_session_cookie(response, user)
    return AuthResponse(user=UserRead.model_validate(user))


@router.post("/logout")
def logout(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    user.session_version += 1
    db.add(AuditEvent(user_id=user.id, action="auth.logout", target_type="user", target_id=user.id))
    db.commit()
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return {"status": "logged_out"}


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    return user
