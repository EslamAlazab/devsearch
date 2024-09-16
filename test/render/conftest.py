import uuid
from starlette.applications import Starlette
from starlette.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Mount
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text
import pytest_asyncio
from base.models import Profile
from apis.users.auth import create_access_token
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from base.middleware import BasicAuthBackend
from main import users_routes, project_routes
from base.models import Base

# Create async in-memory SQLite engine
DATABASE_URL = "sqlite+aiosqlite:///testdevs.db"
engine = create_async_engine(DATABASE_URL)
TestSessionLocal = async_sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False)


class DBSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Create a new database session
        async with TestSessionLocal() as session:
            request.state.db = session  # Add session to request.state
            response = await call_next(request)  # Process the request
            return response


middleware = [
    Middleware(AuthenticationMiddleware, backend=BasicAuthBackend()),
    Middleware(DBSessionMiddleware),
]

routes = [
    Mount("/static", StaticFiles(directory="static"), name="static"),
    Mount('/projects', routes=project_routes, middleware=middleware),
    Mount('', routes=users_routes, middleware=middleware),
]

test_app = Starlette(routes=routes)
client = TestClient(test_app)


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


@pytest_asyncio.fixture
async def test_db():
    await create_db_tables()

    TestSessionLocal = async_sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False)

    db = TestSessionLocal()
    yield db
    await db.aclose()


@pytest_asyncio.fixture
async def test_user(test_db):
    user = Profile(username='test_user', email='testemail@test.com',
                   password='fake_hashed_password')
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    yield user

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM profiles;"))


# token = create_access_token(
#     username=test_user.username, user_id=str(test_user.profile_id))
# # Return the test client

# @pytest.fixture
# async def async_client():
#     # Use httpx for async testing
#     async with AsyncClient(app=s_app, base_url="http://testserver") as client:
#         yield client
