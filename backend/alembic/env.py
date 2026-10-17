from logging.config import fileConfig

import app.models  # noqa: F401  tabloları metadata'ya kaydeder
from alembic import context
from app.core.config import get_settings
from app.db import Base, make_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(_url())
    with engine.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        if sqlite:
            # Batch modu tabloyu yeniden kurar (kopyala → eskisini sil). FK kontrolü açıkken, başka tablolardan
            # referans alan dolu bir tablo silinemiyor. PRAGMA transaction dışında olmalı.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        # SQLite ALTER TABLE kısıtları için batch modu.
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
        if sqlite:
            violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            if violations:
                raise RuntimeError(f"migration sonrası FK ihlali: {violations[:5]}")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
