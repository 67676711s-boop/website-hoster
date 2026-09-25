from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///./serverguard.db"


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    # Import every model before create_all().
    import settings  # noqa: F401
    import panels  # noqa: F401
    import moderation  # noqa: F401
    import invites  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

        def migrate(sync_connection) -> None:
            inspector = inspect(sync_connection)
            existing_tables = set(inspector.get_table_names())

            migrations = {
                "guild_settings": {
                    "welcome_enabled": "BOOLEAN NOT NULL DEFAULT 1",
                    "welcome_channel_id": "INTEGER",
                    "welcome_message": "TEXT",
                    "block_invites": "BOOLEAN NOT NULL DEFAULT 0",
                    "log_deleted_messages": "BOOLEAN NOT NULL DEFAULT 1",
                    "log_edited_messages": "BOOLEAN NOT NULL DEFAULT 1",
                    "log_mod_actions": "BOOLEAN NOT NULL DEFAULT 1",
                    "log_automod": "BOOLEAN NOT NULL DEFAULT 1",
                    "log_giveaways": "BOOLEAN NOT NULL DEFAULT 1",
                    "log_ticket_transcripts": "BOOLEAN NOT NULL DEFAULT 1",
                    "log_invites": "BOOLEAN NOT NULL DEFAULT 1",
                    "anti_raid_enabled": "BOOLEAN NOT NULL DEFAULT 1",
                    "anti_raid_threshold": "INTEGER NOT NULL DEFAULT 8",
                    "anti_raid_window_seconds": "INTEGER NOT NULL DEFAULT 10",
                    "automod_ignore_role_ids": "TEXT",
                    "automod_ignore_channel_ids": "TEXT",
                    "automod_ignore_user_ids": "TEXT",
                    "automod_ignore_bots": "BOOLEAN NOT NULL DEFAULT 1",
                },
                "guild_panel_config": {
                    "ticket_blacklist_role_ids": "TEXT",
                    "ticket_channel_name": "TEXT",
                    "ticket_panel_title": "TEXT",
                    "ticket_panel_description": "TEXT",
                    "ticket_button_label": "TEXT",
                    "ticket_button_emoji": "TEXT",
                    "ticket_panel_color": "TEXT",
                    "ticket_welcome_title": "TEXT",
                    "ticket_welcome_description": "TEXT",
                    "application_panel_title": "TEXT",
                    "application_panel_description": "TEXT",
                    "application_button_label": "TEXT",
                    "application_button_emoji": "TEXT",
                    "application_panel_color": "TEXT",
                    "application_form_title": "TEXT",
                    "application_questions": "TEXT",
                    "application_dm_enabled": "BOOLEAN NOT NULL DEFAULT 1",
                    "application_dm_message": "TEXT",
                    "ticket_transcript_enabled": "BOOLEAN NOT NULL DEFAULT 1",
                },
            }

            for table_name, column_map in migrations.items():
                if table_name not in existing_tables:
                    continue

                existing_columns = {
                    column["name"]
                    for column in inspector.get_columns(table_name)
                }

                for column_name, column_type in column_map.items():
                    if column_name in existing_columns:
                        continue

                    sync_connection.execute(
                        text(
                            f"ALTER TABLE {table_name} "
                            f"ADD COLUMN {column_name} {column_type}"
                        )
                    )
                    print(f"Added database column: {table_name}.{column_name}")

        await connection.run_sync(migrate)
