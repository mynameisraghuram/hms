# backend/hm_core/common/events.py
from collections import defaultdict
from typing import Callable, Dict, List, Any

Handler = Callable[[Dict[str, Any]], None]

_registry: Dict[str, List[Handler]] = defaultdict(list)


def subscribe(event_name: str):
    """
    Decorator to register an event handler.
    Usage:
        @subscribe("encounter.created")
        def handler(payload): ...
    """
    def _decorator(fn: Handler) -> Handler:
        _registry[event_name].append(fn)
        return fn
    return _decorator


def publish(event_name: str, payload: Dict[str, Any]) -> None:
    """
    Publish an event to in-process subscribers (Phase 0/1).
    Keep payloads ID-based to avoid cross-app imports.
    """
    for handler in _registry.get(event_name, []):
        handler(payload)
