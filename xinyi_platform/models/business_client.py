import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from xinyi_platform.base import Base


class ClientStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class BusinessClient(Base):
    __tablename__ = "business_clients"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    redirect_uris: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[ClientStatus] = mapped_column(
        Enum(ClientStatus, name="client_status", schema="xinyi"),
        nullable=False,
        default=ClientStatus.ACTIVE,
        server_default="ACTIVE",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
