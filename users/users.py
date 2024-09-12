import os
from typing import Annotated
from fastapi import APIRouter, status, HTTPException, Depends, UploadFile, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from database import db_dependency, commit_db
from models import Profile, Skill
from .schemas import CreateProfile, Token, UpdateProfile, SendProfile
from .validators import user_validation
from .auth import bcrypt_context, authenticate_user, create_access_token, create_refresh_token, get_current_user, user_dependency
from uuid import UUID
from config import logger
from .utils import save_and_compress_image


router = APIRouter(prefix='/users-api', tags=['users-api'])


# async def get_all_skills(profile_id: str, db):
# stmt = select(Skill.skill_id, Skill.name, Skill.description).where(
#     Skill.owner_id == UUID(profile_id))
# result = (await db.execute(stmt)).all()
# skills = []
# for row in result:
#     skills.append(
#         {'skill_id': row[0], "name": row[1], 'description': row[2]})

# return skills


@router.get('/')
async def get_user(profile_id: str, db: db_dependency, with_skills: bool = True):
    stmt = select(Profile).where(
        Profile.profile_id == UUID(profile_id))
    if with_skills:
        stmt = select(Profile).options(joinedload(Profile.skills)).where(
            Profile.profile_id == UUID(profile_id))
    user = (await db.scalars(stmt)).first()
    if not user:
        raise HTTPException(
            status_code=404, detail='Could not found your profile')
    return user


@router.get('/search/')
async def search_users(db: db_dependency, username: str | None = None,
                       skill: str | None = None, page: Annotated[int, Query(ge=1)] = 1,
                       size: Annotated[int, Query(ge=1)] = 10):
    """
    Retrieve users profile with optional filters for username and skill.

    Returns:
        List[Profile]: A list of user profiles matching the filters.
    """
    start = (page - 1) * size
    stmt = select(Profile).options(joinedload(Profile.skills)).offset(
        start).limit(size)
    if username:
        stmt = stmt.where(Profile.username.ilike(f'%{username}%'))
    if skill:
        stmt = stmt.join(Profile.skills).where(Skill.name == skill)

    profiles = (await db.scalars(stmt)).unique().all()
    return profiles


@router.post('/', status_code=status.HTTP_201_CREATED)
async def create_user(user: CreateProfile, db: db_dependency):
    # errors = await user_validation(username=profile.username, email=profile.email, password=profile.password, db=db)
    # if errors:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST, detail=errors)

    new_user = Profile(**user.model_dump())
    new_user.password = bcrypt_context.hash(new_user.password)
    db.add(new_user)
    await commit_db(db=db)
    await db.refresh(new_user)

    return new_user


@router.post('/token', status_code=status.HTTP_200_OK, response_model=Token, name='token')
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: db_dependency):
    user: Profile = await authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(user.profile_id, user.username)
    refresh_token = create_refresh_token(user.profile_id, user.username)
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
async def refresh_access_token(refresh_token: str):
    user = get_current_user(refresh_token)
    if user:
        new_access_token = create_access_token(
            user['user_id'], user['username'])
        return {"access_token": new_access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.put('/', status_code=status.HTTP_204_NO_CONTENT)
async def update_profile(updated_profile: UpdateProfile, user: user_dependency, db: db_dependency) -> None:
    '''
    Updates the user's profile

    This endpoint allows users to update their profile information. 
    If a field is not provided, the existing value for that field will remain unchanged.
    But if provided with null value it will put it's value to null.

     Example:
    ```
    PUT /my-profile/
    {
        "location": "Some_place",
        "short_intro": "Intro",
        "bio": null
    }
    ```
    In this example, only `location`, `short_intro`, and `bio` fields will be updated in the user's profile.
    Any other fields that are not included in the request will remain unchanged.
    '''
    profile: Profile = await get_user(user['user_id'], db)
    for key, value in updated_profile.model_dump().items():
        setattr(profile, key, value)
    await commit_db(db=db)


@router.put('/profile-image', status_code=status.HTTP_204_NO_CONTENT)
async def update_profile_image(image: UploadFile, user: user_dependency, db: db_dependency) -> None:
    '''
    Updates the user's profile image.

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

    # Get the user profile
    profile: Profile = await get_user(user['user_id'], db, with_skills=False)
    old_image_path = profile.profile_image

    # Validate, compress, and save the image, then update the profile with the new image path
    profile.profile_image = await save_and_compress_image(image)
    await commit_db(db)

    # Remove the old image if it's not the default image
    if old_image_path and old_image_path not in ('/images/default.jpg', '/images/user-default.png'):
        try:
            os.remove(old_image_path)
        except OSError as e:
            logger.error(f"Error removing old image: {e}")


@router.delete('/', status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user: user_dependency, db: db_dependency):
    user = await get_user(user['user_id'], db)

    # Delete the profile image if present
    if user.profile_image and user.profile_image != '/static/images/default.jpg':
        try:
            os.remove(user.profile_image)
        except OSError as e:
            logger.error(f"Error removing old image: {e}")

    await db.delete(user)
    await commit_db(db)
