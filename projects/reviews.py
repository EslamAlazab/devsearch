from uuid import UUID
from typing import Annotated
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from database import db_dependency, commit_db
from models import Review, Profile
from users.auth import user_dependency
from .schemas import ReviewSchema
from .utils import update_votes


router = APIRouter(prefix='/projects/reviews', tags=['reviews'])


@router.get('/')
async def get_Project_reviews(project_id: str, db: db_dependency, page: Annotated[int, Query(ge=1)] = 1,
                              size: Annotated[int, Query(ge=1)] = 10):
    """
    Get all reviews for a specific project.

    Returns:
        list: A list of reviews for the project.
    """
    start = (page - 1) * size
    stmt = select(Review).where(Review.project_id == UUID(project_id)).offset(
        start).limit(size).options(joinedload(Review.owner).load_only(Profile.username, Profile.profile_image))
    reviews = (await db.scalars(stmt)).all() or []
    return reviews


@router.get('/my-review/')
async def get_my_review(review_id: str, user: user_dependency,
                        db: db_dependency):
    """
    Get a specific review by its ID for the authenticated user.

    Returns:
        Review: The review object if found.

    Raises:
        HTTPException: If the review is not found.
    """
    stmt = select(Review).where(Review.review_id == review_id,
                                Review.owner_id == UUID(user['user_id']))
    review = (await db.scalars(stmt)).first()
    if not review:
        raise HTTPException(404, 'Could not find the review!')

    return review


@router.post('/', status_code=201)
async def create_review(project_id: str, review: ReviewSchema,
                        user: user_dependency, db: db_dependency):
    """
    Create a new review for a project by the authenticated user.

    Returns:
        Review: The created review object.

    Raises:
        HTTPException: If the user has already reviewed the project.
    """
    # Check if the user already has a review for this project
    stmt = select(Review).where(Review.project_id == UUID(
        project_id), Review.owner_id == UUID(user['user_id']))
    existing_review = (await db.scalars(stmt)).first()

    if existing_review:
        raise HTTPException(
            status_code=400, detail="User has already reviewed this project.")

    # If no existing review, create a new one
    review = Review(** review.model_dump(), owner_id=UUID(user['user_id']),
                    project_id=UUID(project_id))
    db.add(review)
    await commit_db(db)

    await update_votes(project_id, db)

    await db.refresh(review)
    return review


@router.put('/', status_code=204)
async def update_review(review_id: str, updated_review: ReviewSchema,
                        user: user_dependency, db: db_dependency):
    """
    Update an existing review by its ID for the authenticated user.

    Returns:
        None
    """
    review = await get_my_review(UUID(review_id), user, db)

    for key, value in updated_review.model_dump().items():
        setattr(review, key, value)

    await commit_db(db)
    await update_votes(str(review.project_id), db)


@router.delete('/', status_code=204)
async def delete_review(review_id: str, user: user_dependency,
                        db: db_dependency):
    """
    Delete a review by its ID for the authenticated user.

    Returns:
        None
    """
    review = await get_my_review(UUID(review_id), user, db)

    await db.delete(review)
    await commit_db(db)
    await update_votes(str(review.project_id), db)
