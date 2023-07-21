from fastapi import FastAPI
from fastapi.testclient import TestClient

from cicada.api.middleware import cicada_exception_handler
from cicada.application.exceptions import (
    CicadaException,
    Forbidden,
    InvalidRequest,
    NotFound,
    Unauthorized,
)


def make_exception_handler_app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(CicadaException, cicada_exception_handler)

    @app.get("/invalid")
    def invalid() -> None:
        raise InvalidRequest("not valid")

    @app.get("/unauthorized")
    def unauthorized() -> None:
        raise Unauthorized("not authorized")

    @app.get("/forbidden")
    def forbidden() -> None:
        raise Forbidden("you are forbidden")

    @app.get("/not_found")
    def not_found() -> None:
        raise NotFound("not found")

    return app


def test_exceptions_are_handled_properly() -> None:
    app = make_exception_handler_app()

    client = TestClient(app)

    resp = client.get("/invalid")
    assert resp.status_code == 400
    assert "not valid" in resp.text

    resp = client.get("/unauthorized")
    assert resp.status_code == 401
    assert "not authorized" in resp.text

    resp = client.get("/forbidden")
    assert resp.status_code == 403
    assert "you are forbidden" in resp.text

    resp = client.get("/not_found")
    assert resp.status_code == 404
    assert "not found" in resp.text
