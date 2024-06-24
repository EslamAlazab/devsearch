from .utils import *
from database import get_db


app.dependency_overrides[get_db] = override_get_db


@pytest.mark.asyncio
async def test_create_user():
    user_data = {
        'username': 'testuser',
        'email': 'testuser@test.com',
        'first_name': 'test',
        'last_name': 'user',
        'password': 'Testpassword@1',
    }
    response = client.post('/users-api', json=user_data)

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == user_data["username"]
    assert data["email"] == user_data["email"]
    assert data["first_name"] == user_data["first_name"]
    assert data["last_name"] == user_data["last_name"]
    assert bcrypt_context.verify(user_data["password"], data['password'])

    async with testing_engine.begin() as conn:
        await conn.execute(text('DELETE FROM users'))
