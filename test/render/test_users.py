from .conftest import client, engine, text
import pytest


def test_get_register_page():
    # Test if the registration page renders correctly for a GET request
    response = client.get("/register")
    assert response.status_code == 200
    assert "form" in response.text  # Ensure the registration form is present


def test_post_register_invalid_data():
    form_data = {
        "username": "johndoe222",
        "email": "johndoe@examp",
        "password": "Password123",
        "password_2": "Password@12"
    }

    response = client.post("/register", data=form_data)
    assert response.status_code == 200
    assert "not a valid email" in response.text  # Check if error is rendered
    # Check if error is rendered
    assert "Password must contain at least one symbol" in response.text
    # Check if error is rendered
    assert "Please make sure to use the same password" in response.text


@pytest.mark.asyncio
async def test_post_register_valid_data():
    form_data = {
        "username": "johndoe222",
        "email": "johndoe@example.com",
        "password": "Password@123",
        "password_2": "Password@123"
    }

    response = client.post("/register", data=form_data)
    assert response.status_code == 200
    assert 'Search Developers' in response.text
    assert 'johndoe222' in response.text

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM profiles;"))
