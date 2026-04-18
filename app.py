from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from adapters.dds import get_dds_adapter
from api.mock_autonomy_api import router as mock_autonomy_router
from api.mock_collaboration_api import router as mock_collaboration_router
from api.mock_dds_api import router as mock_dds_router
from api.spec_api import router as spec_router
from api.task_api import router as task_router
from domain.response import ok
from scheduler.decision_loop import decision_loop
from services.dds_ingress_service import register_default_subscriptions


def _resolve_local_swagger_assets_dir() -> Optional[Path]:
    # Preferred offline location inside the repo/image.
    candidate = Path(__file__).resolve().parent / "static" / "swagger-ui"
    if (candidate / "swagger-ui-bundle.js").is_file() and (candidate / "swagger-ui.css").is_file():
        return candidate
    return None


def _find_swagger_assets_dir(root: Path) -> Optional[Path]:
    if not root.is_dir():
        return None

    for js_file in root.rglob("swagger-ui-bundle.js"):
        candidate = js_file.parent
        if (candidate / "swagger-ui.css").is_file():
            return candidate
    return None


def _resolve_swagger_assets_dir() -> Optional[Path]:
    try:
        import swagger_ui_bundle  # type: ignore
    except Exception:
        return None

    package_dir = Path(swagger_ui_bundle.__file__).resolve().parent
    search_roots = [
        package_dir / "vendor",
        package_dir / "dist",
        package_dir / "static",
        package_dir,
    ]
    for root in search_roots:
        candidate = _find_swagger_assets_dir(root)
        if candidate is not None:
            return candidate
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    dds_adapter = get_dds_adapter()
    register_default_subscriptions(dds_adapter)
    decision_loop.start()
    print("[App] decision loop started")
    yield
    decision_loop.stop()
    get_dds_adapter().stop()
    print("[App] decision loop stopped")


app = FastAPI(
    title="cc_cm_tracking_monitor_service",
    version="0.4.0",
    description="Tracking monitor service aligned with W5 v6 API/DDS contract.",
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/swagger.json",
    lifespan=lifespan,
)
# Keep OpenAPI at 3.0.x for legacy Swagger 2.x/older tooling compatibility.
app.openapi_version = "3.0.3"

_SWAGGER_ASSETS_DIR = _resolve_local_swagger_assets_dir() or _resolve_swagger_assets_dir()
if _SWAGGER_ASSETS_DIR is not None:
    app.mount(
        "/assets/swagger-ui",
        StaticFiles(directory=str(_SWAGGER_ASSETS_DIR)),
        name="swagger_ui_assets",
    )


@app.get("/api/swagger_ui/index.html", include_in_schema=False)
def swagger_ui() -> HTMLResponse:
    if _SWAGGER_ASSETS_DIR is not None:
        return get_swagger_ui_html(
            openapi_url=app.openapi_url or "/api/swagger.json",
            title=f"{app.title} - Swagger UI",
            swagger_js_url="/assets/swagger-ui/swagger-ui-bundle.js",
            swagger_css_url="/assets/swagger-ui/swagger-ui.css",
            swagger_favicon_url="/assets/swagger-ui/favicon-32x32.png",
        )

    # Offline-friendly fallback: avoid CDN blank page when container has no internet.
    return HTMLResponse(
        content=(
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{app.title} - Swagger UI Unavailable</title>"
            "</head><body style='font-family:Arial,sans-serif;padding:24px;'>"
            "<h2>Swagger UI is unavailable in offline mode.</h2>"
            "<p>Local swagger-ui static files were not found in this container, "
            "and external CDN assets cannot be loaded without internet access.</p>"
            "<p>You can still use OpenAPI JSON directly:</p>"
            "<p><a href='/api/swagger.json' target='_blank'>/api/swagger.json</a></p>"
            "</body></html>"
        ),
        status_code=503,
    )


@app.get("/api/swagger_ui", include_in_schema=False)
def swagger_ui_redirect() -> HTMLResponse:
    return swagger_ui()


app.include_router(task_router, prefix="/api/v1", tags=["tasks"])
app.include_router(spec_router, prefix="/api/v1", tags=["spec-apis"])
app.include_router(mock_dds_router, prefix="/mock/dds", tags=["mock-dds"])
app.include_router(mock_collaboration_router, prefix="/mock/collaboration", tags=["mock-collaboration"])
app.include_router(mock_autonomy_router, prefix="/mock/autonomy", tags=["mock-autonomy"])


@app.get("/")
def root():
    return {
        "code": 200,
        "message": "success",
        "data": {
            "service": "cc_cm_tracking_monitor_service",
            "version": "0.4.0",
        },
    }


@app.get("/api/v1/healthz")
def healthz():
    return ok(data=None)
