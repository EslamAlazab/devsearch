from fastapi.testclient import TestClient
from base.models import Base, User
from sqlalchemy.pool import StaticPool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from main import app
import pytest
from users.auth import bcrypt_context


testing_engine = create_async_engine(
    'sqlite+aiosqlite:///./test.db', poolclass=StaticPool)
TestingSessionLocal = async_sessionmaker(
    bind=testing_engine, autoflush=False, expire_on_commit=False)

client = TestClient(app)


def Override_get_current_user():
    return {'username': 'user', 'user_id': '65b24d7132a246859b7fe59bb195b9a6'}


async def override_get_db():
    async with testing_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        await db.close()


@pytest.fixture
async def test_user():
    user = User(
        username='testuser',
        email='testuser@test.com',
        first_name='test',
        last_name='user',
        password=bcrypt_context.hash('testpassword'),
    )
    db: AsyncSession = await override_get_db()
    db.add(user)
    await db.commit()
    yield user
    async with testing_engine.begin() as conn:
        await conn.execute(text('DELETE FROM users'))
