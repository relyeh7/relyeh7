import asyncio
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.dashboard.api.routes.status import router as status_router
from services.dashboard.api.routes.pnl import router as pnl_router
from services.dashboard.api.routes.positions import router as positions_router
from services.dashboard.api.routes.trades import router as trades_router
from services.dashboard.api.routes.performance import router as performance_router
from services.dashboard.api.routes.metrics import router as metrics_router
from shared.config import settings
from shared.state import get_state, redis_alive

app = FastAPI(title="AlgoCore Dashboard", version="0.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_EXEMPT_PATHS = {"/health", "/metrics"}


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if settings.api_key and request.url.path not in _EXEMPT_PATHS:
        provided = request.headers.get("X-API-Key", "")
        if provided != settings.api_key:
            return JSONResponse({"error": "Unauthorized"}, status_code=403)
    return await call_next(request)


app.include_router(status_router)
app.include_router(pnl_router)
app.include_router(positions_router)
app.include_router(trades_router)
app.include_router(performance_router)
app.include_router(metrics_router)


@app.get("/health")
def health():
    return {"status": "ok", "redis": "up" if redis_alive() else "down"}


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            payload = {
                "risk":      get_state("risk:state") or {},
                "positions": get_state("positions") or {},
                "ml_signal": get_state("ml_signal") or {},
                "sentiment": get_state("sentiment") or {},
            }
            await websocket.send_json(payload)
            await asyncio.sleep(2)
    except Exception:
        pass
