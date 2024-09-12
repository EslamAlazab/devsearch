from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from models import Profile
from sqlalchemy import select, or_
from jose import jwt, JWTError
import datetime
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_TIMEDELTA, REFRESH_TOKEN_EXPIRE_TIMEDELTA
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer


bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_bearer = OAuth2PasswordBearer(tokenUrl='users-api/token')


async def authenticate_user(username_or_email: str, password: str, db: AsyncSession):
    stmt = select(Profile).where(
        or_(Profile.username == username_or_email, Profile.email == username_or_email))
    user: Profile = (await db.scalars(stmt)).first()
    if user and bcrypt_context.verify(password, user.password):
        return user
    return False


def gen_token(user_id: str, username: str, expires_delta: datetime.timedelta) -> str:
    expires = datetime.datetime.now(datetime.UTC) + expires_delta
    encode = {'sub': username, 'id': str(user_id), 'exp': expires}
    return jwt.encode(encode, key=SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: str, username: str) -> str:
    return gen_token(user_id, username, ACCESS_TOKEN_EXPIRE_TIMEDELTA)


def create_refresh_token(user_id: str, username: str) -> str:
    return gen_token(user_id, username, REFRESH_TOKEN_EXPIRE_TIMEDELTA)


def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        user_id: int = payload.get('id')
        if not username or not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {'username': username, 'user_id': user_id}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


user_dependency = Annotated[dict, Depends(get_current_user)]
