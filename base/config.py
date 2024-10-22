from datetime import timedelta
import os
import logging
from fastapi.templating import Jinja2Templates
from jinja2.ext import loopcontrols
import markdown

templates = Jinja2Templates('render/templates', extensions=[loopcontrols])

templates.env.filters['markdown'] = lambda text: markdown.markdown(text)


def ensure_protocol(url: str) -> str:
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    return url


templates.env.filters['ensure_protocol'] = ensure_protocol


SECRET_KEY = os.getenv('secret_key', 'testkey')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_TIMEDELTA = timedelta(minutes=300)  # 5 hours
REFRESH_TOKEN_EXPIRE_TIMEDELTA = timedelta(minutes=1440)  # 24 hours


SAVE_DIR = "images"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB limit


logger = logging.getLogger("uvicorn.error")


SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER", "eslam.test20@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL", "eslam.test20@gmail.com")
