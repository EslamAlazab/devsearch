from .conftest import client


def test_user_profile(test_user):
    response = client.get(f'/user-profile/{test_user.profile_id}')
    assert 'test_user' in response.text
    assert f'{test_user.profile_id}' in response.text
