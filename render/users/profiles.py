from fastapi import status, HTTPException, UploadFile, Request
from fastapi.responses import RedirectResponse
from starlette.authentication import requires
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from base.models import Profile, Project
from base.database import commit_db
from base.config import templates

from apis.users.users import get_user, search_users
from apis.users.schemas import UpdateProfile
from apis.users.utils import save_and_compress_image
from apis.projects.projects import get_user_projects
from render.utils import Paginator, count_obj, remove_old_image
from render.schemas import Alert


async def profiles(request: Request):
    """
    Handles displaying a paginated list of profiles, with optional filtering by username and skills.

    Args:
        request (Request): The current HTTP request object, which includes query parameters, and cookies.

    Returns:
        TemplateResponse: Renders the profiles page with a list of profiles and pagination data.

    Workflow:
    - Retrieves query parameters for filtering:
        - `search_query`: Optional parameter to search by username.
        - `skill`: Optional parameter to filter profiles by skill.
        - `page`: Optional parameter to paginate profiles, defaults to 1.
        - `size`: Optional parameter to specify the number of profiles per page, defaults to 9.
    - Queries the database for profiles matching the search criteria, with pagination applied.
    - Calculates the total number of profiles for pagination purposes.
    - If an alert exists in the cookies, it is added to the context for rendering.
    - Renders the profiles page with the search results, paginator, and any existing alert.

    """
    # Retrieve optional query parameters for filtering and pagination.
    db = request.state.db
    username: str | None = request.query_params.get('search_query', None)
    skill: str | None = request.query_params.get('skill', None)
    page: int = max(int(request.query_params.get('page', 1)), 1)
    size: int = max(int(request.query_params.get('page', 9)), 9)

    profiles = await search_users(db, username, skill, page, size)
    total_profiles = await count_obj(Profile.profile_id, db=db)
    paginator = Paginator(
        page=page, size=size, total=total_profiles)

    context = {"profiles": profiles,
               'search_query': username, 'paginator': paginator}

    # Check for alert data in cookies and pass it to the context if available.
    alert_data = request.cookies.get('alert_data', None)
    if alert_data:
        alert = Alert.model_validate_json(alert_data)
        context.update({'alert': alert})
    return templates.TemplateResponse(request, 'users/profiles.html', context)


async def _user_profile(profile_id: str, page: int, size: int, db: AsyncSession):
    """
    A helper function that retrieves profile information and paginated project data for a specific user.

    Args:
        profile_id (str): The unique identifier of the user whose profile is being retrieved.
        page (int): The current page number for paginated projects.
        size (int): The number of projects to display per page.
        db (AsyncSession): The database session for performing async database operations.

    Returns:
        dict: A context dictionary containing:
            - 'profile': The user's profile data.
            - 'projects': The paginated list of the user's projects.
            - 'paginator': The pagination information for the user's projects.
    """
    user = await get_user(profile_id, db)
    user_projects = await get_user_projects(profile_id, db, page, size)
    total_projects = await count_obj(Project.project_id, db)

    projects_paginator = Paginator(
        page=page, size=size, total=total_projects)
    context = {'profile': user, 'projects': user_projects,
               'paginator': projects_paginator}
    return context


async def user_profile(request: Request):
    """
    Handles displaying a specific user's profile, including their skills, projects, or other related information,
    with pagination for the relevant content.

    Args:
        request (Request): The current HTTP request object, which includes path parameters, query parameters, and session state.

    Returns:
        TemplateResponse: Renders the user profile page with the requested profile's details and paginated data.

    """
    db = request.state.db
    profile_id: str = request.path_params['profile_id']
    page: int = max(int(request.query_params.get('page', 1)), 1)
    size: int = max(int(request.query_params.get('page', 9)), 9)

    # helper function to get profile, project associated with it, and a paginator for that projects.
    context = await _user_profile(profile_id, page, size, db)

    return templates.TemplateResponse(request, 'users/user-profile.html', context=context)


@requires('authenticated', redirect='login-page')
async def account(request: Request):
    """
    Handles the user's account dashboard view, showing their profile details and paginated list of their projects.

    Args:
        request (Request): The current HTTP request object, which includes user information and query parameters.

    Returns:
        TemplateResponse: Renders the user's account page with profile and project information.

    Workflow:
    - Retrieves the user's profile ID from the authenticated request.
    - Retrieves pagination parameters for the projects (defaults to page 1, size 9 if not provided).
    - Calls the helper function `_user_profile` to get the profile and paginated project data.
    - Renders the account dashboard template with the user's profile and project data.
    """
    db = request.state.db
    profile_id: str = request.user.profile_id
    page: int = max(int(request.query_params.get('page', 1)), 1)
    size: int = max(int(request.query_params.get('page', 9)), 9)

    # helper function to get profile, project associated with it, and a paginator for that projects.
    context = await _user_profile(profile_id, page, size, db)

    return templates.TemplateResponse(request, 'users/account.html', context=context)


@requires('authenticated', redirect='login-page')
async def edit_account(request: Request):
    """
    Handles the user's account editing functionality, allowing the user to update their profile details.

    Args:
        request (Request): The current HTTP request object, which includes form data and session state.

    Returns:
        TemplateResponse or RedirectResponse: Renders the edit form with any validation errors, or redirects to the account page upon successful update.

    Workflow:
    - Retrieves the user's current profile details from the database.
    - If the request is a POST, it validates and updates the user's profile details.
    - If validation errors occur, re-renders the form with errors.
    - On successful update, redirects the user back to their account page.
    """
    db = request.state.db
    profile_id = request.user.profile_id
    profile = await get_user(profile_id, db, with_skills=False)
    updated_profile = UpdateProfile(**profile.__dict__)

    if request.method == 'POST':
        form = await request.form()
        try:
            updated_profile = UpdateProfile(**form)
        except ValidationError as ex:
            # If validation fails, extract and display errors.
            errors = {item['loc'][0]: item['msg'] for item in ex.errors()}
            context = {'errors': errors, 'profile': updated_profile}
            return templates.TemplateResponse(request, 'users/edit-account.html', context)

        for key, value in updated_profile.model_dump().items():
            setattr(profile, key, value)

        await commit_db(db=db)
        redirect_url = request.url_for('account')
        return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(request, 'users/edit-account.html', {'profile': updated_profile})


@requires('authenticated', redirect='login-page')
async def edit_profile_image(request: Request):
    """
    Handles the updating of the user's profile image. Validates, compresses, and saves the new image.

    Args:
        request (Request): The current HTTP request object, which includes form data and session state.

    Returns:
        TemplateResponse or RedirectResponse: Renders the form with errors or redirects to the account page on success.

    Workflow:
    - Retrieves the user's profile information.
    - On POST, validates the new profile image, compresses it, and saves it.
    - Updates the profile with the new image path and removes the old image from storage.
    - Redirects the user to their account page upon successful update.
    """
    if request.method == 'POST':
        db = request.state.db
        profile_id = request.user.profile_id
        profile = await get_user(profile_id, db, with_skills=False)

        # Store the old image path for deletion after updating the profile.
        old_image_path = profile.profile_image
        async with request.form() as form:
            profile_image: UploadFile = form["profile_image"]

            # Save and compress the new image, updating the profile's image path.
            try:
                profile.profile_image = await save_and_compress_image(profile_image)
            except HTTPException as ex:
                errors = ex.detail
                return templates.TemplateResponse(request, 'users/edit-profile-image.html', {'errors': errors})

        await commit_db(db)

        remove_old_image(old_image_path)

        redirect_url = request.url_for('account')
        return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)

    # Handel the get request
    return templates.TemplateResponse(request, 'users/edit-profile-image.html')
