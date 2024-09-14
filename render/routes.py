from starlette.routing import Route
from render.users import users
from render.users import profiles
from render.users import skills
from render.users import messages
from render.projects import projects


users_routes = [
    Route('/login/', endpoint=users.login,
          name='login-page', methods=['GET', 'POST'],),
    Route('/logout/', endpoint=users.logout,
          name='logout'),
    Route('/register/', endpoint=users.register,
          name='register', methods=['GET', 'POST']),
    Route('/send-email-verification',
          endpoint=users.send_email_verification, name='send-email'),
    Route('/reset-password', endpoint=users.reset_password,
          name='reset-password', methods=['GET', 'POST']),
    Route('/change-password/{token}', endpoint=users.change_password,
          name='change-password', methods=['GET', 'POST']),

    Route('/user-profile/{profile_id:str}', endpoint=profiles.user_profile,
          name='user-profile'),
    Route('/', endpoint=profiles.profiles, name='profiles'),
    Route('/account', endpoint=profiles.account, name='account'),
    Route('/edit-account', endpoint=profiles.edit_account,
          name='edit-account', methods=['GET', 'POST']),
    Route('/edit-profile-image', endpoint=profiles.edit_profile_image,
          name='edit-profile-image', methods=['GET', 'POST']),

    Route('/create-skill', endpoint=skills.create_skill,
          name='create-skill', methods=['GET', 'POST']),
    Route('/update-skill/{skill_id:str}', endpoint=skills.update_skill,
          name='update-skill', methods=['GET', 'POST']),
    Route('/delete-skill/{skill_id:str}', endpoint=skills.delete_skill,
          name='delete-skill', methods=['GET', 'POST']),

    Route('/inbox', endpoint=messages.inbox, name='inbox'),
    Route('/message/{message_id:str}',
          endpoint=messages.get_message, name='message'),
    Route('/create-message/{profile_id:str}',
          endpoint=messages.create_message, name='create-message', methods=['GET', 'POST']),
]

project_routes = [
    Route('/', projects.projects, name='projects'),
    Route('/project/{project_id}', projects.project,
          name='project', methods=['GET', 'POST']),
    Route('/create-project', projects.create_project,
          name='create-project', methods=['GET', 'POST']),
    Route('/update-project/{project_id}', projects.update_project,
          name='update-project', methods=['GET', 'POST']),
    Route('/delete-project/{project_id}', projects.delete_project,
          name='delete-project', methods=['GET', 'POST']),
    Route('/project/{project_id}/delete-tag/{tag_id}', projects.delete_tag,
          name='delete-tag'),
]
