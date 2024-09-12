import os
from database import db_dependency, commit_db
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from models import Project, Review
from fastapi import HTTPException
from config import logger


async def _get_project(project_id: str, db: db_dependency):
    stmt = select(Project).where(Project.project_id == UUID(project_id))
    project = (await db.scalars(stmt)).first()
    return project


async def update_votes(project_id: str, db: AsyncSession):
    """Update the vote ratio for a project based on the count of 'up' reviews."""
    stmt = select(func.count(Review.review_id)).where(Review.project_id ==
                                                      UUID(project_id), Review.value == 'up')
    up_votes = await db.scalar(stmt)
    project = await _get_project(project_id, db)
    # total votes calculated by a trigger in the db
    project.update_vote_ratio(up_votes)
    await commit_db(db)


# async def change_project_image(project: Project, new_image_path: str, db: AsyncSession):
#     old_image_path = project.featured_image

#     # Validate, compress, and save the image, then update the profile with the new image path
#     project.featured_image = new_image_path
#     await commit_db(db)

#     # Remove the old image if it's not the default image
#     if old_image_path and old_image_path != '/static/images/default.jpg':
#         try:
#             os.remove(old_image_path)
#         except OSError as e:
#             logger.error(f"Error removing old image: {e}")
