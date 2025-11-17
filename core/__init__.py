"""LIKU - AI-Terminal Protocol Core Package"""

__version__ = "0.9.0"

try:
    from .event_bus import EventBus
    from .state_backend import StateBackend
    from .tmux_manager import TmuxManager
    from .watcher_factory import WatcherFactory, WatcherNotAvailable
except ImportError:
    # Handle case where dependencies aren't fully loaded yet
    pass

__all__ = [
    "EventBus",
    "StateBackend",
    "TmuxManager",
    "WatcherFactory",
    "WatcherNotAvailable",
]
