"""
Alembic (async db) config file
"""
from sqlalchemy.ext import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
import os
from alembic import context
from logging.config import fileConfig
from db.base import Base
import asyncio

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_url():
    url = os.environ["DATABASE_URL"]
    return url.replace("postgresql://", "postgresql+asyncpg://").replace(
        "postgres://", "postgresql+asyncpg://"
    )

def run_migrations_offline():   
    context.configure(
            url=get_url(),
            target_metadata= target_metadata,
            literal_binds=True,
            dialect_opts= {"paramstyle": "named"},
            )
    with context.begin_transaction():
        context.run_migrations()

def complete_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    engine = create_async_engine(get_url())
    async with engine.connect() as connection:
        await connection.run_sync(complete_migrations)
    await engine.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
