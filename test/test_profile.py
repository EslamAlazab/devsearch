from .utils import *
from base.database import get_db
from users.auth import get_current_user
import tempfile


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = Override_get_current_user


@pytest.mark.asyncio
async def test_update_profile_image(test_user):
    # Create a temporary image file for testing
    with tempfile.NamedTemporaryFile(suffix=".jpg") as temp_image:
        temp_image.write(b"Test image content")
        temp_image.seek(0)

        response = client.put(
            "/profiles/me/profile-image",
            files={"image": ("test.jpg", temp_image, "image/jpeg")},
            headers={"Authorization": f"Bearer {test_user}"}
        )

        print(response)
        assert response.status_code == 204
