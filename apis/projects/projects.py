from uuid import UUID
import os
from typing import Annotated
from fastapi import APIRouter, UploadFile, HTTPException, Query
from sqlalchemy import select, or_, desc
from base.database import db_dependency, commit_db
from base.models import Project, Tag, Profile
from base.config import logger
from apis.users.auth import user_dependency
from apis.users.utils import save_and_compress_image
from .schemas import CreateProject, UpdateProject
from .utils import _get_project
from sqlalchemy.orm import joinedload


router = APIRouter(prefix='/projects-api', tags=['projects'])


@router.get('/search/')
async def search_projects(db: db_dependency, project_title_or_tag: str | None = None,
                          page: Annotated[int, Query(ge=1)] = 1, size: Annotated[int, Query(ge=1)] = 9):
    start = (page - 1) * size
    stmt = select(Project).distinct().offset(
        start).limit(size).order_by(desc(Project.created)).options(
        joinedload(Project.tags),
        joinedload(Project.owner).load_only(Profile.username))

    if project_title_or_tag:
        var = f"%{project_title_or_tag}%"
        stmt = stmt.join(Project.tags).where(
            or_(
                Project.title.ilike(var),
                Tag.name.ilike(var)
            )
        )

    projects = (await db.scalars(stmt)).unique().all()
    return projects


@router.get('/user-projects/{user_id}')
async def get_user_projects(user_id: str, db: db_dependency,
                            page: Annotated[int, Query(ge=1)] = 1,
                            size: Annotated[int, Query(ge=1)] = 10):
    start = (page - 1) * size
    stmt = select(Project).where(Project.owner_id == UUID(user_id)).offset(
        start).limit(size).order_by(Project.created).options(joinedload(
            Project.tags))

    projects = (await db.scalars(stmt)).unique().all()
    return projects


@router.get('/{project_id}')
async def get_project(project_id: str, db: db_dependency):
    stmt = select(Project).options(joinedload(
        Project.tags)).options(joinedload(Project.owner).load_only(Profile.username)).where(Project.project_id == UUID(project_id))
    project = (await db.scalars(stmt)).first()

    return project


@router.post('/', status_code=201)
async def create_project_api(project: CreateProject, user: user_dependency, db: db_dependency):
    project = Project(**project.model_dump(), owner_id=UUID(user['user_id']))
    db.add(project)
    await commit_db(db)
    await db.refresh(project)
    return project


@router.put('/{project_id}')
async def Update_project(project_id: str, updated_project: UpdateProject,
                         user: user_dependency, db: db_dependency):
    """
    This endpoint allows users to update their projects information. 
    If a field is not provided, the existing value for that field will remain unchanged.
    But if provided with null value it will put it's value to null.
    """
    project = await _get_project(project_id, db)
    if project.owner_id != UUID(user['user_id']):
        raise HTTPException(401, "You're not authorized to edit this project!")

    for key, value in updated_project.model_dump().items():
        setattr(project, key, value)
    await commit_db(db=db)


@router.put('/{project_id}/project-image')
async def Update_project_image(image: UploadFile, project_id: str,
                               user: user_dependency, db: db_dependency):
    '''
    Updates the project featured image.

    Steps:
    1. Retrieve the profile associated with the logged-in user.
    2. Validate the uploaded image's file type and size, then compress the image.
        - Allowed file types: 'png', 'jpg', 'jpeg', 'gif'.
        - Maximum size: 10 MB.
        - Ensure it is an actual image file.
    3. Save the compressed image to the designated directory with a unique filename.
    4. Update the user's profile with the new image path in the database.
    5. Commit the changes to the database.
    6. Delete the old profile image file if it exists and is not the default image.
    '''
    # Note: Error handling occurs within the called functions.
    project = await _get_project(project_id, db)
    if project.owner_id != UUID(user['user_id']):
        raise HTTPException(401, "You're not authorized to edit this project!")

    old_image_path = project.featured_image

    # Validate, compress, and save the image, then update the profile with the new image path
    project.featured_image = await save_and_compress_image(image)
    await db.commit()

    # Remove the old image if it's not the default image
    if old_image_path and old_image_path not in ('images/default.jpg', 'images/user-default.png'):
        try:
            os.remove(old_image_path)
        except OSError as e:
            logger.error(f"Error removing old image: {e}")


@router.delete('/{project_id}')
async def delete_project(project_id: str, user: user_dependency, db: db_dependency):
    project = await _get_project(project_id, db)
    if project.owner_id != UUID(user['user_id']):
        raise HTTPException(401, "You're not authorized to edit this project!")

    # Delete the profile image if present
    if project.featured_image and project.featured_image != '/static/images/default.jpg':
        try:
            os.remove(project.featured_image)
        except OSError as e:
            logger.error(f"Error removing old image: {e}")

    await db.delete(user)
    await commit_db(db)
