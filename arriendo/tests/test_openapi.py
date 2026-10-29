from pathlib import Path

import yaml
from openapi_spec_validator import validate

from app.main import app


OPENAPI_PATH = Path(__file__).parents[1] / "openapi.yaml"
HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "head",
    "options",
    "trace",
}


def _iter_http_routes(routes):
    for route in routes:
        nested_routes = getattr(route, "routes", None)
        if nested_routes is None:
            original_router = getattr(route, "original_router", None)
            nested_routes = getattr(original_router, "routes", None)
        if nested_routes is not None:
            yield from _iter_http_routes(nested_routes)
        else:
            yield route


def _load_openapi():
    with OPENAPI_PATH.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def _documented_routes(specification):
    return {
        (path, method)
        for path, path_item in specification["paths"].items()
        for method in path_item
        if method in HTTP_METHODS
    }


def _implemented_routes():
    return {
        (route.path, method.lower())
        for route in _iter_http_routes(app.routes)
        if getattr(route, "path", None) is not None
        and route.path not in {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}
        for method in (getattr(route, "methods", set()) or set())
        if method.lower() in HTTP_METHODS
    }


def test_openapi_document_is_valid():
    specification = _load_openapi()
    validate(specification)


def test_openapi_routes_match_fastapi_implementation():
    documented_routes = _documented_routes(_load_openapi())
    implemented_routes = _implemented_routes()

    missing_from_openapi = implemented_routes - documented_routes
    missing_from_implementation = documented_routes - implemented_routes

    assert not missing_from_openapi, (
        "Rutas implementadas que faltan en openapi.yaml: "
        f"{sorted(missing_from_openapi)}"
    )
    assert not missing_from_implementation, (
        "Rutas documentadas que no existen en FastAPI: "
        f"{sorted(missing_from_implementation)}"
    )
