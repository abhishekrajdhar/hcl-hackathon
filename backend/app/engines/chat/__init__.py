"""Deterministic chat engine: intent detection and grounded response composition."""

from app.engines.chat.compose import compose_reply
from app.engines.chat.intent import Intent, IntentKind, detect_intent

__all__ = ["Intent", "IntentKind", "compose_reply", "detect_intent"]
