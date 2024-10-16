import contextlib
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from fastapi import Depends, HTTPException
from typing import Annotated
from base.models import Base
from base.config import logger


engine = create_async_engine('sqlite+aiosqlite:///devs.db')
SessionLocal = async_sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False)


async def create_db_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("""
        CREATE TRIGGER IF NOT EXISTS update_vote_total_after_insert
        AFTER INSERT ON reviews
        FOR EACH ROW
        BEGIN
            UPDATE projects
            SET vote_total = vote_total + 1
            WHERE project_id = NEW.project_id;
        END;
        """))

        await conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS update_vote_total_after_delete
            AFTER DELETE ON reviews
            FOR EACH ROW
            BEGIN
                UPDATE projects
                SET vote_total = vote_total - 1
                WHERE project_id = OLD.project_id;
            END;
        """))


@contextlib.asynccontextmanager
async def lifespan(app):
    await create_db_tables()  # Initialize database when app starts
    yield


async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        await db.close()


db_dependency = Annotated[AsyncSession, Depends(get_db)]


async def commit_db(db: AsyncSession) -> None:
    """
    Helper function to commit a database session and handle errors.

    Parameters:
    - db (Session): The database session to commit.

    Raises:
    - HTTPException: If an error occurs during the commit, with a status code of 500.
    """
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()  # Rollback the transaction in case of an error
        logger.error(f"Error committing to the database: {e}")
        raise HTTPException(
            status_code=500, detail="An error occurred while committing to the database")
