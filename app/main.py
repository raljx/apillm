import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analyze import router as analyze_router
from app.api.routes.health import router as health_router


LOG_LEVEL = os.getenv(
    "LOG_LEVEL",
    "INFO",
).upper()


logging.basicConfig(
    level=LOG_LEVEL,
    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(name)s "
        "%(message)s"
    ),
)


app = FastAPI(
    title="Menu Analyst API",
    description=(
        "API d'analyse de documents de menus "
        "via Azure AI Foundry."
    ),
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mco-prp.yourmco.com",
        "https://mco.yourmco.com",
        "https://mco-itg.yourmco.com",
        "http://localhost",
        "http://localhost:8000",
        "http://localhost:8001",
    ],
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


app.include_router(
    health_router,
    prefix="/api/v1",
)

app.include_router(
    analyze_router,
    prefix="/api/v1",
)


@app.get("/")
async def root():
    return {
        "service": "menu-analyst-api",
        "status": "ok",
    }