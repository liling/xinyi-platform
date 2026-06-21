import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from xinyi_platform.base import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"


class AuthProvider(str, enum.Enum):
    LOCAL = "local"
    CAS = "cas"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider, name="auth_provider", schema="xinyi"),
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", schema="xinyi"),
        nullable=False,
        default=UserRole.USER,
        server_default="USER",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
