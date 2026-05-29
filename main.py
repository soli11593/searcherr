"""
Entry point — FastAPI application.
Run locally:  uvicorn main:app --reload
In Docker:    CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from db.database import init_db, init_search_history
from routers.search import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)

app = FastAPI(
    title="searcherr",
    description="Self-learning torrent preference system powered by Phi-3.5-mini.",
    version="1.0.0",
)

# ── Global error handlers ─────────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Return Pydantic validation errors as a plain readable string."""
    messages = []
    for err in exc.errors():
        field = " → ".join(str(x) for x in err.get("loc", []))
        messages.append(f"{field}: {err['msg']}")
    detail = "; ".join(messages)
    logging.getLogger(__name__).warning("Validation error on %s: %s", request.url.path, detail)
    return JSONResponse(
        status_code=422,
        content={"detail": detail},
    )

@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logging.getLogger(__name__).error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) or "Internal server error"},
    )

# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    init_db()
    init_search_history()
    logging.getLogger(__name__).info("Database initialised.")


# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(router)
app.mount("/static", StaticFiles(directory="static"), name="static")
