from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.mock_autonomy_api import router as mock_autonomy_router
from api.mock_collaboration_api import router as mock_collaboration_router
from api.mock_dds_api import router as mock_dds_router
from api.spec_api import router as spec_router
from api.task_api import router as task_router
from scheduler.decision_loop import decision_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    decision_loop.start()
    print("[App] decision loop started")
    yield
    decision_loop.stop()
    print("[App] decision loop stopped")


app = FastAPI(
    title="Tracking Monitor Service",
    version="0.4.0",
    description="Tracking monitor service with mock APIs for DDS and external integrations.",
    lifespan=lifespan,
)

app.include_router(task_router, prefix="/tasks", tags=["tasks"])
app.include_router(spec_router, tags=["spec-apis"])
app.include_router(mock_dds_router, prefix="/mock/dds", tags=["mock-dds"])
app.include_router(mock_collaboration_router, prefix="/mock/collaboration", tags=["mock-collaboration"])
app.include_router(mock_autonomy_router, prefix="/mock/autonomy", tags=["mock-autonomy"])


@app.get("/")
def root():
    return {
        "code": 0,
        "message": "success",
        "data": {
            "service": "tracking_monitor_service",
            "version": "0.4.0",
        },
    }
