import json

from sqlalchemy import Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base


class GuildSettings(Base):
    __tablename__ = "guild_settings"

    guild_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Join / welcome
    auto_role_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    welcome_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    welcome_channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AutoMod
    automod_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    block_links: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    block_attachments: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    block_invites: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    automod_ignore_role_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    automod_ignore_channel_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    automod_ignore_user_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    automod_ignore_bots: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Logging
    log_channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    log_deleted_messages: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    log_edited_messages: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    log_mod_actions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    log_automod: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    log_giveaways: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    log_ticket_transcripts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    log_invites: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Anti-raid
    anti_raid_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    anti_raid_threshold: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    anti_raid_window_seconds: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    @staticmethod
    def _read_ids(value: str | None) -> list[int]:
        if not value:
            return []
        try:
            data = json.loads(value)
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        result: list[int] = []
        for item in data:
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                continue
        return list(dict.fromkeys(result))

    def get_ignore_role_ids(self) -> list[int]:
        return self._read_ids(self.automod_ignore_role_ids)

    def get_ignore_channel_ids(self) -> list[int]:
        return self._read_ids(self.automod_ignore_channel_ids)

    def get_ignore_user_ids(self) -> list[int]:
        return self._read_ids(self.automod_ignore_user_ids)
