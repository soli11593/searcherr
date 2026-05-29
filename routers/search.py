"""
API routes:
  POST /api/search          — parse prompt, fetch, score, return results
  POST /api/select          — record user selection, update weights
  GET  /api/history         — recent selections
  GET  /api/weights         — current learned weights
  GET  /api/rules           — active regex rules
  GET  /                    — serve the Web UI
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from config import BEARER_TOKEN
from db.database import (
    get_all_weights,
    get_active_regex_rules,
    get_history,
    log_selection,
    upsert_weight,
    delete_history_entry,
    clear_all_history,
    delete_weight,
    clear_all_weights,
    delete_regex_rule,
    clear_all_regex_rules,
    log_search_query,
    get_search_queries,
    delete_search_query,
    clear_all_search_queries,
)
from services.nlp import parse_intent
from services.prowlarr import ProwlarrClient
from services.scorer import score_and_rank

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="templates")
security = HTTPBearer(auto_error=False)


# ── Auth dependency ───────────────────────────────────────────────────────────

def verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> None:
    if not BEARER_TOKEN or BEARER_TOKEN == "changeme-secret-token":
        return  # Token auth disabled / not configured
    if credentials is None or credentials.credentials != BEARER_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


AuthDep = Annotated[None, Depends(verify_token)]


# ── Request / Response models ─────────────────────────────────────────────────

class SearchRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=500)
    exploration: float = Field(default=0.1, ge=0.0, le=1.0)
    limit: int = Field(default=50, ge=1, le=200)


class SelectRequest(BaseModel):
    query: str
    torrent_title: str
    group_name: str | None = None
    codec: str | None = None
    resolution: str | None = None
    source: str | None = None
    size_bytes: int | None = None
    info_url: str | None = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/api/search", dependencies=[Depends(verify_token)])
async def search(body: SearchRequest):
    # 1. Parse intent
    intent = parse_intent(body.prompt)
    logger.info("Parsed intent: %s", intent)

    # 2. Fetch from Prowlarr
    client = ProwlarrClient()
    try:
        results = await client.search(intent.query, limit=body.limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Prowlarr error: {exc}") from exc

    if not results:
        return {"intent": intent.__dict__, "results": [], "total": 0}

    # 3. Score & rank
    ranked = score_and_rank(results, intent, exploration=body.exploration)

    # 4. Log the search prompt
    log_search_query(prompt=body.prompt, query=intent.query)

    return {
        "intent": intent.__dict__,
        "results": ranked,
        "total": len(ranked),
    }


@router.post("/api/select", dependencies=[Depends(verify_token)])
async def select_torrent(body: SelectRequest):
    """
    Called when the user picks a torrent.
    Updates the weight table and logs the selection.
    """
    # Update weights for each known attribute
    for attr, val in [
        ("codec", body.codec),
        ("resolution", body.resolution),
        ("group_name", body.group_name),
        ("source", body.source),
    ]:
        if val:
            upsert_weight(attr, val, delta=10.0)

    log_selection(
        query=body.query,
        torrent_title=body.torrent_title,
        group_name=body.group_name,
        codec=body.codec,
        resolution=body.resolution,
        source=body.source,
        size_bytes=body.size_bytes,
        info_url=body.info_url,
    )

    return {"status": "ok", "message": "Preferences updated."}


@router.get("/api/debug")
async def debug():
    """Shows current config values — remove this route in production."""
    from config import PROWLARR_URL, PROWLARR_API_KEY
    key = PROWLARR_API_KEY
    masked = (key[:4] + "****" + key[-4:]) if len(key) > 8 else ("****" if key else "NOT SET")
    return {
        "prowlarr_url": PROWLARR_URL,
        "prowlarr_api_key": masked,
        "key_length": len(key),
    }


@router.get("/api/searches", dependencies=[Depends(verify_token)])
async def search_queries(limit: int = 30):
    return {"searches": get_search_queries(limit)}

@router.delete("/api/searches/{entry_id}", dependencies=[Depends(verify_token)])
async def delete_search(entry_id: int):
    delete_search_query(entry_id)
    return {"status": "ok"}

@router.delete("/api/searches", dependencies=[Depends(verify_token)])
async def clear_searches():
    clear_all_search_queries()
    return {"status": "ok"}


@router.get("/api/history", dependencies=[Depends(verify_token)])
async def history(limit: int = 50):
    return {"history": get_history(limit)}

@router.delete("/api/history/{entry_id}", dependencies=[Depends(verify_token)])
async def delete_history(entry_id: int):
    delete_history_entry(entry_id)
    return {"status": "ok"}

@router.delete("/api/history", dependencies=[Depends(verify_token)])
async def clear_history():
    clear_all_history()
    return {"status": "ok"}


@router.get("/api/weights", dependencies=[Depends(verify_token)])
async def weights():
    return {"weights": get_all_weights()}

@router.delete("/api/weights/{weight_id}", dependencies=[Depends(verify_token)])
async def delete_weight_entry(weight_id: int):
    delete_weight(weight_id)
    return {"status": "ok"}

@router.delete("/api/weights", dependencies=[Depends(verify_token)])
async def clear_weights():
    clear_all_weights()
    return {"status": "ok"}


@router.get("/api/rules", dependencies=[Depends(verify_token)])
async def rules():
    return {"rules": get_active_regex_rules()}

@router.delete("/api/rules/{rule_id}", dependencies=[Depends(verify_token)])
async def delete_rule(rule_id: int):
    delete_regex_rule(rule_id)
    return {"status": "ok"}

@router.delete("/api/rules", dependencies=[Depends(verify_token)])
async def clear_rules():
    clear_all_regex_rules()
    return {"status": "ok"}