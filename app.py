from contextlib import asynccontextmanager

from fastapi import FastAPI

from adapters.dds import get_dds_adapter
from api.mock_autonomy_api import router as mock_autonomy_router
from api.mock_collaboration_api import router as mock_collaboration_router
from api.mock_dds_api import router as mock_dds_router
from api.spec_api import router as spec_router
from api.task_api import router as task_router
from domain.response import ok
from scheduler.decision_loop import decision_loop
from services.dds_ingress_service import register_default_subscriptions


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
    docs_url="/api/swagger_ui/index.html",
    openapi_url="/api/swagger.json",
    lifespan=lifespan,
)

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
