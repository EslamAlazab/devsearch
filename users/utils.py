from io import BytesIO
from PIL import Image
import os
import uuid
from fastapi import HTTPException, UploadFile
from config import SAVE_DIR, ALLOWED_EXTENSIONS, MAX_FILE_SIZE
import datetime


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
    date_dir = f'{SAVE_DIR}/{current_date}'
    os.makedirs(date_dir, exist_ok=True)

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

    return file_path
