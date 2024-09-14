from uuid import UUID
from fastapi import status, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from starlette.authentication import requires
from sqlalchemy import func, select, insert
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from base.models import Project, Review, Tag, project_tag
from base.config import templates
from apis.projects.projects import get_project, search_projects
from apis.projects.reviews import get_Project_reviews
from apis.projects.tags import delete_tag_api
from apis.users.utils import save_and_compress_image
from render.utils import Paginator, count_obj, remove_old_image
from render.schemas import ProjectSchema
from base.database import commit_db


async def projects(request: Request):
    """
    Handles listing projects with pagination and optional search functionality.

    Args:
        request (Request): The HTTP request object containing query parameters.

    Returns:
        TemplateResponse: Renders the 'projects/projects.html' template with a paginated list of projects.

    Workflow:
    - Retrieves the page number, page size, and optional search query from the request.
    - Queries the database for projects based on the search query and pagination.
    - Fetches the total count of projects to handle pagination.
    - Builds a paginator object to manage the current page's data.
    - Returns a rendered HTML template displaying the projects and paginator information.
    """
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
    """
    Displays a single project's details, its reviews, and allows authenticated users to add a review.

    Args:
        request (Request): The HTTP request object containing path and query parameters.

    Returns:
        TemplateResponse: Renders the 'projects/single-project.html' template displaying project details and reviews.

    Workflow:
    - Retrieves the project ID and handles pagination for reviews.
    - If the user is authenticated, checks if they have already reviewed the project.
    - Allows the user to submit a new review if they haven't already.
    - Fetches the project details and paginated reviews.
    - Returns a rendered HTML template displaying the project's details, reviews, and pagination.
    """
    db = request.state.db
    project_id = request.path_params['project_id']
    page = max(int(request.query_params.get('page', 1)), 1)
    size = max(int(request.query_params.get('size', 10)), 10)

    # Check if the authenticated user has already reviewed this project
    already_reviewed = False
    if request.user.is_authenticated:
        stmt = select(Review).where(Review.project_id == UUID(project_id)).where(
            Review.owner_id == UUID(request.user.profile_id))
        already_reviewed = True if await db.scalar(stmt) else False

        # Handle review submission if the user has not already reviewed the project
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


async def handle_project_data(request: Request):
    """
    Handles form data submitted for creating or updating a project,
    including validation and optional image uploads.

    Parameters:
    -----------
    request : Request
        The incoming HTTP request containing form data.

    Returns:
    --------
    dict:
        A dictionary containing the validated project content and the processed image path.
    TemplateResponse:
        If form validation or image processing fails, it returns a TemplateResponse with errors ready to be sent.

    Behavior:
    ---------
    - Validates the form data using the ProjectSchema model.
    - Processes and compresses the uploaded image if provided.
    - Returns validation errors and stops execution if validation fails.
    """

    # Extract the form data from the request
    form = await request.form()
    form_data = {key: value for key, value in form.items() if value}

    # Validate the form data using ProjectSchema
    try:
        project_content = ProjectSchema(**form_data)
    except ValidationError as ex:
        # Catch validation errors, prepare error messages, and return them to the form template
        errors = {item['loc'][0]: item['msg'] for item in ex.errors()}
        context = {'errors': errors}
        return templates.TemplateResponse(request, 'projects/project-form.html', context)

    # Handle image upload if a featured image is present in the form data
    image_path = None
    if 'featured_image' in form:  # Ensure 'featured_image' is in the form
        project_image: UploadFile = form['featured_image']
        if project_image.filename:  # Check if an image file is provided
            try:
                # Process and compress the uploaded image
                image_path = await save_and_compress_image(project_image)
            except HTTPException as ex:
                # Catch exceptions during image handling and return errors
                errors = {'featured_image': ex.detail}
                context = {'errors': errors, 'project': project_content}
                return templates.TemplateResponse(request, 'projects/project-form.html', context)

    # Return the validated project content and the processed image path
    return {'project_content': project_content, 'image_path': image_path}


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
    """
    Handles the deletion of a project.

    Args:
        request (Request): The HTTP request object containing the project ID.

    Returns:
        TemplateResponse or RedirectResponse: If the request method is GET, renders the confirmation page;
        If the request method is POST, deletes the project and redirects the user to the account page.

    Raises:
        HTTPException: If the project is not found in the database.
    """
    project_id = request.path_params.get('project_id')
    db: AsyncSession = request.state.db
    project = await get_project(project_id, db)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if request.method == 'POST':
        await db.delete(project)
        await commit_db(db)

        return RedirectResponse(request.url_for('account'), status_code=status.HTTP_302_FOUND)

    # Render confirmation page if GET request
    return templates.TemplateResponse(request, 'delete.html', {'object': project.title})


async def assign_tag(tag_name: str, project: Project, db: AsyncSession):
    """
    Assigns a tag to a project. If the tag doesn't exist, it creates a new tag and associates it with the project.

    Args:
        tag_name (str): The name of the tag to assign.
        project (Project): The project to associate the tag with.
        db (AsyncSession): The database session for querying and updating the database.

    Workflow:
    - Check if the tag exists in the database.
    - If it doesn't exist, create the tag and associate it with the project.
    - If it exists, create an entry in the association table to link the tag with the project.
    - Commits the changes to the database.
    """
    # Check if the tag already exists
    tag_exist = (await db.scalars(select(Tag).where(Tag.name == tag_name))).first()

    if not tag_exist:
        tag = Tag(name=tag_name)
        tag.projects.append(project)  # Associate the tag with the project
        db.add(tag)
    else:
        tag = tag_exist
        # If tag exists, create the association with the project
        stmt = insert(project_tag).values(
            project_id=project.project_id, tag_id=tag.tag_id)
        await db.execute(stmt)

    await db.commit()


@requires('authenticated', redirect='login-page')
async def delete_tag(request: Request):
    """
    Deletes a tag from a project.

    Args:
        request (Request): The HTTP request object containing path parameters (project ID and tag ID).

    Returns:
        RedirectResponse: Redirects to the project update page after the tag has been deleted.

    Workflow:
    - Fetches the project and tag IDs from the request path parameters.
    - Calls an API helper to delete the tag from the project.
    - Redirects to the project update page after deletion.
    """
    db: AsyncSession = request.state.db
    project_id = request.path_params.get('project_id')
    tag_id = request.path_params.get('tag_id')
    await delete_tag_api(tag_id, project_id, {'user_id': request.user.profile_id}, db)

    return RedirectResponse(request.url_for('update-project', project_id=project_id), status_code=302)
