from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import db_dependency, commit_db
from models import Skill
from config import logger
from .auth import user_dependency
from .schemas import SkillSchema
from .users import get_user


router = APIRouter(prefix='/skills', tags=['skills'])


@router.get('/{skill_id}')
async def get_skill(skill_id: str, user: user_dependency, db: db_dependency):
    profile = await get_user(user['user_id'], db)
    stmt = select(Skill).where(Skill.skill_id == UUID(skill_id)).where(
        Skill.owner_id == profile.profile_id)
    skill = (await db.scalars(stmt)).first()
    if not skill:
        raise HTTPException(
            status_code=404, detail='Could not find the skill.')
    return skill


@router.get('/all/{profile_id}')
async def get_all_skills(profile_id: str, db: db_dependency):
    stmt = select(Skill).where(
        Skill.owner_id == UUID(profile_id))
    skills = (await db.scalars(stmt)).all()

    return skills


@router.post('/me/skill', status_code=status.HTTP_201_CREATED)
async def add_skill(skill: SkillSchema, user: user_dependency, db: db_dependency):
    profile = await get_user(user['user_id'], db)
    skill = Skill(**skill.model_dump(), owner_id=profile.profile_id)
    db.add(skill)
    await commit_db(db=db)
    await db.refresh(skill)
    return skill


@router.put('/me/skill/{skill_id}', status_code=status.HTTP_204_NO_CONTENT)
async def update_skill_api(skill_id: str, updated_skill: SkillSchema, user: user_dependency, db: db_dependency):
    """
    If the description field is not provided, the existing value remain unchanged.
    If it is provided with a null value, it will be set to null.
    """
    skill = await get_skill(skill_id, user, db)  # error handling occurs in get_skill
    for key, value in updated_skill.model_dump().items():
        setattr(skill, key, value)
    await commit_db(db=db)


@router.delete('/me/skill/{skill_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(skill_id: str, user: user_dependency, db: db_dependency):
    # error handling occurs in get_skill
    skill = await get_skill(skill_id, user, db)
    await db.delete(skill)
    await commit_db(db)
