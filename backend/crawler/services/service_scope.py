"""
Service delivery-mode classification (D2, DISCOVERY_QUALITY_ANALYSIS.md).

Some LSP services require the interpreter/equipment to be physically present with
the client — simultaneous/conference/liaison (interactive) interpretation, sight
translation, equipment hire/booths — so a lead is only usable for these if it's in
Kenya/East Africa. Others are delivered remotely — virtual interpretation, document
translation, localization, rapporteuring — and are just as usable anywhere in the
world. The strict East-Africa geo gate should only be lifted for the latter: a
candidate with no identifiable service signal at all keeps the conservative
East-Africa-strict default, same as before this classification existed.
"""

from __future__ import annotations

# Specific compound phrases are checked first and decide the classification outright —
# they're unambiguous even though some contain a generic word ("interpretation") that
# would otherwise lean the other way (e.g. "virtual interpretation" must win as virtual).
_PHYSICAL_SPECIFIC = (
    "simultaneous interpretation",
    "conference interpretation",
    "liaison interpretation",
    "interactive interpretation",
    "consecutive interpretation",
    "sight translation",
    "interpretation booth",
    "interpretation equipment",
    "on-site interpret",
    "onsite interpret",
    "in-person interpretation",
    "conference equipment",
    "pa system",
    "av setup",
    "simultaneous equipment",
)

_VIRTUAL_SPECIFIC = (
    "virtual interpretation",
    "remote interpretation",
    "virtual conference interpretation",
    "video remote interpreting",
    "vri",
    "document translation",
    "certified translation",
    "legal translation",
    "technical translation",
    "localization",
    "localisation",
    "rapporteur",
    "rapporteuring",
    "transcription",
    "subtitling",
)

# Bare/generic fallback terms — only consulted when no specific phrase matched at all.
# "Interpretation" alone conventionally implies live/in-person unless qualified as
# virtual/remote; "translation" alone conventionally implies a written, deliverable
# (location-agnostic) work product.
_PHYSICAL_GENERIC = ("interpreter", "interpretation", "interpreting")
_VIRTUAL_GENERIC = ("translation services", "translator", "translation")


def classify_service_scope(*texts: str) -> str:
    """
    Return "physical", "virtual", or "unknown" for the combined text (a seed topic,
    search query, or page content). "unknown" covers both no signal at all and a
    genuine tie between physical and virtual specific phrases.
    """
    combined = " ".join(t for t in texts if t).lower()
    if not combined.strip():
        return "unknown"

    p_specific = sum(1 for t in _PHYSICAL_SPECIFIC if t in combined)
    v_specific = sum(1 for t in _VIRTUAL_SPECIFIC if t in combined)
    if p_specific or v_specific:
        if p_specific > v_specific:
            return "physical"
        if v_specific > p_specific:
            return "virtual"
        return "unknown"

    p_generic = any(t in combined for t in _PHYSICAL_GENERIC)
    v_generic = any(t in combined for t in _VIRTUAL_GENERIC)
    if p_generic and not v_generic:
        return "physical"
    if v_generic and not p_generic:
        return "virtual"
    return "unknown"


def requires_strict_geo(service_scope: str) -> bool:
    """
    The strict East-Africa/Kenya gate applies unless the candidate clearly signals a
    location-agnostic (virtual/deliverable) service need. Physical-presence AND
    unknown/no-signal candidates both keep the existing strict default — only an
    explicit virtual signal lifts the gate.
    """
    return service_scope != "virtual"
