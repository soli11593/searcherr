"""
Prowlarr API client.
Docs: https://prowlarr.com/docs/api/
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from config import PROWLARR_API_KEY, PROWLARR_URL

logger = logging.getLogger(__name__)

# Prowlarr returns size in bytes
_MB = 1024 * 1024


class ProwlarrClient:
    def __init__(self) -> None:
        self._base = PROWLARR_URL.rstrip("/")
        self._headers = {
            "X-Api-Key": PROWLARR_API_KEY,
            "Accept": "application/json",
        }

    # ── Public API ────────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        categories: list[int] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Search Prowlarr for torrents matching *query*.

        Returns a list of normalized result dicts:
            title, size_mb, seeders, leechers, indexer,
            download_url, info_url, publish_date,
            group_name, codec, resolution, source
        """
        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
        }
        if categories:
            params["categories"] = ",".join(str(c) for c in categories)

        url = f"{self._base}/api/v1/search"
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(url, params=params, headers=self._headers)
                resp.raise_for_status()
                raw: list[dict] = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Prowlarr HTTP error %s: %s", exc.response.status_code, exc)
            raise
        except httpx.RequestError as exc:
            logger.error("Prowlarr connection error: %s — is Prowlarr running at %s?", exc, self._base)
            raise

        return [self._normalize(r) for r in raw]

    async def get_indexers(self) -> list[dict]:
        """Return all configured indexers."""
        url = f"{self._base}/api/v1/indexer"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _normalize(raw: dict) -> dict:
        """Flatten a Prowlarr result into a consistent shape."""
        title: str      = raw.get("title", "")
        size_bytes: int = raw.get("size", 0) or 0

        # Prowlarr can return any combination of these three link types:
        # - downloadUrl  → direct .torrent file link
        # - magnetUrl    → magnet:// URI (common on public trackers)
        # - infoUrl      → human-readable page (always present)
        download_url: str = raw.get("downloadUrl", "") or ""
        magnet_url: str   = raw.get("magnetUrl", "")   or ""
        info_url: str     = raw.get("infoUrl", "")     or ""

        # Prefer direct download, fall back to magnet
        primary_link = download_url or magnet_url

        return {
            "title":        title,
            "size_bytes":   size_bytes,
            "size_mb":      round(size_bytes / _MB, 1),
            "seeders":      raw.get("seeders",  0) or 0,
            "leechers":     raw.get("leechers", 0) or 0,
            "indexer":      raw.get("indexer",  ""),
            "download_url": primary_link,   # .torrent or magnet — whichever exists
            "magnet_url":   magnet_url,     # kept separately so UI can show magnet icon
            "info_url":     info_url,
            "publish_date": raw.get("publishDate", ""),
            # Parsed from title
            "group_name":   _extract_group(title),
            "codec":        _extract_codec(title),
            "resolution":   _extract_resolution(title),
            "source":       _extract_source(title),
        }


# ── Title parsers (best-effort regex) ────────────────────────────────────────

import re

# Group is the FIRST bracketed token at the start of the title
# e.g. "[SubsPlease] Re Zero..." → "SubsPlease"
# Falls back to the trailing "-GroupName" scene convention if no leading bracket
_GROUP_BRACKET_RE = re.compile(r"^\s*\[([^\]]+)\]")
_GROUP_SCENE_RE   = re.compile(r"-([A-Za-z0-9]+)$")

_CODEC_RE  = re.compile(r"\b(AV1|HEVC|H\.?265|H\.?264|AVC|x265|x264)\b", re.I)
_RES_RE    = re.compile(r"\b(4K|2160p|1080p|720p|480p)\b", re.I)
_SOURCE_RE = re.compile(r"\b(BluRay|Blu-Ray|WEB-DL|WEBRip|HDTV|AMZN|NF|DSNP)\b", re.I)


def _extract_group(title: str) -> str | None:
    # Prefer leading [Group] bracket — common in anime releases
    m = _GROUP_BRACKET_RE.match(title)
    if m:
        val = m.group(1).strip()
        # Skip if it looks like a hash (8+ hex chars) or a resolution/codec tag
        if not re.fullmatch(r"[0-9A-Fa-f]{6,}", val) and \
           not re.fullmatch(r"[\d]+p|4K|AV1|HEVC|AVC|AAC|FLAC|opus", val, re.I):
            return val
    # Fall back to trailing scene convention: Title.Name-GroupName
    m = _GROUP_SCENE_RE.search(title)
    return m.group(1) if m else None


def _extract_codec(title: str) -> str | None:
    m = _CODEC_RE.search(title)
    if not m:
        return None
    raw = m.group(1).upper()
    if raw in {"H.265", "H265", "X265", "HEVC"}:
        return "HEVC"
    if raw in {"H.264", "H264", "X264", "AVC"}:
        return "AVC"
    return raw


def _extract_resolution(title: str) -> str | None:
    m = _RES_RE.search(title)
    return m.group(1).upper() if m else None


def _extract_source(title: str) -> str | None:
    m = _SOURCE_RE.search(title)
    return m.group(1).upper() if m else None
