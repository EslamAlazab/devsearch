from starlette.routing import Route, Mount
import render.users_renders as users
import render.projects_renders as projects
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

users_routes = [
    Route('/login/', endpoint=users.login,
          name='login-page', methods=['GET', 'POST'],),
    Route('/logout/', endpoint=users.logout,
          name='logout'),
    Route('/register/', endpoint=users.register,
          name='register', methods=['GET', 'POST']),

    Route('/user-profile/{profile_id:str}', endpoint=users.user_profile,
          name='user-profile'),
    Route('/', endpoint=users.profiles, name='profiles'),
    Route('/account', endpoint=users.account, name='account'),
    Route('/edit-account', endpoint=users.edit_account,
          name='edit-account', methods=['GET', 'POST']),
    Route('/edit-profile-image', endpoint=users.edit_profile_image,
          name='edit-profile-image', methods=['GET', 'POST']),

    Route('/create-skill', endpoint=users.create_skill,
          name='create-skill', methods=['GET', 'POST']),
    Route('/update-skill/{skill_id:str}', endpoint=users.update_skill,
          name='update-skill', methods=['GET', 'POST']),
    Route('/delete-skill/{skill_id:str}', endpoint=users.delete_skill,
          name='delete-skill', methods=['GET', 'POST']),

    Route('/inbox', endpoint=users.inbox, name='inbox'),
    Route('/message/{message_id:str}',
          endpoint=users.get_message, name='message'),
    Route('/create-message/{profile_id:str}',
          endpoint=users.create_message, name='create-message', methods=['GET', 'POST']),
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
routes = [
    Mount('/projects', routes=project_routes), Mount('', routes=users_routes),
]
# render_router = APIRouter(
#     prefix='', tags=['users-renders'], routes=routes)
