"""Auth API router — signup, login, and profile management."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.connection import get_session
from app.db.models.user import User
from app.dependencies import get_current_user
from app.rate_limit import limiter
from app.repositories.user_repo import UserRepository
from app.repositories.wishlist_repo import WishlistRepository
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    SignupRequest,
    UpdateProfileRequest,
    UserResponse,
)
from app.security import create_access_token, hash_password, verify_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# A precomputed hash with no matching plaintext — verified against on every
# login for a nonexistent email, so response time doesn't leak whether an
# account exists (bcrypt.checkpw would otherwise only run for real users,
# making "wrong password" and "no such account" distinguishable by timing).
_DUMMY_PASSWORD_HASH = hash_password("not-a-real-password-used-only-for-timing-safety")


async def _claim_device_wishlist_if_present(
    session: AsyncSession, user_id: UUID, device_id: Optional[UUID]
) -> None:
    """Best-effort: fold the current device's anonymous wishlist into the
    account being signed into. Never let this fail the auth request.

    Runs in a SAVEPOINT (not the outer transaction) — if the merge itself
    fails, only its own changes roll back; a plain `except` with no
    savepoint would leave the session's transaction aborted, and the
    caller's subsequent `session.commit()` would then also fail, silently
    discarding the just-created user row on signup.
    """
    if device_id is None:
        return
    try:
        async with session.begin_nested():
            await WishlistRepository(session).claim_device_wishlist(device_id, user_id)
    except Exception as e:
        logger.error(f"Failed to claim device wishlist for user {user_id}: {e}", exc_info=True)


@router.post("/signup", response_model=AuthResponse)
@limiter.limit(f"{get_settings().rate_limit_auth_per_min}/minute")
async def signup(
    request: Request,
    payload: SignupRequest,
    x_device_id: Optional[UUID] = Header(None, alias="X-Device-Id"),
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    """Create a new account. If X-Device-Id is present, that device's
    anonymous wishlist is folded into the new account."""
    try:
        user_repo = UserRepository(session)
        if await user_repo.get_by_email(payload.email):
            raise HTTPException(status_code=409, detail="An account with this email already exists")

        user = await user_repo.create(
            email=payload.email,
            password_hash=hash_password(payload.password),
            name=payload.name,
        )
        await _claim_device_wishlist_if_present(session, user.id, x_device_id)
        await session.commit()

        logger.info(f"New account created: {user.id}")
        token = create_access_token(user.id)
        return AuthResponse(user=UserResponse.model_validate(user), token=token)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Signup failed")


@router.post("/login", response_model=AuthResponse)
@limiter.limit(f"{get_settings().rate_limit_auth_per_min}/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    x_device_id: Optional[UUID] = Header(None, alias="X-Device-Id"),
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    """Log into an existing account. If X-Device-Id is present, that
    device's anonymous wishlist is folded into the account."""
    try:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_email(payload.email)
        password_hash = user.password_hash if user else _DUMMY_PASSWORD_HASH
        password_ok = verify_password(payload.password, password_hash)
        if not user or not password_ok:
            raise HTTPException(status_code=401, detail="Incorrect email or password")

        await _claim_device_wishlist_if_present(session, user.id, x_device_id)
        await session.commit()

        token = create_access_token(user.id)
        return AuthResponse(user=UserResponse.model_validate(user), token=token)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Login failed")


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    """Return the logged-in shopper's profile."""
    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """Update the logged-in shopper's name/size/department preferences."""
    try:
        updated = await UserRepository(session).update_profile(
            user.id,
            name=payload.name,
            preferred_size=payload.preferred_size,
            department=payload.department,
        )
        await session.commit()
        return UserResponse.model_validate(updated)
    except Exception as e:
        logger.error(f"Failed to update profile for {user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update profile")
