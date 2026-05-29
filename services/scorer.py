"""
Weighted scoring engine.

Pipeline:
  1. Score every result — preferred attributes get bonuses, constraint
     violations get a soft penalty (still visible, ranked last).
  2. Apply regex-rule bonuses.
  3. Apply seeder health bonus.
  4. Optionally inject exploration noise.

Results are NEVER hidden — they are always returned so the UI can show
everything and let the user filter client-side.
"""

from __future__ import annotations

import math
import random
import re
from typing import Any

from config import EXPLORATION_FACTOR
from db.database import get_active_regex_rules, get_weight
from services.nlp import ParsedIntent

# Score constants
BASE_SCORE        = 100
CONSTRAINT_PENALTY = -200   # Soft penalty — result still shows, just ranked low
SEEDER_BONUS_MAX  = 20
WEIGHT_MULTIPLIER = 1.0


def score_and_rank(
    results: list[dict[str, Any]],
    intent: ParsedIntent,
    exploration: float = EXPLORATION_FACTOR,
) -> list[dict[str, Any]]:
    """
    Score every result and return the full list sorted by score descending.
    Nothing is removed — constraint violations are penalised but still visible.
    """
    regex_rules = get_active_regex_rules()

    scored = []
    for torrent in results:
        score, reasons, constraint_fail = _score_one(torrent, intent, regex_rules)

        if exploration > 0 and not constraint_fail:
            score += random.uniform(0, exploration * 30)

        scored.append({
            **torrent,
            "score": round(score, 2),
            "score_reasons": reasons,
            "constraint_fail": constraint_fail,   # UI uses this to dim the card
        })

    scored.sort(key=lambda t: t["score"], reverse=True)
    return scored


# ── Per-torrent scoring ───────────────────────────────────────────────────────

def _score_one(
    torrent: dict,
    intent: ParsedIntent,
    regex_rules: list[dict],
) -> tuple[float, list[str], bool]:
    score = float(BASE_SCORE)
    reasons: list[str] = []
    constraint_fail = False

    size_mb: float  = torrent.get("size_mb", 0) or 0
    codec: str | None      = torrent.get("codec")
    resolution: str | None = torrent.get("resolution")
    group: str | None      = torrent.get("group_name")
    source: str | None     = torrent.get("source")
    seeders: int           = torrent.get("seeders", 0) or 0
    title: str             = torrent.get("title", "")

    # ── Soft constraint penalties (still shown, ranked low) ───────────────────
    if intent.max_size_mb and size_mb and size_mb > intent.max_size_mb:
        score += CONSTRAINT_PENALTY
        reasons.append(f"⚠ size {size_mb:.0f}MB > requested max {intent.max_size_mb:.0f}MB")
        constraint_fail = True

    if intent.min_size_mb and size_mb and size_mb < intent.min_size_mb:
        score += CONSTRAINT_PENALTY
        reasons.append(f"⚠ size {size_mb:.0f}MB < requested min {intent.min_size_mb:.0f}MB")
        constraint_fail = True

    if intent.codec and codec and codec.upper() != intent.codec.upper():
        score += CONSTRAINT_PENALTY
        reasons.append(f"⚠ codec {codec} ≠ requested {intent.codec}")
        constraint_fail = True

    if intent.resolution and resolution and resolution.upper() != intent.resolution.upper():
        score += CONSTRAINT_PENALTY
        reasons.append(f"⚠ resolution {resolution} ≠ requested {intent.resolution}")
        constraint_fail = True

    # ── Preference bonuses from learned SQLite weights ────────────────────────
    for attr, val in [
        ("codec",       codec),
        ("resolution",  resolution),
        ("group_name",  group),
        ("source",      source),
    ]:
        if val:
            w = get_weight(attr, val) * WEIGHT_MULTIPLIER
            if w:
                score += w
                reasons.append(f"✓ learned {attr} '{val}' +{w:.1f}")

    # ── Regex rule bonuses ────────────────────────────────────────────────────
    for rule in regex_rules:
        try:
            if re.search(rule["pattern"], title):
                score += rule["bonus"]
                reasons.append(f"✓ regex rule '{rule['pattern']}' +{rule['bonus']}")
        except re.error:
            pass

    # ── Seeder health bonus (log-scaled, capped) ──────────────────────────────
    if seeders > 0:
        bonus = min(math.log10(seeders + 1) * 10, SEEDER_BONUS_MAX)
        score += bonus
        reasons.append(f"seeders {seeders} +{bonus:.1f}")

    return score, reasons, constraint_fail
