from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.dashboard.api.routes.status import router as status_router
from services.dashboard.api.routes.pnl import router as pnl_router

app = FastAPI(title="AlgoCore Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(status_router)
app.include_router(pnl_router)


@app.get("/health")
def health():
    return {"status": "ok"}
