from uuid import UUID
from fastapi import status, Request
from fastapi.responses import RedirectResponse
from starlette.authentication import requires
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from base.models import Skill
from base.database import commit_db
from base.config import templates


@requires('authenticated', redirect='login-page')
async def create_skill(request: Request):
    """
    Handles the creation of a new skill for the authenticated user.

    Args:
        request (Request): The current HTTP request object, which includes form data and session state.

    Returns:
        RedirectResponse or TemplateResponse:
            - Redirects to the account page if the skill is successfully created.
            - Renders the skill form template if accessed via GET request.

    Workflow:
    - For POST requests:
        - Retrieves form data and creates a new `Skill` object with the form data and the current user's profile ID as the owner.
        - Adds the new skill to the database and commits the transaction.
        - Redirects to the account page.
    - For GET requests:
        - Renders the skill form template for skill creation.

    Security:
    - Requires authentication to access the skill creation functionality.
    """
    if request.method == 'POST':
        db = request.state.db
        form = await request.form()
        skill = Skill(**form, owner_id=UUID(request.user.profile_id))
        db.add(skill)
        await db.commit()

        redirect_url = request.url_for('account')
        return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(request, 'users/skill-form.html')


async def get_skill(skill_id: str, profile_id: str, db: AsyncSession) -> Skill | None:
    """
    Retrieves a specific skill belonging to a user by skill ID and profile ID.

    Args:
        skill_id (str): The unique ID of the skill to be retrieved.
        profile_id (str): The profile ID of the skill's owner to ensure ownership.
        db (AsyncSession): The database session used to execute the query.
    """
    stmt = select(Skill).where(Skill.skill_id == UUID(skill_id)).where(
        Skill.owner_id == UUID(profile_id))
    return (await db.scalars(stmt)).first()


@requires('authenticated', redirect='login-page')
async def update_skill(request: Request):
    """
    Handles the update of an existing skill for the authenticated user.

    Args:
        request (Request): The current HTTP request object, which includes form data, path parameters, and session state.

    Returns:
        RedirectResponse or TemplateResponse:
            - Redirects to the account page if the skill is successfully updated.
            - Renders the skill form template with the current skill data if accessed via GET request.

    Workflow:
    - Retrieves the skill to be updated based on the skill ID from the path parameters and the current user's profile ID.
    - For POST requests:
        - Updates the skill's attributes with the form data.
        - Commits the changes to the database.
        - Redirects to the account page.
    - For GET requests:
        - Renders the skill form template with the current skill data for updating.

    Security:
    - Requires authentication to access the skill update functionality.
    - Ensures the user can only update skills they own.
    """
    db = request.state.db
    skill = await get_skill(request.path_params['skill_id'], request.user.profile_id, db)

    if request.method == 'POST':
        form = await request.form()
        for key, value in form.items():
            setattr(skill, key, value)
        await commit_db(db=db)
        redirect_url = request.url_for('account')
        return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(request, 'users/skill-form.html', {'skill': skill})


@requires('authenticated', redirect='login-page')
async def delete_skill(request: Request):
    """
    Handles the deletion of a skill for the authenticated user.

    Args:
        request (Request): The current HTTP request object, which includes path parameters and session state.

    Returns:
        RedirectResponse or TemplateResponse:
            - Redirects to the account page if the skill is successfully deleted.
            - Renders a confirmation template for the deletion if accessed via GET request.

    Workflow:
    - Retrieves the skill to be deleted based on the skill ID from the path parameters and the current user's profile ID.
    - For POST requests:
        - Deletes the skill from the database and commits the transaction.
        - Redirects to the account page.
    - For GET requests:
        - Renders a confirmation template for the deletion.

    Security:
    - Requires authentication to access the skill deletion functionality.
    - Ensures the user can only delete skills they own.
    """
    db = request.state.db
    skill = await get_skill(request.path_params['skill_id'], request.user.profile_id, db)

    if request.method == 'POST':
        await db.delete(skill)
        await commit_db(db)

        redirect_url = request.url_for('account')
        return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(request, 'delete.html', {'object': skill.name})
