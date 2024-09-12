from fastapi import FastAPI
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.middleware import Middleware
from debug_toolbar.middleware import DebugToolbarMiddleware
from users import skills, users, messages
from projects import projects, tags, reviews
from render.routes import project_routes, users_routes
from fastapi.staticfiles import StaticFiles
from starlette.middleware.authentication import AuthenticationMiddleware
from middleware import BasicAuthBackend, DBSessionMiddleware
from asgi_csrf import asgi_csrf


app = FastAPI(debug=True)


# app.add_middleware(DBSessionMiddleware)


app.add_middleware(
    DebugToolbarMiddleware,
    panels=["debug_toolbar.panels.sqlalchemy.SQLAlchemyPanel"]
)
# app.add_middleware(AuthenticationMiddleware, backend=BasicAuthBackend())
# app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(users.router)
app.include_router(skills.router)
app.include_router(messages.router)
app.include_router(projects.router)
app.include_router(tags.router)
app.include_router(reviews.router)

# app.include_router(routes.render_router)
# app.include_router(projects_renders.router)
middleware = [
    Middleware(AuthenticationMiddleware, backend=BasicAuthBackend()),
    Middleware(DBSessionMiddleware),
]
routes = [
    Mount('/api', app=app),
    Mount("/static", StaticFiles(directory="static"), name="static"),
    Mount('/projects', routes=project_routes, middleware=middleware),
    Mount('', routes=users_routes, middleware=middleware),
]

ssapp = Starlette(debug=True, routes=routes)
sapp = asgi_csrf(ssapp, signing_secret="secret-goes-here")
