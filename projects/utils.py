from database import db_dependency, commit_db
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from models import Project, Review
from fastapi import HTTPException


async def _get_project(project_id: str, db: db_dependency):
    stmt = select(Project).where(Project.project_id == UUID(project_id))
    project = (await db.scalars(stmt)).first()
    if not project:
        raise HTTPException(404, 'Could not find the project!')
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
