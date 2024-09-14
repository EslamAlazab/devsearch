import datetime
from fastapi import status, Request, HTTPException
from fastapi.responses import RedirectResponse
from starlette.authentication import requires
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from base.models import Profile
from base.database import commit_db
from base.config import templates

from apis.users.auth import authenticate_user, bcrypt_context, create_access_token, gen_token, get_current_user
from apis.users.users import get_user
from apis.users.validators import user_validation
from apis.users.utils import email_verify
from render.schemas import Alert, ChangePassword
from render.utils import send_reset_email


def get_login_response(request: Request, user: Profile):
    """
    A helper function used in login and register that generates a login response that issues an access token and redirects the user.

    Args:
        request (Request): The current request object containing query parameters.
        user (Profile): The authenticated user's profile containing necessary data like `username` and `profile_id`.

    Returns:
        RedirectResponse: A response that sets an access token in a secure, HTTP-only cookie and redirects the user 
        either to the specified URL in the `next` query parameter or to the default 'profiles' page.

    Workflow:
    - An access token is created for the user using the `create_access_token` function.
    - If a `next` query parameter exists, the user is redirected to that URL. Otherwise, they are redirected to the 
      default 'profiles' page.
    - The access token is stored in a secure, HTTP-only cookie (`access_token`).
    - The response uses a 302 status code to perform the redirect.

    Security:
    - The `httponly` attribute ensures the token is not accessible via JavaScript.
    - The `secure` attribute ensures the token is only transmitted over HTTPS.

    """
    token = create_access_token(
        username=user.username, user_id=str(user.profile_id))
    if request.query_params.get('next', False):
        redirect_url = request.query_params['next']
    else:
        redirect_url = request.url_for('profiles')

    response = RedirectResponse(
        url=redirect_url, status_code=status.HTTP_302_FOUND)
    # set the access token as cookie
    response.set_cookie(key="access_token", value=token,
                        httponly=True, secure=True)
    return response


async def login(request: Request):
    """
    Handles the user login functionality based on the request method.

    Args:
        request (Request): The current HTTP request object, which includes form data, method type, and session state.

    Returns:
        TemplateResponse: Renders the login page with appropriate context if the request is GET or login fails. 
        Otherwise, returns a redirect response with a secure access token if login is successful.

    Workflow:
    - If the request method is POST:
        - The form data (username_or_email and password) is retrieved.
        - The `authenticate_user` function checks the credentials against the database.
        - If authentication fails, an error message is displayed on the login page.
        - If authentication succeeds, a login response with a secure access token is generated.
    - If the request method is GET:
        - Checks if there is any alert data stored in cookies (e.g., success/failure messages from other requests).
        - Displays the login page along with any alert (if exists).

    Key Features:
    - Authentication: Validates user credentials (email or username + password).
    - Alerts: Provides feedback for successful or failed login attempts.
    - Redirection: On successful login, redirects the user to a specified page or the default 'profiles' page.
    """
    if request.method == 'POST':
        db = request.state.db
        form = await request.form()
        username_or_email = form.get('username_or_email')
        password = form.get('password')
        user = await authenticate_user(username_or_email, password, db)
        if not user:
            alert = Alert(msg='Could not validate user.', tag='error')
            return templates.TemplateResponse(request, 'users/login.html', {'alert': alert})

        response = get_login_response(request, user)
        return response

    alert_data = request.cookies.get('alert_data', None)
    alert = None
    if alert_data:
        alert = Alert.model_validate_json(alert_data)
    return templates.TemplateResponse(request, 'users/login.html', {'alert': alert})


@requires('authenticated', redirect='login-page')
def logout(request: Request):
    """
    Handles user logout by invalidating the access token and redirecting to the login page.

    Args:
        request (Request): The current HTTP request object, which includes session information and URL routing.

    Returns:
        RedirectResponse: Redirects the user to the login page with a success alert message.

    Workflow:
    - Checks if the user is authenticated using the `requires` decorator.
    - Sets an alert message indicating successful logout.
    - Generates a redirect response to the login page.
    - Deletes the `access_token` cookie to invalidate the user's session.
    - Sets a cookie for the alert message with a short expiration time (10 seconds) and HTTP-only flag.
    """
    alert_data = Alert(msg='logout successful', tag='success')
    redirect_url = request.url_for('login-page')
    response = RedirectResponse(
        redirect_url, status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key='access_token')
    response.set_cookie(
        key='alert_data', value=alert_data.model_dump_json(), max_age=10, httponly=True)

    return response


async def register(request: Request):
    """
    Handles user registration by validating form data, hashing the password, creating a new user,
    and returning a login response or error template.

    Args:
        request (Request): The current HTTP request object, which includes form data and session state.

    Returns:
        TemplateResponse or RedirectResponse: 
            - Renders the registration page with error messages if validation fails.
            - Redirects the user to the login page with a success alert if registration is successful.

    Workflow:
    - For POST requests:
        - Retrieves and validates the form data (e.g., username, email, password).
        - If validation errors exist, renders the registration template with errors.
        - If validation is successful:
            - Hashes the password for security.
            - Creates a new user profile and saves it to the database.
            - Commits the new user to the database.
            - Generates a login response for the new user.
            - Sets a success alert message in a cookie.
    - For GET requests:
        - Renders the registration page.

    Security:
    - Passwords are hashed using `bcrypt_context` to ensure they are stored securely.
    """
    if request.method == "POST":
        db = request.state.db
        form = await request.form()
        try:
            errors: dict[str, list] = await user_validation(**form, db=db)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail='Something Went Wrong')
        if errors:
            return templates.TemplateResponse(request, 'users/register.html', {'errors': errors})

        form_data = dict(form)
        form_data.pop('password_2')
        form_data['password'] = bcrypt_context.hash(form['password'])

        new_user = Profile(**form_data)
        db.add(new_user)
        await commit_db(db=db)

        response = get_login_response(request, new_user)
        alert_data = Alert(msg='WELCOME to DevSearch', tag='success')
        response.set_cookie(
            key='alert_data', value=alert_data.model_dump_json(), max_age=10, httponly=True)
        return response

    return templates.TemplateResponse(request, 'users/register.html')


async def send_email_verification(request: Request):
    """
    Sends an email verification request to the user and redirects them back to the previous page.

    Args:
        request (Request): The current HTTP request object, which includes user information and headers.

    Returns:
        RedirectResponse: Redirects the user to the previous page or a default URL after sending the verification email.
    """
    db = request.state.db
    await email_verify(request.user.profile_id, request.user.username, request, db)
    previous_url = request.headers.get('referer')

    # If no referrer is provided, set a default URL
    if not previous_url:
        previous_url = '/'

    # Redirect to the previous URL
    return RedirectResponse(url=previous_url)


async def reset_password(request: Request):
    """
    Handles the password reset process by sending a reset email to the user.

    Args:
        request (Request): The current HTTP request object, which includes form data and session state.

    Returns:
        TemplateResponse: Renders the password reset sent page if the request is POST and the user is found,
        or the password reset form if the request is GET.

    Workflow:
    - For POST requests:
        - Retrieves the email from the form data.
        - Queries the database for a user with the provided email.
        - If the user is found:
            - Generates a password reset token valid for 2 hours.
            - Sends a reset email to the user with the token.
        - Renders the password reset sent confirmation page.
    - For GET requests:
        - Renders the password reset form.
    """
    if request.method == 'POST':
        db: AsyncSession = request.state.db
        form = await request.form()
        email = form.get('email')
        stmt = select(Profile).where(Profile.email == email)
        user = (await db.scalars(stmt)).first()
        if user:
            token = gen_token(user.profile_id, user.username,
                              datetime.timedelta(hours=2))
            await send_reset_email(request, user.email, token)
        return templates.TemplateResponse(request, 'password/reset_password_sent.html')

    return templates.TemplateResponse(request, 'password/reset_password.html')


async def change_password(request: Request):
    """
    Handles changing the user's password after verifying the reset token.

    Args:
        request (Request): The current HTTP request object, which includes form data, path parameters, and session state.

    Returns:
        TemplateResponse or HTTPException:
            - Renders the password reset complete page if the password is successfully changed.
            - Renders the password reset form with errors if validation fails.
            - Raises an HTTPException if the token is invalid or the user cannot be found.

    Workflow:
    - Retrieves the reset token from the path parameters and uses it to get the current user.
    - For POST requests:
        - Retrieves and validates the new password from the form data.
        - Updates the user's password in the database.
        - Renders the password reset complete page.
    - For GET requests:
        - Renders the password reset form if the user is found.
        - Raises an HTTPException if the user cannot be found.

    Security:
    - Ensures the new password is hashed before being stored.
    - Validates the reset token to prevent unauthorized password changes.
    """
    token = request.path_params.get('token')
    user = get_current_user(token)

    if request.method == 'POST':
        db: AsyncSession = request.state.db
        form = await request.form()
        try:
            form_data = ChangePassword(**form)
        except ValidationError as ex:
            errors: list[str] = ex.errors()[0]['msg'].replace(
                'Value error,', '').strip().split(',')
            context = {'errors': errors}
            return templates.TemplateResponse(request, 'password/reset.html', context)

        user = await get_user(user['user_id'], db, with_skills=False)
        user.password = bcrypt_context.hash(form_data.password)
        await commit_db(db)

        return templates.TemplateResponse(request, 'password/reset_password_complete.html')

    if user:
        return templates.TemplateResponse(request, 'password/reset.html')
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail='Something Went Wrong')
