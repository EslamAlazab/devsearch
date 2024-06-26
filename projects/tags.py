from uuid import UUID
from fastapi import APIRouter, HTTPException
from sqlalchemy import select, delete, insert
from database import db_dependency, commit_db
from models import Tag, Project, project_tag
from users.auth import user_dependency
from .utils import _get_project


router = APIRouter(prefix='/projects/tags', tags=['tags'])


@router.get('/', status_code=201)
async def get_project_tags(project_id: str, db: db_dependency):
    stmt = select(Tag).where(Tag.projects.any(
        Project.project_id == UUID(project_id)))
    tags = (await db.scalars(stmt)).all() or []
    return tags


@router.post('/')
async def post_tag(tag_name: str, project_id: str, user: user_dependency, db: db_dependency):
    # Retrieve the project
    project = await _get_project(project_id, db)
    if project.owner_id != UUID(user['user_id']):
        raise HTTPException(
            status_code=401, detail="You're not authorized to add tags to this project!")

    # Check if the tag already exists
    tag_exist = (await db.scalars(select(Tag).where(Tag.name == tag_name))).first()
    print(tag_exist.__dict__)

    if not tag_exist:
        tag = Tag(name=tag_name)
        # Associate the tag with the project
        tag.projects.append(project)
        db.add(tag)
    else:
        tag = tag_exist
        # Associate the existing tag with the project
        stmt = insert(project_tag).values(
            project_id=UUID(project_id), tag_id=tag.tag_id)
        await db.execute(stmt)

    # Commit the transaction
    await db.commit()
    await db.refresh(tag)

    return tag


@router.delete('/')
async def delete_tag(tag_id: str, project_id: str, user: user_dependency, db: db_dependency):
    # verify the owner, and project
    stmt = select(Project.owner_id).join(Project.tags).where(
        Project.project_id == UUID(project_id),
        Tag.tag_id == UUID(tag_id))
    owner_id = await db.scalar(stmt)
    if not owner_id:
        raise HTTPException(status_code=404, detail="Tag not found!")

    if user['user_id'] != str(owner_id):
        raise HTTPException(
            401, "You're not authorized to delete tags from this project!")

    # Delete the association
    await db.execute(delete(project_tag).where(
        project_tag.c.project_id == UUID(project_id),
        project_tag.c.tag_id == UUID(tag_id)
    ))

    # Check if there are any other associations for the tag
    stmt = select(project_tag).where(project_tag.c.tag_id == UUID(tag_id))
    result = await db.execute(stmt)
    another_association = result.scalar_one_or_none()

    # If there are no other associations, delete the tag itself
    if not another_association:
        await db.execute(delete(Tag).where(Tag.tag_id == UUID(tag_id)))

    await commit_db(db)
