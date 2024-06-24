from datetime import timedelta
import os
import logging

SECRET_KEY = os.getenv('secret_key', 'testkey')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_TIMEDELTA = timedelta(minutes=300)  # 30 minutes
REFRESH_TOKEN_EXPIRE_TIMEDELTA = timedelta(minutes=1440)  # 24 hours


SAVE_DIR = "./static/images"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB limit


logger = logging.getLogger("uvicorn.error")
