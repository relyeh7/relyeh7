import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from services.dashboard.api.routes.status import router as status_router
from services.dashboard.api.routes.pnl import router as pnl_router
from services.dashboard.api.routes.positions import router as positions_router
from services.dashboard.api.routes.trades import router as trades_router
from services.dashboard.api.routes.performance import router as performance_router
from shared.state import get_state

app = FastAPI(title="AlgoCore Dashboard", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(status_router)
app.include_router(pnl_router)
app.include_router(positions_router)
app.include_router(trades_router)
app.include_router(performance_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            payload = {
                "risk":      get_state("risk")      or {},
                "positions": get_state("positions") or {},
                "ml_signal": get_state("ml_signal") or {},
                "sentiment": get_state("sentiment") or {},
            }
            await websocket.send_json(payload)
            await asyncio.sleep(2)
    except Exception:
        pass
