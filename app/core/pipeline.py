"""Defines the sequential pipeline for the Multi-Agent Studio."""
from __future__ import annotations
from enum import Enum, auto

class AgentState(Enum):
    IDLE = auto()
    RESEARCHING = auto()
    VERIFYING_ACCURACY = auto()
    SCRIPTING = auto()
    CHECKING_VIRALITY = auto()
    QUALITY_CONTROL = auto()
    VOICEOVER = auto()
    SOURCING_MEDIA = auto()
    CHECKING_MEDIA = auto()
    EDITING = auto()
    VERIFYING_VIDEO = auto()
    THUMBNAIL_GEN = auto()
    SEO_OPTIMIZATION = auto()
    ANALYZING = auto()
    CONFIGURING = auto()
    COMPLETED = auto()
    FAILED = auto()

AGENT_SEQUENCE = [
    AgentState.RESEARCHING, AgentState.VERIFYING_ACCURACY, AgentState.SCRIPTING,
    AgentState.CHECKING_VIRALITY, AgentState.QUALITY_CONTROL, AgentState.VOICEOVER,
    AgentState.SOURCING_MEDIA, AgentState.CHECKING_MEDIA, AgentState.EDITING,
    AgentState.VERIFYING_VIDEO, AgentState.THUMBNAIL_GEN, AgentState.SEO_OPTIMIZATION,
]
# ANALYZING and CONFIGURING are left out: their agents are placeholders that
# need published-video analytics, which the pipeline does not have yet.

def get_next_state(current: AgentState) -> AgentState | None:
    try:
        idx = AGENT_SEQUENCE.index(current)
        if idx + 1 < len(AGENT_SEQUENCE): return AGENT_SEQUENCE[idx + 1]
    except ValueError: pass
    return None
