from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from fastapi import Depends, HTTPException
from typing import Annotated
from models import Base
from config import logger


engine = create_async_engine('sqlite+aiosqlite:///devs.db')
SessionLocal = async_sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False)


async def get_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
