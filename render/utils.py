import os
from math import ceil
from uuid import UUID
from sqlalchemy import func, select, insert
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request, status, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from models import Profile, Project, Skill, Tag, project_tag
from users.auth import create_access_token
from database import get_db
from projects.projects import get_user_projects
from users.users import get_user
from projects.schemas import CreateProject
from config import logger, templates
from users.utils import save_and_compress_image
from render.schemas import ProjectSchema


class Paginator:
    def __init__(self, page, size, total):
        """
        Initialize the Paginator.

        :param page: The current page number (1-based).
        :param size: The number of items per page.
        :param total: The total number of items.
        """
        self.page_size = size
        self.current_page = page
        self.items = total
        self.pages = ceil(total / size)
        self.next_page = page + 1 if page < self.pages else None
        self.previous_page = page - 1 if page > 1 else None

    def pages_range(self, *, on_each_side=2, on_ends=2):
        """
        Generate a list of page numbers to display, including ellipses to shorten
        the range if the total number of pages is large.

        :param on_each_side: The number of pages to display on each side of the current page.
        :param on_ends: The number of pages to display at the beginning and end of the pagination range.
        :return: A list of page numbers and ellipses ('...') indicating skipped ranges.

        Example:
        If there are 20 pages and the current page is 10, with on_each_side=2 and on_ends=2, 
        the output would be:
        [1, 2, '...', 8, 9, 10, 11, 12, '...', 19, 20]
        """
        max_display = on_each_side * 2 + on_ends * 2 + 1

        # If the total number of pages is less than or equal to max_display, show all pages.
        if self.pages <= max_display:
            return list(range(1, self.pages + 1))

        # Calculate the start and end of the middle range around the current page.
        start = max(1, self.current_page - on_each_side)
        end = min(self.pages, self.current_page + on_each_side)

        middle = list(range(start, end + 1))

        # Determine the beginning of the range (with potential ellipsis).
        if start > on_ends + 1:
            beginning = list(range(1, on_ends + 1)) + ['...']
        else:
            beginning = list(range(1, start))

        # Determine the ending of the range (with potential ellipsis).
        if end < self.pages - on_ends:
            ending = ['...'] + \
                list(range(self.pages - on_ends + 1, self.pages + 1))
        else:
            ending = list(range(end + 1, self.pages + 1))

        # Combine the beginning, middle, and ending ranges.
        return beginning + middle + ending

    def __repr__(self):
        """
        Provide a string representation of the Paginator object.

        :return: A string representation of the paginator, showing its key properties.
        """
        return (f"Paginator(page_size={self.page_size}, current_page={self.current_page}, "
                f"items={self.items}, pages={self.pages}, "
                f"next_page={self.next_page}, previous_page={self.previous_page})")


async def count_obj(obj, db):
    stmt = select(func.count(obj))
    return await db.scalar(stmt)


class Alert:
    def __init__(self, msg: str, *, tag: str) -> None:
        self.msg = msg
        self.tag = tag


alerts: dict[str:Alert] = {}


def get_login_response(request: Request, user: Profile):
    token = create_access_token(
        username=user.username, user_id=str(user.profile_id))
    if request.query_params.get('next', False):
        redirect_url = request.query_params['next']
    else:
        redirect_url = request.url_for('profiles')

    response = RedirectResponse(
        url=redirect_url, status_code=status.HTTP_302_FOUND)
    # set the access token in Authorization header
    response.set_cookie(key="access_token", value=token,
                        httponly=True, secure=True)
    return response


async def _user_profile(profile_id: str, page: int, size: int, db: AsyncSession):
    # Trying to make all the queries called concurrently
    # db1 = await get_db().__anext__()
    # db2 = await get_db().__anext__()
    # db3 = await get_db().__anext__()
    # user_task = get_user(profile_id, db=db1)
    # projects_task = get_user_projects(
    #     user_id=profile_id, db=db2, page=page, size=size)
    # count_task = count_obj(Project.project_id, db=db3)

    # user, user_projects, total_projects = await gather(user_task, projects_task, count_task)

    user = await get_user(profile_id, db)
    user_projects = await get_user_projects(profile_id, db, page, size)
    total_projects = await count_obj(Project.project_id, db)

    projects_paginator = Paginator(
        page=page, size=size, total=total_projects)
    context = {'profile': user, 'projects': user_projects,
               'paginator': projects_paginator}
    return context


async def get_skill(skill_id: str, profile_id: str, db: AsyncSession) -> Skill:
    stmt = select(Skill).where(Skill.skill_id == UUID(skill_id)).where(
        Skill.owner_id == UUID(profile_id))
    return (await db.scalars(stmt)).first()


def _unread_count(messages): return sum(
    1 for message in messages if not message.is_read)


async def assign_tag(tag_name: str, project: Project, db: AsyncSession):
    # Check if the tag already exists
    tag_exist = (await db.scalars(select(Tag).where(Tag.name == tag_name))).first()

    if not tag_exist:
        tag = Tag(name=tag_name)
        # Associate the tag with the project
        tag.projects.append(project)
        db.add(tag)
    else:
        tag = tag_exist
        # Associate the existing tag with the project
        stmt = insert(project_tag).values(
            project_id=project.project_id, tag_id=tag.tag_id)
        await db.execute(stmt)

    # Commit the transaction
    await db.commit()


def remove_old_image(old_image_path: str):
    # Remove the old image if it's not the default image
    if old_image_path and old_image_path not in ('./static/images/default.jpg', './static/images/user-default.png'):
        try:
            os.remove(old_image_path)
        except OSError as e:
            logger.error(f"Error removing old image: {e}")


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
