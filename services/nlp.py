"""
NLP layer — uses llama-cpp-python to run Phi-3.5-mini locally.
Parses a free-text user prompt into a structured ParsedIntent object.

Falls back to a simple regex heuristic if the model file is not present,
so the rest of the app still works during development / testing.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config import MODEL_PATH, N_CTX, N_THREADS

logger = logging.getLogger(__name__)

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ParsedIntent:
    query: str                          # Normalized search string, e.g. "Re:Zero S04"
    codec: Optional[str] = None         # e.g. "AV1", "HEVC", "AVC"
    resolution: Optional[str] = None    # e.g. "1080p", "4K"
    max_size_mb: Optional[float] = None # Upper size limit in MB
    min_size_mb: Optional[float] = None
    source: Optional[str] = None        # e.g. "BluRay", "WEB-DL"
    group: Optional[str] = None         # Preferred release group
    raw_prompt: str = ""
    extra: dict = field(default_factory=dict)


# ── Prompt template ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a torrent search assistant. Extract structured information from the user's request.
Return ONLY a valid JSON object with these keys (omit keys that are not mentioned):
{
  "query": "<normalized show/movie title with season/episode if present>",
  "codec": "<AV1|HEVC|AVC|null>",
  "resolution": "<4K|2160p|1080p|720p|480p|null>",
  "max_size_mb": <number or null>,
  "min_size_mb": <number or null>,
  "source": "<BluRay|WEB-DL|WEBRip|HDTV|null>",
  "group": "<release group name or null>"
}
Do not include any explanation, only the JSON object."""

_USER_TEMPLATE = "User request: {prompt}"


# ── Model loader (lazy singleton) ─────────────────────────────────────────────

_llm = None


def _load_model():
    global _llm
    if _llm is not None:
        return _llm

    if not Path(MODEL_PATH).exists():
        logger.warning(
            "Model file not found at %s — falling back to regex parser.", MODEL_PATH
        )
        return None

    try:
        # llama_cpp may raise FileNotFoundError if a CUDA build is installed
        # but the CUDA toolkit folder is missing — treat it like ImportError.
        from llama_cpp import Llama  # type: ignore
    except (ImportError, FileNotFoundError, OSError) as exc:
        logger.warning(
            "llama_cpp unavailable (%s) — falling back to regex parser. "
            "Fix: pip uninstall llama-cpp-python -y && "
            "pip install llama-cpp-python --prefer-binary "
            "--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu",
            exc,
        )
        return None

    try:
        logger.info("Loading model from %s …", MODEL_PATH)
        _llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=N_CTX,
            n_threads=N_THREADS,
            verbose=False,
        )
        logger.info("Model loaded successfully.")
    except Exception as exc:
        logger.error("Failed to load model: %s", exc)
        _llm = None

    return _llm


# ── Main parse function ───────────────────────────────────────────────────────

def parse_intent(prompt: str) -> ParsedIntent:
    """
    Convert a free-text user prompt into a ParsedIntent.
    Tries the local LLM first; falls back to regex heuristics.
    """
    llm = _load_model()
    if llm is not None:
        return _parse_with_llm(llm, prompt)
    return _parse_with_regex(prompt)


# ── LLM path ──────────────────────────────────────────────────────────────────

def _parse_with_llm(llm, prompt: str) -> ParsedIntent:
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _USER_TEMPLATE.format(prompt=prompt)},
    ]
    try:
        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=256,
            temperature=0.0,
        )
        raw_json = response["choices"][0]["message"]["content"].strip()
        # Strip markdown code fences if the model wraps the JSON
        raw_json = re.sub(r"^```[a-z]*\n?", "", raw_json)
        raw_json = re.sub(r"\n?```$", "", raw_json)
        data: dict = json.loads(raw_json)
        return ParsedIntent(
            query=data.get("query", prompt),
            codec=data.get("codec"),
            resolution=data.get("resolution"),
            max_size_mb=data.get("max_size_mb"),
            min_size_mb=data.get("min_size_mb"),
            source=data.get("source"),
            group=data.get("group"),
            raw_prompt=prompt,
            extra={k: v for k, v in data.items() if k not in {
                "query", "codec", "resolution", "max_size_mb",
                "min_size_mb", "source", "group"
            }},
        )
    except Exception as exc:
        logger.warning("LLM parse failed (%s), falling back to regex.", exc)
        return _parse_with_regex(prompt)


# ── Regex fallback ────────────────────────────────────────────────────────────

_CODEC_RE = re.compile(r"\b(AV1|HEVC|H\.?265|H\.?264|AVC|x265|x264)\b", re.I)
_RES_RE = re.compile(r"\b(4K|2160p|1080p|720p|480p)\b", re.I)
_SIZE_RE = re.compile(
    r"(?:less than|under|max|<)\s*(\d+(?:\.\d+)?)\s*(GB|MB)", re.I
)
_SOURCE_RE = re.compile(r"\b(BluRay|Blu-Ray|WEB-DL|WEBRip|HDTV|AMZN|NF)\b", re.I)
_SEASON_RE = re.compile(
    r"(\d+(?:st|nd|rd|th)?\s+season|season\s+\d+|s\d{1,2})", re.I
)


def _parse_with_regex(prompt: str) -> ParsedIntent:
    codec_m = _CODEC_RE.search(prompt)
    res_m = _RES_RE.search(prompt)
    size_m = _SIZE_RE.search(prompt)
    source_m = _SOURCE_RE.search(prompt)

    max_size_mb: float | None = None
    if size_m:
        val = float(size_m.group(1))
        unit = size_m.group(2).upper()
        max_size_mb = val * 1024 if unit == "GB" else val

    # Normalize codec label
    codec: str | None = None
    if codec_m:
        raw = codec_m.group(1).upper()
        codec = "HEVC" if raw in {"H.265", "H265", "X265", "HEVC"} else \
                "AVC"  if raw in {"H.264", "H264", "X264", "AVC"} else raw

    # Build a rough query by stripping constraint keywords
    query = re.sub(
        r"(?:i want|give me|find|search for|show me|get me)\s+", "", prompt, flags=re.I
    ).strip()
    # Remove constraint fragments
    query = _CODEC_RE.sub("", query)
    query = _RES_RE.sub("", query)
    query = _SIZE_RE.sub("", query)
    query = _SOURCE_RE.sub("", query)
    query = re.sub(r"\b(torrent[s]?|file[s]?|which|has|and|with|encoder|size)\b", "", query, flags=re.I)
    query = re.sub(r"\s{2,}", " ", query).strip(" ,.")

    return ParsedIntent(
        query=query or prompt,
        codec=codec,
        resolution=res_m.group(1).upper() if res_m else None,
        max_size_mb=max_size_mb,
        raw_prompt=prompt,
    )
