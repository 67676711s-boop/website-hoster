import json

from sqlalchemy import Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base


class GuildPanelConfig(Base):
    __tablename__ = "guild_panel_config"

    guild_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Tickets
    ticket_panel_channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ticket_panel_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ticket_category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ticket_support_role_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ticket_required_role_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ticket_blacklist_role_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_channel_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_panel_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_panel_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_button_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_button_emoji: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_panel_color: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_welcome_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_welcome_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Applications
    application_panel_channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_panel_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_review_channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_reviewer_role_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_panel_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_panel_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_button_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_button_emoji: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_panel_color: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_form_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_questions: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_dm_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    application_dm_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Ticket transcript preference (actual files are stored by the bot)
    ticket_transcript_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def get_blacklist_role_ids(self) -> list[int]:
        if not self.ticket_blacklist_role_ids:
            return []
        try:
            data = json.loads(self.ticket_blacklist_role_ids)
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        result: list[int] = []
        for value in data:
            try:
                result.append(int(value))
            except (TypeError, ValueError):
                continue
        return list(dict.fromkeys(result))

    def get_questions(self) -> list[str]:
        if not self.application_questions:
            return []
        try:
            data = json.loads(self.application_questions)
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        return [str(item).strip() for item in data if str(item).strip()][:20]
