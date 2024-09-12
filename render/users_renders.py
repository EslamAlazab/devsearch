import os
from uuid import UUID
from fastapi import APIRouter, status, HTTPException, Depends, UploadFile, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.authentication import requires
from pydantic import ValidationError
from sqlalchemy import select

from models import Project, Profile, Skill, Message
from database import SessionLocal, db_dependency, commit_db, get_db
from config import templates, logger
from users.users import get_user, search_users
from users.auth import authenticate_user, create_access_token, bcrypt_context
from users.schemas import UpdateProfile
from users.utils import save_and_compress_image

from .utils import (
    Paginator, count_obj, Alert, alerts, get_login_response, _user_profile, get_skill, _unread_count, remove_old_image)
from render.schemas import MessageSchema
from users.validators import user_validation
from users.messages import get_received_messages, open_message


async def login(request: Request):
    if request.method == 'POST':
        db = request.state.db
        form = await request.form()
        username_or_email = form.get('username_or_email')
        password = form.get('password')
        user = await authenticate_user(username_or_email, password, db)
        if not user:
            msg = Alert('Could not validate user.', tag='danger')
            return templates.TemplateResponse(request, 'users/login.html', {'msg': msg})

        response = get_login_response(request, user)
        alerts.update(
            {str(user.profile_id): [Alert('Login successful', tag='success')]})
        return response

    return templates.TemplateResponse(request, 'users/login.html')


@requires('authenticated', redirect='login-page')
def logout(request: Request):
    msg = Alert('logout successful', tag='success')
    redirect_url = request.url_for('login-page')
    response = RedirectResponse(
        redirect_url, status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key='access_token')
    return response


async def register(request: Request):
    """
    Handles user registration. Validates form data, hashes password, creates a new user,
    and returns a login response or error template.

    Args:
        request (Request): Incoming HTTP request object.
    Returns:
        TemplateResponse or HTTPResponse: Rendered template or a redirect response.
    """
    if request.method == "POST":
        db = request.state.db
        form = await request.form()
        errors: dict[str, list] = await user_validation(**form, db=db)
        if errors:
            return templates.TemplateResponse(request, 'users/register.html', {'errors': errors})

        form_data = dict(form)
        form_data.pop('password_2')
        form_data['password'] = bcrypt_context.hash(form['password'])

        new_user = Profile(**form_data)
        db.add(new_user)
        await commit_db(db=db)

        response = get_login_response(request, new_user)
        alerts.update(
            {str(new_user.profile_id): [Alert('WELCOME to devsearch', tag='success')]})
        return response

    return templates.TemplateResponse(request, 'users/register.html')


async def profiles(request: Request):
    db = request.state.db
    username: str | None = request.query_params.get('search_query', None)
    skill: str | None = request.query_params.get('skill', None)
    page: int = int(request.query_params.get('page', 1))
    size: int = int(request.query_params.get('page', 10))

    profiles = await search_users(db, username, skill, page, size)
    total_profiles = await count_obj(Profile.profile_id, db=db)
    paginator = Paginator(
        page=page, size=size, total=total_profiles)

    context = {"profiles": profiles,
               'search_query': username, 'paginator': paginator}
    return templates.TemplateResponse(request, 'users/profiles.html', context)


async def user_profile(request: Request):
    db = request.state.db
    profile_id: str = request.path_params['profile_id']
    page: int = int(request.query_params.get('page', 1))
    size: int = int(request.query_params.get('page', 6))

    context = await _user_profile(profile_id, page, size, db)

    return templates.TemplateResponse(request, 'users/user-profile.html', context=context)


@requires('authenticated', redirect='login-page')
async def account(request: Request):
    db = request.state.db
    profile_id: str = request.user.profile_id
    page: int = int(request.query_params.get('page', 1))
    size: int = int(request.query_params.get('page', 6))

    # helper function to get profile, project associated with it, and a paginator for that projects.
    context = await _user_profile(profile_id, page, size, db)

    return templates.TemplateResponse(request, 'users/account.html', context=context)


@requires('authenticated', redirect='login-page')
async def edit_account(request: Request):
    db = request.state.db
    profile_id = request.user.profile_id
    profile = await get_user(profile_id, db, with_skills=False)
    updated_profile = UpdateProfile(**profile.__dict__)

    if request.method == 'POST':
        form = await request.form()
        try:
            updated_profile = UpdateProfile(**form)
        except ValidationError as ex:
            errors = {item['loc'][0]: item['msg'] for item in ex.errors()}
            context = {'errors': errors, 'profile': updated_profile}
            return templates.TemplateResponse(request, 'users/edit-account.html', context)

        for key, value in updated_profile.model_dump().items():
            setattr(profile, key, value)

        await commit_db(db=db)
        redirect_url = request.url_for('account')
        return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(request, 'users/edit-account.html', {'profile': updated_profile})


@requires('authenticated', redirect='login-page')
async def edit_profile_image(request: Request):
    if request.method == 'POST':
        db = request.state.db
        profile_id = request.user.profile_id
        profile = await get_user(profile_id, db, with_skills=False)
        old_image_path = profile.profile_image
        async with request.form() as form:
            profile_image: UploadFile = form["profile_image"]

            # Validate, compress, and save the image, then update the profile with the new image path
            try:
                profile.profile_image = await save_and_compress_image(profile_image)
            except HTTPException as ex:
                errors = ex.detail
                return templates.TemplateResponse(request, 'users/edit-profile-image.html', {'errors': errors})

        await commit_db(db)

        remove_old_image(old_image_path)

        redirect_url = request.url_for('account')
        return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(request, 'users/edit-profile-image.html')


@requires('authenticated', redirect='login-page')
async def create_skill(request: Request):
    if request.method == 'POST':
        db = request.state.db
        form = await request.form()
        skill = Skill(**form, owner_id=UUID(request.user.profile_id))
        db.add(skill)
        await db.commit()

        redirect_url = request.url_for('account')
        return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(request, 'users/skill-form.html')


@requires('authenticated', redirect='login-page')
async def update_skill(request: Request):
    db = request.state.db
    skill = await get_skill(request.path_params['skill_id'], request.user.profile_id, db)

    if request.method == 'POST':
        form = await request.form()
        for key, value in form.items():
            setattr(skill, key, value)
        await commit_db(db=db)
        redirect_url = request.url_for('account')
        return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(request, 'users/skill-form.html', {'skill': skill})


@requires('authenticated', redirect='login-page')
async def delete_skill(request: Request):
    db = request.state.db
    skill = await get_skill(request.path_params['skill_id'], request.user.profile_id, db)

    if request.method == 'POST':
        await db.delete(skill)
        await commit_db(db)

        redirect_url = request.url_for('account')
        return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(request, 'delete.html', {'object': skill.name})


@requires('authenticated', redirect='login-page')
async def inbox(request: Request):
    user = {"user_id": request.user.profile_id}
    db = request.state.db
    messages = await get_received_messages(user, db)
    unread_count = _unread_count(messages)

    context = {"messages": messages, 'unread_count': unread_count}
    return templates.TemplateResponse(request, 'users/inbox.html', context)


@requires('authenticated', redirect='login-page')
async def get_message(request: Request):
    user = {"user_id": request.user.profile_id}
    db = request.state.db
    message_id = request.path_params["message_id"]
    message = await open_message(message_id, user, db)
    return templates.TemplateResponse(request, 'users/message.html', {'message': message})


async def create_message(request: Request):
    recipient_id = request.path_params['profile_id']

    if request.method == 'POST':
        db = request.state.db
        form = await request.form()
        if not request.user.is_authenticated:
            try:
                message_content = MessageSchema(
                    **form)
            except ValidationError as ex:
                errors = {item['loc'][0]: item['msg'] for item in ex.errors()}
                context = {'errors': errors, 'recipient_id': recipient_id}
                return templates.TemplateResponse(request, 'users/message-form.html', context)
            message = Message(**message_content.model_dump(),
                              sender=None, recipient=UUID(recipient_id))
        else:
            sender = await get_user(request.user.profile_id, db, with_skills=False)
            try:
                message_content = MessageSchema(
                    **form, name=sender.username, email=sender.email)
            except ValidationError as ex:
                errors = {item['loc'][0]: item['msg'] for item in ex.errors()}
                context = {'errors': errors, 'recipient_id': recipient_id}
                return templates.TemplateResponse(request, 'users/message-form.html', context)
            message = Message(**message_content.model_dump(),
                              sender=sender.profile_id, recipient=UUID(recipient_id))

        db.add(message)
        await commit_db(db)

        redirect_url = request.url_for('user-profile', profile_id=recipient_id)
        return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(request, 'users/message-form.html', {'recipient_id': recipient_id})
