from fastapi import FastAPI
from debug_toolbar.middleware import DebugToolbarMiddleware


from apis.users import skills, users, messages
from apis.projects import projects, tags, reviews


app = FastAPI()


app.add_middleware(
    DebugToolbarMiddleware,
    panels=["debug_toolbar.panels.sqlalchemy.SQLAlchemyPanel"]
)

app.include_router(users.router)
app.include_router(skills.router)
app.include_router(messages.router)
app.include_router(projects.router)
app.include_router(tags.router)
app.include_router(reviews.router)
