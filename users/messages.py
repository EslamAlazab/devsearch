from uuid import UUID
from fastapi import APIRouter, status, HTTPException
from sqlalchemy import select, or_, desc
from database import db_dependency, commit_db
from models import Message
from .auth import user_dependency
from .users import get_user
from .schemas import MessageFromUser, MessageFromNonUser


router = APIRouter(prefix='/messages', tags=['messages'])


@router.get('/{message_id}')
async def open_message(message_id: str, user: user_dependency, db: db_dependency):
    """
    Retrieve a message by its ID and mark it as read if the current user is the recipient.

    Returns:
        Message: The retrieved message.

    Raises:
        HTTPException: If the message is not found.
    """
    stmt = select(Message).where(
        Message.message_id == UUID(message_id),
        or_(Message.recipient == UUID(
            user['user_id']), Message.sender == UUID(user['user_id']))
    )
    mes = (await db.scalars(stmt)).first()
    if not mes:
        raise HTTPException(
            status_code=404, detail='Could not find the message!')

    # Mark the message as read if the current user is the recipient
    if mes.recipient == UUID(user['user_id']):
        mes.is_read = True
        await commit_db(db)
    return mes


@router.post('/', status_code=status.HTTP_201_CREATED)
async def send_message_from_user(message: MessageFromUser, user: user_dependency, db: db_dependency):
    sender = await get_user(user['user_id'], db)
    recipient_mes = Message(**message.model_dump(), sender=sender.profile_id,
                            name=sender.username, email=sender.email)
    db.add(recipient_mes)
    await commit_db(db)


@router.post('/from-non-user', status_code=status.HTTP_201_CREATED)
async def send_message_from_non_user(message: MessageFromNonUser, db: db_dependency):
    '''Send a message from a non-registered user.'''
    recipient_mes = Message(**message.model_dump())
    db.add(recipient_mes)
    await commit_db(db)


@router.get('/received-messages')
async def get_received_messages(user: user_dependency, db: db_dependency):
    stmt = select(Message).where(Message.recipient == UUID(
        user['user_id'])).order_by(Message.is_read, Message.created)
    messages = (await db.scalars(stmt)).all()
    if not messages:
        return []
    return messages


@router.get('/sent-messages')
async def get_sent_messages(user: user_dependency, db: db_dependency):
    stmt = select(Message).where(Message.sender == UUID(user['user_id']))
    messages = (await db.scalars(stmt)).all()
    if not messages:
        return []
    return messages


@router.delete('/{message_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(message_id: str, user: user_dependency, db: db_dependency):
    """
    Delete a message by its ID. If the user is the sender or recipient, the corresponding
    reference is removed. If both references are removed, the message is deleted.

    Raises:
        HTTPException: If the message is not found.
    """
    mes = await open_message(message_id, user, db)

    # Remove sender or recipient reference if the user matches
    if mes.sender == UUID(user['user_id']):
        mes.sender = None
    if mes.recipient == UUID(user['user_id']):
        mes.recipient = None

    # Delete the message if both sender and recipient references are removed
    if not mes.sender and not mes.recipient:
        await db.delete(mes)

    await commit_db(db)
