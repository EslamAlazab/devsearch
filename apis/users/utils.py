from io import BytesIO
from PIL import Image
import os
import uuid
from fastapi import HTTPException, UploadFile, Request
from base.config import (
    SAVE_DIR, ALLOWED_EXTENSIONS, MAX_FILE_SIZE, templates,
    SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_PORT, FROM_EMAIL
)
import datetime
from apis.users.auth import gen_token
from base.models import Profile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import aiosmtplib
from email.message import EmailMessage


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


async def save_and_compress_image(image: UploadFile) -> str:
    # Check if the file has a valid extension
    if not allowed_file(image.filename):
        raise HTTPException(status_code=400, detail="Invalid image extension")

    # Check the size of the uploaded file
    if image.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400, detail="File size exceeds the maximum limit of 10 MB")

    current_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # Create a directory named after the current date
    date_dir = f'./static/{SAVE_DIR}/{current_date}'
    os.makedirs(f"{date_dir}", exist_ok=True)

    # Generate a unique filename using UUID
    extension = image.filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{str(uuid.uuid4())[:10]}.{extension}"

    # Create the full path for the file
    file_path = f'{date_dir}/{unique_filename}'

    # Convert the contents to a BytesIO object
    content = await image.read()
    image_file = BytesIO(content)
    try:
        img = Image.open(image_file)
    except IOError:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Compress the image and save it
    img = img.convert("RGB")  # Ensure compatibility with all formats
    img.save(file_path, format='JPEG', optimize=True, quality=85)

    return file_path.replace('./static/', '')


async def email_verify(user_id: str, username: str, request: Request, db: AsyncSession):
    try:
        # Validate user_id as a UUID
        user_id = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # Generate the verification token
    token = gen_token(user_id, username, datetime.timedelta(hours=2))

    # Select the user's email based on the profile ID
    stmt = select(Profile.email).where(Profile.profile_id == user_id)
    user_email = await db.scalar(stmt)  # Fetch a single scalar value

    if not user_email:
        raise HTTPException(
            status_code=404, detail="Email not found for the given user ID")

    # Render the email template
    template = templates.get_template('verification_email.html').render({
        'request': request,
        'token': token
    })

    # Prepare the email message
    message = EmailMessage()
    message["From"] = FROM_EMAIL
    message["To"] = user_email
    message["Subject"] = 'DevSearch Account Verification'
    message.add_alternative(template, subtype='html')

    # Send the email via aiosmtplib
    try:
        await aiosmtplib.send(
            message,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            use_tls=True,
        )
    except Exception as e:
        print(f"Failed to send email: {e}")
        raise HTTPException(
            status_code=500, detail="Error sending verification email")
