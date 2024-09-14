from uuid import UUID
from fastapi import status, Request
from fastapi.responses import RedirectResponse
from starlette.authentication import requires
from pydantic import ValidationError

from base.models import Message
from base.database import commit_db
from base.config import templates
from apis.users.users import get_user
from render.schemas import MessageSchema
from apis.users.messages import get_received_messages, open_message


def _unread_count(messages: list[Message]) -> int:
    """
    Helper function to count unread messages from a list of messages.
    """
    return sum(1 for message in messages if not message.is_read)


@requires('authenticated', redirect='login-page')
async def inbox(request: Request):
    """
    Handles the user's inbox view, displaying all received messages and counting unread messages.

    Args:
        request (Request): The current HTTP request object, which includes user information.

    Returns:
        TemplateResponse: Renders the inbox page with the user's received messages and unread message count.

    Workflow:
    - Retrieves the authenticated user's profile ID.
    - Fetches the user's received messages from the database.
    - Counts the unread messages using the `_unread_count` helper function.
    - Renders the inbox template with the messages and unread count.
    """
    user = {"user_id": request.user.profile_id}
    db = request.state.db
    messages = await get_received_messages(user, db)
    unread_count = _unread_count(messages)

    context = {"messages": messages, 'unread_count': unread_count}
    return templates.TemplateResponse(request, 'users/inbox.html', context)


@requires('authenticated', redirect='login-page')
async def get_message(request: Request):
    """
    Handles viewing a single message from the user's inbox.

    Args:
        request (Request): The current HTTP request object, which includes user information and path parameters.

    Returns:
        TemplateResponse: Renders the single message view.

    Workflow:
    - Retrieves the message ID from the URL path parameters.
    - Marks the message as read and fetches the message details from the database.
    - Renders the message template with the message data.
    """
    user = {"user_id": request.user.profile_id}
    db = request.state.db
    message_id = request.path_params["message_id"]
    message = await open_message(message_id, user, db)

    return templates.TemplateResponse(request, 'users/message.html', {'message': message})


async def create_message(request: Request):
    """
    Handles creating and sending a message to another user.

    Args:
        request (Request): The current HTTP request object, which includes form data and user session.

    Returns:
        TemplateResponse or RedirectResponse: Renders the message creation form with errors, or redirects upon success.

    Workflow:
    - Retrieves the recipient's profile ID from the URL path parameters.
    - If the sender is an authenticated user, uses their profile information to send the message.
    - If the sender is not a user, validates the form and sends the message without a sender.
    - On successful message creation, redirects the user to the recipient's profile page.
    """
    recipient_id = request.path_params['profile_id']

    if request.method == 'POST':
        db = request.state.db
        form = await request.form()

        if not request.user.is_authenticated:
            # Handle unauthenticated users by validating the form and sending the message without a sender.
            try:
                message_content = MessageSchema(
                    **form)
            except ValidationError as ex:
                # Handle validation errors and re-render the form with errors.
                errors = {item['loc'][0]: item['msg'] for item in ex.errors()}
                context = {'errors': errors, 'recipient_id': recipient_id}
                return templates.TemplateResponse(request, 'users/message-form.html', context)

            message = Message(**message_content.model_dump(),
                              sender=None, recipient=UUID(recipient_id))

        else:
            # Handle authenticated users by using their profile information to send the message.
            sender = await get_user(request.user.profile_id, db, with_skills=False)
            try:
                message_content = MessageSchema(
                    **form, name=sender.username, email=sender.email)
            except ValidationError as ex:
                # Handle validation errors and re-render the form with errors.
                errors = {item['loc'][0]: item['msg'] for item in ex.errors()}
                context = {'errors': errors, 'recipient_id': recipient_id}
                return templates.TemplateResponse(request, 'users/message-form.html', context)

            message = Message(**message_content.model_dump(),
                              sender=sender.profile_id, recipient=UUID(recipient_id))

        db.add(message)
        await commit_db(db)

        redirect_url = request.url_for('user-profile', profile_id=recipient_id)
        return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)

    # Handel the get request
    return templates.TemplateResponse(request, 'users/message-form.html', {'recipient_id': recipient_id})
