from uuid import UUID
from fastapi import status, HTTPException, UploadFile, Request
from fastapi.responses import RedirectResponse, Response
from starlette.authentication import requires
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from models import Project, Review
from config import templates
from users.users import get_user
from projects.projects import get_project, search_projects, create_project_api
from projects.reviews import get_Project_reviews
from projects.tags import delete_tag_api
from .utils import Paginator, count_obj, assign_tag, remove_old_image, handle_project_data
from render.schemas import ProjectSchema
from database import commit_db


async def projects(request: Request):
    db = request.state.db
    page = max(int(request.query_params.get('page', 1)), 1)
    size = max(int(request.query_params.get('size', 9)), 9)
    search_query = request.query_params.get('search_query', None)

    projects = await search_projects(db, search_query, page, size)
    projects_count = await count_obj(Project.project_id, db)

    paginator = Paginator(page, size, projects_count)

    context = {'projects': projects, 'paginator': paginator,
               'search_query': search_query}
    return templates.TemplateResponse(request, 'projects/projects.html', context)


async def project(request: Request):
    db = request.state.db
    project_id = request.path_params['project_id']
    page = max(int(request.query_params.get('page', 1)), 1)
    size = max(int(request.query_params.get('size', 10)), 10)

    already_reviewed = False
    if request.user.is_authenticated:
        stmt = select(Review).where(Review.project_id == UUID(project_id)).where(
            Review.owner_id == UUID(request.user.profile_id))
        already_reviewed = True if await db.scalar(stmt) else False
        if not already_reviewed and request.method == "POST":
            form = await request.form()
            review = Review(**form, project_id=UUID(project_id),
                            owner_id=UUID(request.user.profile_id))
            db.add(review)
            await commit_db(db)
            already_reviewed = True

    project = await get_project(project_id, db)
    project_reviews = await get_Project_reviews(project_id, db, page, size)
    stmt = select(func.count(Review.review_id)).where(
        Review.project_id == UUID(project_id))
    total_reviews = await db.scalar(stmt)
    paginator = Paginator(page, size, total_reviews)

    context = {'project': project, 'project_reviews': project_reviews,
               'paginator': paginator, 'already_reviewed': already_reviewed}

    return templates.TemplateResponse(request, 'projects/single-project.html', context)


@requires('authenticated', redirect='login-page')
async def create_project(request: Request):
    """
    Handles the creation of a new project by authenticated users.

    - For GET requests: Renders a form to create a new project.
    - For POST requests: Validates form data, handles image uploads, and saves the project to the database.

    Parameters:
    -----------
    request : Request
        The incoming HTTP request object.

    Returns:
    --------
    TemplateResponse or RedirectResponse
        - On GET requests: Renders the form for creating a project.
        - On POST success: Redirects to the newly created project's page.
        - On POST failure: Renders the form with validation errors.
    """
    if request.method == 'POST':
        db: AsyncSession = request.state.db
        result = await handle_project_data(request)

        # Check if the result is a TemplateResponse (indicating an error)
        if isinstance(result, Response):
            return result

        # Extract the validated project content and image path from the result
        project_content: ProjectSchema = result['project_content']
        image_path = result['image_path']

        # Creating the project object
        project = Project(**project_content.model_dump(),
                          owner_id=UUID(request.user.profile_id))
        if image_path:
            project.featured_image = image_path

        # Add project to the database
        db.add(project)
        await commit_db(db)
        await db.refresh(project)

        # Handle new tags
        form = await request.form()
        if 'newtags' in form:
            tags = form['newtags'].split()
            for tag in tags:
                await assign_tag(tag, project, db)

        # Redirect to the newly created project page
        return RedirectResponse(request.url_for('project', project_id=project.project_id), status_code=302)

    # Render form for GET request
    return templates.TemplateResponse(request, 'projects/project-form.html')


@requires('authenticated', redirect='login-page')
async def update_project(request: Request):
    """
    Handles updating an existing project for authenticated users.

    - For GET requests: Renders the form to update a project.
    - For POST requests: Validates form data, handles image uploads, updates the project, and saves it to the database.

    Parameters:
    -----------
    request : Request
        The incoming HTTP request object.

    Returns:
    --------
    TemplateResponse or RedirectResponse
        - On GET requests: Renders the form to update the project.
        - On POST success: Redirects to the updated project's detail page.
        - On POST failure: Renders the form with validation errors.
    """
    db: AsyncSession = request.state.db
    project_id = request.path_params.get('project_id')
    project = await get_project(project_id, db)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if request.method == "POST":
        result = await handle_project_data(request)

        # Check if the result is a TemplateResponse (indicating an error)
        if isinstance(result, Response):
            return result

        project_content: ProjectSchema = result['project_content']
        image_path = result['image_path']

        for key, value in project_content.model_dump().items():
            setattr(project, key, value)

        # Set new image and remove old one, if applicable
        if image_path:
            remove_old_image(project.featured_image)
            project.featured_image = image_path

        form = await request.form()
        if 'newtags' in form:
            tags = form['newtags'].split()
            for tag in tags:
                await assign_tag(tag, project, db)

        await commit_db(db=db)

       # Redirect to the project's detail page after successful update
        return RedirectResponse(request.url_for('project', project_id=project.project_id), status_code=302)

    # Handle GET request - Render the form with the existing project data
    return templates.TemplateResponse(request, 'projects/project-form.html', {'project': project})


async def delete_project(request: Request):
    project_id = request.path_params.get('project_id')
    db: AsyncSession = request.state.db
    project = await get_project(project_id, db)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if request.method == 'POST':
        await db.delete(project)
        await commit_db(db)

        return RedirectResponse(request.url_for('account'), status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(request, 'delete.html', {'object': project.title})


@requires('authenticated', redirect='login-page')
async def delete_tag(request: Request):
    db: AsyncSession = request.state.db
    project_id = request.path_params.get('project_id')
    tag_id = request.path_params.get('tag_id')
    await delete_tag_api(tag_id, project_id, {'user_id': request.user.profile_id}, db)

    return RedirectResponse(request.url_for('update-project', project_id=project_id), status_code=302)
