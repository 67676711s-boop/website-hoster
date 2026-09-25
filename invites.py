from datetime import datetime

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class InviteJoin(Base):
    __tablename__ = "invite_joins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    member_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    inviter_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    invite_code: Mapped[str | None] = mapped_column(Text, index=True, nullable=True)
    invite_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
