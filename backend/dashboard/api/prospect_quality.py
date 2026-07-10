from __future__ import annotations

from typing import Any

from crawler.scoring import get_score_label
from leads.models import Prospect


def _raw_payload(prospect: Prospect) -> dict[str, Any]:
    raw = prospect.raw_payload
    return raw if isinstance(raw, dict) else {}


def prospect_translation_need_score(prospect: Prospect) -> int | None:
    """Read translation need score from raw_payload (crawler / AI search)."""
    val = _raw_payload(prospect).get("translation_need_score")
    if val is None:
        return None
    try:
        return max(0, min(100, int(val)))
    except (TypeError, ValueError):
        return None


def prospect_score_label(prospect: Prospect) -> str | None:
    raw = _raw_payload(prospect)
    label = raw.get("score_label")
    if label:
        return str(label)
    score = prospect_translation_need_score(prospect)
    if score is not None:
        return get_score_label(score)
    return None


def prospect_score_reasoning(prospect: Prospect) -> str:
    """Human-readable context for why the prospect was scored."""
    raw = _raw_payload(prospect)
    parts: list[str] = []
    why = (raw.get("why_needs_translation") or "").strip()
    if why:
        parts.append(why)
    reasoning = (raw.get("translation_need_reasoning") or "").strip()
    if reasoning and reasoning not in parts:
        parts.append(reasoning)
    org_type = (raw.get("org_type") or "").strip()
    if org_type:
        parts.append(f"Org type: {org_type}")
    signals = raw.get("international_signals") or []
    if isinstance(signals, list) and signals:
        parts.append("Signals: " + ", ".join(str(s) for s in signals[:5]))
    return "\n".join(parts)
