from fastapi import FastAPI
from users import skills, users, messages
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(users.router)
app.include_router(skills.router)
app.include_router(messages.router)
