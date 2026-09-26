import logging

from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes import auth, bookings, centres, payments, tests
from app.core.database import SessionLocal
import app.models  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="EVE Healthcare Diagnostic Booking API", version="1.0.0")
app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(tests.router)
app.include_router(bookings.router)
app.include_router(payments.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["health"])
async def readiness() -> dict[str, str]:
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ready"}
