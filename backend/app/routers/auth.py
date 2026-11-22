import logging
from datetime import UTC, datetime, timedelta
from time import monotonic, sleep
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import document_storage
from app.auth_tokens import consume_token, issue_token, revoke_tokens
from app.config import settings
from app.database import get_db
from app.demo_fixtures import DEMO_EMAIL
from app.dependencies import get_current_user
from app.email import (
    EmailDeliveryError,
    EmailProvider,
    auth_email,
    provide_email_provider,
    take_test_email_link,
)
from app.medical_ai import provider_configured
from app.models import (
    AuditEvent,
    ConsentRecord,
    EmergencyShare,
    MedicalDocument,
    PatientProfile,
    TimelineEvent,
    User,
)
from app.network import client_ip
from app.rate_limit import auth_rate_limiter
from app.schemas import AuthResponse, LoginRequest, RegisterRequest, UserRead
from app.security import COOKIE_NAME, create_session_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["authentication"])
logger = logging.getLogger(__name__)
_DUMMY_HASH = hash_password("not-a-real-user-password")
CONSENT_VERSION = "v1"


@router.get("/ai-capabilities")
def ai_capabilities(user: User = Depends(get_current_user)) -> dict[str, bool]:
    return {"external_ai_configured": provider_configured()}


def _rate_limit(request: Request, action: str) -> None:
    auth_rate_limiter.check(
        f"{action}:{client_ip(request)}",
        settings.auth_rate_limit_count,
        settings.auth_rate_limit_window_seconds,
        "Too many authentication attempts. Try again later.",
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


def _locale(request: Request) -> str:
    return "hi" if request.headers.get("accept-language", "").lower().startswith("hi") else "en"


def _email_link(path: str, token: str) -> str:
    return f"{settings.public_app_url.rstrip('/')}/{path}?{urlencode({'token': token})}"


def _deliver_auth_email(provider: EmailProvider, message) -> None:
    try:
        provider.send(message)
    except EmailDeliveryError:
        logger.warning("auth_email_delivery_failed provider=%s", settings.email_provider)


def _pad_password_reset_response(started: float) -> None:
    minimum_seconds = settings.auth_uniform_response_ms / 1000
    remaining = minimum_seconds - (monotonic() - started)
    if remaining > 0:
        sleep(remaining)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    provider: EmailProvider = Depends(provide_email_provider),
    db: Session = Depends(get_db),
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
        for purpose in ("terms", "privacy"):
            record = ConsentRecord(
                user_id=user.id,
                purpose=purpose,
                version=CONSENT_VERSION,
                granted_at=datetime.now(UTC),
            )
            db.add(record)
            db.flush()
            db.add(
                AuditEvent(
                    user_id=user.id,
                    action="consent.granted",
                    target_type="consent",
                    target_id=record.id,
                )
            )
        verification_token = issue_token(db, user.id, "email_verification", timedelta(hours=24))
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        ) from None
    _set_session_cookie(response, user)
    background_tasks.add_task(
        _deliver_auth_email,
        provider,
        auth_email(
            email,
            "verification",
            _email_link("verify-email", verification_token),
            _locale(request),
        ),
    )
    return AuthResponse(user=UserRead.model_validate(user))


@router.get("/consents")
def list_consents(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    records = db.scalars(
        select(ConsentRecord)
        .where(ConsentRecord.user_id == user.id)
        .order_by(ConsentRecord.granted_at.desc(), ConsentRecord.purpose)
    ).all()
    return [
        {
            "id": str(record.id),
            "purpose": record.purpose,
            "version": record.version,
            "granted_at": record.granted_at.isoformat(),
            "withdrawn_at": record.withdrawn_at.isoformat() if record.withdrawn_at else None,
        }
        for record in records
    ]


@router.post("/consents/{purpose}/withdraw")
def withdraw_consent(
    purpose: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    if purpose in {"terms", "privacy"}:
        raise HTTPException(
            409,
            "Terms and privacy records cannot be withdrawn here. "
            "Delete your account to stop using the service.",
        )
    if purpose != "emergency_sharing":
        raise HTTPException(404, "Consent purpose not found")

    now = datetime.now(UTC)
    active_records = db.scalars(
        select(ConsentRecord).where(
            ConsentRecord.user_id == user.id,
            ConsentRecord.purpose == purpose,
            ConsentRecord.withdrawn_at.is_(None),
        )
    ).all()
    if not active_records:
        raise HTTPException(409, "No active emergency-sharing consent exists")

    for record in active_records:
        record.withdrawn_at = now
    shares = db.scalars(
        select(EmergencyShare).where(
            EmergencyShare.created_by_user_id == user.id,
            EmergencyShare.revoked_at.is_(None),
            EmergencyShare.expires_at > now,
        )
    ).all()
    for share in shares:
        share.revoked_at = now
        db.add(
            AuditEvent(
                user_id=user.id,
                action="emergency_share.revoked",
                target_type="emergency_share",
                target_id=share.id,
            )
        )
    db.add(
        AuditEvent(
            user_id=user.id,
            action="consent.withdrawn",
            target_type="consent",
            target_id=active_records[0].id,
        )
    )
    db.commit()
    return {"withdrawn_records": len(active_records), "revoked_links": len(shares)}


@router.get("/audit-log")
def list_audit_log(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.user_id == user.id)
        .order_by(AuditEvent.created_at.desc())
        .limit(100)
    ).all()
    return [{"time": event.created_at.isoformat(), "action": event.action} for event in events]


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


@router.get("/demo-status")
def demo_status(db: Session = Depends(get_db)) -> dict[str, bool]:
    enabled = settings.demo_mode and settings.app_env != "production"
    if enabled:
        enabled = (
            db.scalar(select(User.id).where(User.email == DEMO_EMAIL, User.is_demo.is_(True)))
            is not None
        )
    return {"enabled": enabled}


@router.post("/demo-login", response_model=AuthResponse)
def demo_login(request: Request, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    _rate_limit(request, "demo-login")
    if not settings.demo_mode or settings.app_env == "production":
        raise HTTPException(status_code=404, detail="Demo access is unavailable")
    user = db.scalar(
        select(User).where(
            User.email == DEMO_EMAIL,
            User.is_demo.is_(True),
            User.email_verified_at.is_not(None),
        )
    )
    if user is None:
        raise HTTPException(status_code=404, detail="Demo access is unavailable")
    db.add(
        AuditEvent(
            user_id=user.id,
            action="auth.demo_login.succeeded",
            target_type="user",
            target_id=user.id,
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


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1, max_length=2048)


@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    user = consume_token(db, payload.token, "email_verification")
    if user is None:
        raise HTTPException(400, "Verification link is invalid or has expired")
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
        db.add(
            AuditEvent(
                user_id=user.id,
                action="auth.email_verified",
                target_type="user",
                target_id=user.id,
            )
        )
    db.commit()
    return {"status": "verified"}


@router.post("/resend-verification")
def resend_verification(
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    provider: EmailProvider = Depends(provide_email_provider),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    _rate_limit(request, "resend-verification")
    if user.email_verified_at is None:
        revoke_tokens(db, user.id, "email_verification")
        verification_token = issue_token(db, user.id, "email_verification", timedelta(hours=24))
        db.add(
            AuditEvent(
                user_id=user.id,
                action="auth.email_verification.resent",
                target_type="user",
                target_id=user.id,
            )
        )
        db.commit()
        background_tasks.add_task(
            _deliver_auth_email,
            provider,
            auth_email(
                user.email,
                "verification",
                _email_link("verify-email", verification_token),
                _locale(request),
            ),
        )
    return {"message": "If this account needs verification, instructions will be sent."}


@router.get("/test/email-link")
def test_email_link(
    purpose: str = "email_verification",
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    if settings.app_env != "test" or not settings.email_test_hook_enabled:
        raise HTTPException(404, "Not found")
    if purpose not in {"email_verification", "password_reset"}:
        raise HTTPException(422, "Unsupported email purpose")
    link = take_test_email_link(user.email, purpose)
    if link is None:
        raise HTTPException(404, "No test email is available")
    return {"url": link}


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=2048)
    password: str = Field(min_length=12, max_length=128)


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    provider: EmailProvider = Depends(provide_email_provider),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    started = monotonic()
    _rate_limit(request, "forgot-password")
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    reset_token = None
    if user is not None:
        revoke_tokens(db, user.id, "password_reset")
        reset_token = issue_token(db, user.id, "password_reset", timedelta(minutes=30))
    db.add(
        AuditEvent(
            user_id=user.id if user else None,
            action="auth.password_reset.requested",
            target_type="user" if user else "password_reset_request",
            target_id=user.id if user else None,
        )
    )
    db.commit()
    if user is not None and reset_token is not None:
        background_tasks.add_task(
            _deliver_auth_email,
            provider,
            auth_email(
                user.email,
                "password_reset",
                _email_link("reset-password", reset_token),
                _locale(request),
            ),
        )
    _pad_password_reset_response(started)
    return {"message": "If an account exists, password reset instructions will be sent."}


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    _rate_limit(request, "reset-password")
    user = consume_token(db, payload.token, "password_reset")
    if user is None:
        raise HTTPException(400, "Password reset link is invalid or has expired")
    user.password_hash = hash_password(payload.password)
    user.session_version += 1
    db.add(
        AuditEvent(
            user_id=user.id,
            action="auth.password_reset.completed",
            target_type="user",
            target_id=user.id,
        )
    )
    db.commit()
    return {"status": "password_reset"}


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


@router.get("/export")
def export_my_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Machine-readable copy of everything the account owns (right of access / portability)."""
    profiles = db.scalars(select(PatientProfile).where(PatientProfile.user_id == user.id)).all()
    ids = [p.id for p in profiles]
    events = db.scalars(select(TimelineEvent).where(TimelineEvent.profile_id.in_(ids))).all()
    documents = db.scalars(select(MedicalDocument).where(MedicalDocument.profile_id.in_(ids))).all()
    shares = db.scalars(select(EmergencyShare).where(EmergencyShare.profile_id.in_(ids))).all()
    db.add(
        AuditEvent(
            user_id=user.id, action="account.exported", target_type="user", target_id=user.id
        )
    )
    db.commit()
    return {
        "account": {"email": user.email, "created_at": user.created_at.isoformat()},
        "profiles": [
            {
                "id": str(p.id),
                "full_name": p.full_name,
                "blood_group": p.blood_group,
                "known_allergies": p.known_allergies,
                "major_conditions": p.major_conditions,
                "current_medications": p.current_medications,
                "emergency_contacts": [
                    {"full_name": c.full_name, "phone_number": c.phone_number}
                    for c in p.emergency_contacts
                ],
            }
            for p in profiles
        ],
        "timeline_events": [
            {
                "title": e.title,
                "category": e.category,
                "event_date": e.event_date.isoformat() if e.event_date else None,
                "summary": e.summary,
                "source_document_filename": e.source_document_filename,
                "verification_status": e.verification_status,
            }
            for e in events
        ],
        "documents": [
            {
                "id": str(d.id),
                "filename": d.original_filename,
                "category": d.category,
                "uploaded_at": d.created_at.isoformat(),
                "sha256": d.sha256_checksum,
            }
            for d in documents
        ],
        "emergency_links": [
            {
                "fields": s.shared_fields,
                "expires_at": s.expires_at.isoformat(),
                "revoked": s.revoked_at is not None,
            }
            for s in shares
        ],
    }


@router.post("/delete-account")
def delete_account(
    payload: DeleteAccountRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Permanently erase the account, its profiles, files, timeline and emergency links."""
    _rate_limit(request, "delete-account")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=403, detail="Password is incorrect")
    ids = list(db.scalars(select(PatientProfile.id).where(PatientProfile.user_id == user.id)).all())
    documents = db.scalars(
        select(MedicalDocument).where(
            or_(
                MedicalDocument.profile_id.in_(ids),
                MedicalDocument.uploaded_by_user_id == user.id,
            )
        )
    )
    for document in documents:
        document_storage.delete(document.profile_id, document.id)
    db.delete(user)
    db.add(AuditEvent(user_id=None, action="account.deleted", target_type="user", target_id=None))
    db.commit()
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return {"status": "deleted"}
