from password_validator import PasswordValidator
from pydantic import BaseModel, EmailStr, ValidationError
from models import Profile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


class Email(BaseModel):
    email: EmailStr


async def username_validator(username: str, db: AsyncSession) -> list[str]:
    errors = []
    stmt = select(Profile.username).where(Profile.username == username)
    if (await db.scalars(stmt)).first():
        errors.append('Username used before!')
    return errors


async def email_validator(email: str, db: AsyncSession) -> list[str]:
    errors = []
    stmt = select(Profile.email).where(Profile.email == email)
    if (await db.scalars(stmt)).first():
        errors.append('Email used before!')

    try:
        email = Email(email=email)
    except ValidationError as ex:
        errors.append(ex.errors()[0]['msg'])
    return errors


def password_validator(password: str) -> list[str]:
    schema = PasswordValidator
    errors = []

    if not schema().min(8).validate(password):
        errors.append('Password must be at least 8 characters.')
    if not schema().max(50).validate(password):
        errors.append('Password must not exceed 50 characters.')
    if not schema().has().uppercase().validate(password):
        errors.append('Password must contain at least one uppercase letter.')
    if not schema().has().lowercase().validate(password):
        errors.append('Password must contain at least one lowercase letter.')
    if not schema().has().digits().validate(password):
        errors.append('Password must contain at least one digit.')
    if not schema().has().no().spaces().validate(password):
        errors.append('Password must not contain spaces.')
    if not schema().has().symbols().validate(password):
        errors.append('Password must contain at least one symbol.')

    return errors


async def user_validation(username: str, email: str, password: str, db: AsyncSession) -> dict[str, list]:
    errors = {}
    username_err = await username_validator(username, db)
    if username_err:
        errors['username'] = username_err
    email_err = await email_validator(email, db)
    if email_err:
        errors['email'] = email_err
    password_err = password_validator(password)
    if password_err:
        errors['password'] = password_err

    return errors
