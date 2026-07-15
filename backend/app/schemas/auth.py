"""Request/response schemas for signup, login, and profile endpoints."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    name: str = Field(..., min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=72)


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    preferred_size: Optional[str] = None
    department: Optional[str] = None

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Returned on signup/login — the token is stored client-side and
    sent back as `Authorization: Bearer <token>` on subsequent requests."""

    user: UserResponse
    token: str


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    preferred_size: Optional[str] = Field(None, max_length=10)
    department: Optional[str] = Field(None, max_length=20)
