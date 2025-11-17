"""
Pytest configuration and shared fixtures for LIKU tests.
"""

import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Generator

import pytest

# Add core directory to path for imports
core_dir = Path(__file__).parent.parent / "core"
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))

from event_bus import EventBus
from state_backend import StateBackend
from tmux_manager import TmuxManager
from liku_client import LikuClient
from liku_daemon import LikuDaemon


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_db_path(temp_dir: Path) -> str:
    """Provide a path for a test database."""
    return str(temp_dir / "test_liku.db")


@pytest.fixture
def test_events_dir(temp_dir: Path) -> str:
    """Provide a directory for test event files."""
    events_dir = temp_dir / "events"
    events_dir.mkdir()
    return str(events_dir)


@pytest.fixture
def state_backend(test_db_path: str) -> Generator[StateBackend, None, None]:
    """Create a StateBackend instance with a temporary database."""
    backend = StateBackend(test_db_path)
    yield backend
    # Cleanup connections properly to avoid Windows file lock issues
    try:
        backend.close_all_connections()
    except Exception:
        pass
    # Give Windows time to release file locks
    import time
    time.sleep(0.1)


@pytest.fixture
def event_bus(test_events_dir: str, test_db_path: str) -> EventBus:
    """Create an EventBus instance with temporary paths."""
    return EventBus(events_dir=test_events_dir, db_path=test_db_path)


@pytest.fixture
def tmux_manager(event_bus: EventBus) -> TmuxManager:
    """Create a TmuxManager instance."""
    return TmuxManager(event_bus=event_bus)


@pytest.fixture
def daemon_port() -> int:
    """Provide a TCP port for test daemon."""
    # Use port 0 to let OS assign available port, or use fixed test port
    return 13338  # Different from default to avoid conflicts


@pytest.fixture
def liku_daemon(temp_dir: Path, daemon_port: int) -> Generator[LikuDaemon, None, None]:
    """
    Start a LIKU daemon for testing (TCP mode for cross-platform compatibility).
    """
    db_path = str(temp_dir / "daemon_test.db")
    events_dir = str(temp_dir / "events")
    Path(events_dir).mkdir(exist_ok=True)
    
    daemon = LikuDaemon(
        tcp_port=daemon_port,
        db_path=db_path,
        events_dir=events_dir,
        use_tcp=True  # Force TCP for cross-platform tests
    )
    
    # Start daemon in background thread
    daemon_thread = threading.Thread(target=daemon.start, daemon=True)
    daemon_thread.start()
    
    # Wait for daemon to be ready
    time.sleep(0.5)
    
    yield daemon
    
    # Cleanup
    daemon.stop()


@pytest.fixture
def liku_client(daemon_port: int, liku_daemon: LikuDaemon) -> LikuClient:
    """
    Create a LIKU client connected to the test daemon.
    """
    client = LikuClient(tcp_port=daemon_port, use_tcp=True)
    
    # Verify connection
    max_retries = 10
    for i in range(max_retries):
        try:
            client.ping()
            break
        except ConnectionError:
            if i == max_retries - 1:
                raise
            time.sleep(0.1)
    
    return client


@pytest.fixture
def mock_tmux_env(monkeypatch):
    """Mock environment variables for tmux tests."""
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1234,0")
    monkeypatch.setenv("TMUX_PANE", "%0")


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset any singleton instances between tests."""
    # Add any singleton reset logic here if needed
    yield
    # Cleanup after test


# Markers for conditional test execution
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "requires_tmux: marks tests that require tmux to be running"
    )
    config.addinivalue_line(
        "markers", "requires_daemon: marks tests that require the daemon to be running"
    )


# Skip tests based on platform
def pytest_collection_modifyitems(config, items):
    """Modify test collection to skip platform-specific tests."""
    skip_windows_unix = pytest.mark.skip(reason="UNIX sockets not supported on Windows")
    skip_requires_tmux = pytest.mark.skip(reason="tmux not available")
    
    # Check if tmux is available
    import subprocess
    tmux_available = False
    try:
        subprocess.run(["tmux", "-V"], capture_output=True, check=True)
        tmux_available = True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    
    for item in items:
        # Skip UNIX socket tests on Windows
        if sys.platform == "win32" and "unix_socket" in item.nodeid.lower():
            item.add_marker(skip_windows_unix)
        
        # Skip tmux tests if tmux not available
        if "requires_tmux" in [mark.name for mark in item.iter_markers()]:
            if not tmux_available:
                item.add_marker(skip_requires_tmux)
