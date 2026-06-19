import hashlib
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token, create_refresh_token, hash_token,
    find_user_by_email, get_current_user, hash_password,
    verify_password, REFRESH_TOKEN_EXPIRE_DAYS
)
from app.core.config import get_settings
from app.db.session import get_db
from app.models import AuditAction, PendingPasswordChange, User, UserRole, RefreshToken
from app.schemas import AccountUpdateRequest, LoginRequest, PasswordChangeRequest, PasswordChangeVerifyRequest, UserCreate, UserRead
from app.services.audit import log_action
from app.services.email import generate_password_change_token, send_password_change_email, verify_password_change_token
from app.services.request_security import enforce_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])
REFRESH_COOKIE_PATH = "/api/auth"
ACCESS_COOKIE_PATH = "/api"


def hash_password_change_token_id(token_id: str) -> str:
    return hashlib.sha256(token_id.encode("utf-8")).hexdigest()


def user_to_schema(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        name=user.full_name,
        email=user.email,
        role=user.role.value,
        manager_id=user.manager_id,
        manager_name=user.manager.full_name if user.manager else None,
    )

async def _issue_tokens(user: User, db: AsyncSession, response: Response) -> UserRead:
    settings = get_settings()
    access_token = create_access_token(user)
    raw_refresh, hashed_refresh = create_refresh_token()

    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    await db.commit()

    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=settings.environment.lower() in {"prod", "production"},
        samesite="lax",
        max_age=60 * 60 * 24 * REFRESH_TOKEN_EXPIRE_DAYS,
        path=REFRESH_COOKIE_PATH,
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.environment.lower() in {"prod", "production"},
        samesite="lax",
        max_age=60 * 60 * settings.access_token_expire_minutes,
        path=ACCESS_COOKIE_PATH,
    )
    return user_to_schema(user)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserCreate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    await enforce_rate_limit(request=request, bucket="auth_register", limit=5, window_seconds=60)
    existing = await find_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    user = User(
        full_name=payload.name.strip(),
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        role=UserRole(payload.role),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return await _issue_tokens(user, db, response)


@router.post("/login", response_model=UserRead)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    await enforce_rate_limit(request=request, bucket="auth_login", limit=10, window_seconds=60)
    user = await find_user_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    session = await _issue_tokens(user, db, response)
    await log_action(db, user, AuditAction.login, target_id=user.id, target_label=user.full_name)
    return session


@router.post("/refresh", response_model=UserRead)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
) -> UserRead:
    await enforce_rate_limit(request=request, bucket="auth_refresh", limit=20, window_seconds=60)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    token_hash = hash_token(refresh_token)
    record = (
        await db.execute(
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .where(RefreshToken.revoked == False)
            .where(RefreshToken.expires_at > datetime.now(timezone.utc))
        )
    ).scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    record.revoked = True
    await db.commit()

    user = await db.get(User, record.user_id)
    return await _issue_tokens(user, db, response)


@router.post("/logout")
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
) -> dict:
    user: User | None = None
    if refresh_token:
        token_hash = hash_token(refresh_token)
        record = (
            await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        ).scalar_one_or_none()
        if record:
            user = await db.get(User, record.user_id)
            record.revoked = True
            await db.commit()
    if user:
        await log_action(db, user, AuditAction.logout, target_id=user.id, target_label=user.full_name)

    response.delete_cookie("refresh_token", path=REFRESH_COOKIE_PATH)
    response.delete_cookie("access_token", path=ACCESS_COOKIE_PATH)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserRead)
async def get_me(user: User = Depends(get_current_user)) -> UserRead:
    return user_to_schema(user)


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: AccountUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserRead:
    user.full_name = payload.name.strip()
    await db.commit()
    await db.refresh(user)
    return user_to_schema(user)


@router.post("/change-password")
async def change_password(
    payload: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    if verify_password(payload.new_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be different")

    new_hash = hash_password(payload.new_password)
    verification_token, token_id, expires_at = generate_password_change_token(user.id)
    now = datetime.now(timezone.utc)

    await db.execute(
        update(PendingPasswordChange)
        .where(PendingPasswordChange.user_id == user.id)
        .where(PendingPasswordChange.used_at.is_(None))
        .where(PendingPasswordChange.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.add(
        PendingPasswordChange(
            user_id=user.id,
            token_hash=hash_password_change_token_id(token_id),
            new_password_hash=new_hash,
            expires_at=expires_at,
        )
    )
    await db.commit()
    await send_password_change_email(user.email, verification_token)
    return {"message": "A verification email has been sent. Please check your inbox and click the link to confirm your password change. The link expires in 15 minutes."}


@router.post("/verify-password-change")
async def verify_password_change(
    payload: PasswordChangeVerifyRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        token_data = verify_password_change_token(payload.token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    user = await db.get(User, token_data["user_id"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    token_id = str(token_data.get("jti") or "").strip()
    if not token_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid password change link")

    token_hash = hash_password_change_token_id(token_id)
    pending_change = (
        await db.execute(
            select(PendingPasswordChange)
            .where(PendingPasswordChange.user_id == user.id)
            .where(PendingPasswordChange.token_hash == token_hash)
        )
    ).scalar_one_or_none()
    if (
        not pending_change
        or pending_change.revoked_at is not None
        or pending_change.used_at is not None
        or pending_change.expires_at <= datetime.now(timezone.utc)
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password change link is no longer valid. Please request a new one.")

    now = datetime.now(timezone.utc)
    user.hashed_password = pending_change.new_password_hash
    pending_change.used_at = now
    await db.execute(
        update(PendingPasswordChange)
        .where(PendingPasswordChange.user_id == user.id)
        .where(PendingPasswordChange.id != pending_change.id)
        .where(PendingPasswordChange.used_at.is_(None))
        .where(PendingPasswordChange.revoked_at.is_(None))
        .values(revoked_at=now)
    )

    # Revoke ALL refresh tokens for this user (global logout)
    existing_tokens = (
        await db.execute(
            select(RefreshToken)
            .where(RefreshToken.user_id == user.id)
            .where(RefreshToken.revoked == False)
        )
    ).scalars().all()
    for rt in existing_tokens:
        rt.revoked = True

    await db.commit()

    # Clear the refresh cookie on this response too
    response.delete_cookie("refresh_token", path=REFRESH_COOKIE_PATH)
    response.delete_cookie("access_token", path=ACCESS_COOKIE_PATH)

    await log_action(db, user, AuditAction.password_change, target_id=user.id, target_label=user.full_name)

    return {"message": "Password updated successfully. Please log in again with your new password."}
