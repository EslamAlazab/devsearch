from fastapi import Request, HTTPException

from starlette.authentication import (
    AuthenticationBackend, AuthenticationError, SimpleUser, AuthCredentials
)
from starlette.middleware.base import BaseHTTPMiddleware
from apis.users.auth import get_current_user
from base.database import SessionLocal


class CustomUser(SimpleUser):
    def __init__(self, username: str, profile_id: str):
        super().__init__(username)
        self.profile_id = profile_id


class BasicAuthBackend(AuthenticationBackend):
    async def authenticate(self, request: Request):
        token = request.cookies.get("access_token")
        if not token:
            return None

        try:
            user = get_current_user(token)
        except HTTPException:
            # TODO:Add refresh token functionality
            return None
        if user:
            return AuthCredentials(["authenticated"]), CustomUser(username=user['username'], profile_id=user['user_id'])
        else:
            return None


class DBSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Create a new database session
        async with SessionLocal() as session:
            request.state.db = session  # Add session to request.state
            response = await call_next(request)  # Process the request
            return response
