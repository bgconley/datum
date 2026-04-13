from pgvector.asyncpg import register_vector
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from datum.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)
async_session_factory = async_session


@event.listens_for(engine.sync_engine, "connect")
def register_pgvector_types(dbapi_connection, connection_record) -> None:
    del connection_record
    dbapi_connection.run_async(register_vector)


async def get_session():
    async with async_session() as session:
        yield session
