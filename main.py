from asgi_csrf import asgi_csrf
from fastapi.staticfiles import StaticFiles
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware

from apis.api import app as api
from render.routes import project_routes, users_routes
from base.middleware import BasicAuthBackend, DBSessionMiddleware


middleware = [
    Middleware(AuthenticationMiddleware, backend=BasicAuthBackend()),
    Middleware(DBSessionMiddleware),
]
routes = [
    Mount('/api', app=api,
          middleware=[Middleware(AuthenticationMiddleware, backend=BasicAuthBackend())]),
    Mount("/static", StaticFiles(directory="static"), name="static"),
    Mount('/projects', routes=project_routes, middleware=middleware),
    Mount('', routes=users_routes, middleware=middleware),
]

s_app = Starlette(debug=True, routes=routes)


def skip_api_paths(scope):
    return scope["path"].startswith("/api/")


app = asgi_csrf(s_app,
                signing_secret="secret-goes-here",
                skip_if_scope=skip_api_paths)
