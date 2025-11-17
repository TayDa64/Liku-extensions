# LIKU Quick Start Guide

## For Developers

### Prerequisites

- Python 3.9 or higher
- Git
- tmux 3.0+ (for full functionality)
- SQLite 3.30+

### Installation

#### Option 1: Automated Setup (Recommended)

```bash
# Clone repository
git clone https://github.com/TayDa64/Liku-extensions.git
cd Liku-extensions

# Run setup script
python setup_dev.py
```

#### Option 2: Manual Setup

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Or just core dependencies
pip install -e .
```

### Verify Installation

```bash
# Check package installed
python -c "import liku; print(liku.__version__)"

# Run tests
pytest

# Check coverage
pytest --cov=core --cov-report=html
# Open htmlcov/index.html
```

## Running the Daemon

### Start Daemon (Cross-Platform)

```bash
# Auto-detect mode (TCP on Windows, UNIX on Linux/macOS)
python -m liku.liku_daemon

# Force TCP mode
python -m liku.liku_daemon --tcp --port 13337

# Force UNIX socket mode (Linux/macOS only)
python -m liku.liku_daemon --unix --socket ~/.liku/liku.sock
```

### Use Client

```python
from liku_client import LikuClient

# Connect (auto-detect)
client = LikuClient()

# Emit event
client.emit_event("test.event", {"data": "hello"})

# Get recent events
events = client.get_events(limit=10)

# List tmux sessions
sessions = client.list_sessions()

# Create tmux pane
pane = client.create_pane(
    session="liku",
    window="agents",
    name="test-agent"
)
```

## Testing

### Run All Tests

```bash
pytest
```

### Run Specific Tests

```bash
# By file
pytest tests/test_event_bus_pytest.py

# By marker
pytest -m "not slow"  # Skip slow tests
pytest -m integration  # Only integration tests

# By keyword
pytest -k "event"  # Tests matching "event"
```

### Coverage Reports

```bash
# Terminal report
pytest --cov=core --cov-report=term-missing

# HTML report
pytest --cov=core --cov-report=html
open htmlcov/index.html

# XML report (for CI)
pytest --cov=core --cov-report=xml
```

### Platform-Specific Testing

```bash
# Windows (skip Unix-specific tests)
pytest -m "not requires_tmux and not requires_daemon"

# Linux/macOS (full suite)
pytest
```

## Code Quality

### Format Code

```bash
# Check formatting
black --check core tests

# Auto-format
black core tests
```

### Type Checking

```bash
mypy core
```

### Linting

```bash
pylint core
```

## Project Structure

```
Liku-extensions/
├── core/                  # Python package (pip install -e .)
│   ├── __init__.py       # Package exports
│   ├── event_bus.py      # Event system
│   ├── state_backend.py  # SQLite persistence
│   ├── tmux_manager.py   # Tmux orchestration
│   ├── liku_daemon.py    # Unified API server
│   └── liku_client.py    # Client library
├── tests/                 # pytest test suite
│   ├── conftest.py       # Shared fixtures
│   └── test_*.py         # Test files
├── docs/                  # Documentation
│   └── PHASE2.5-IMPROVEMENTS.md
├── pyproject.toml         # Modern Python config
├── setup_dev.py          # Development setup script
└── README.md             # Main documentation
```

## Common Tasks

### Add New Test

```python
# tests/test_mynew_feature.py
import pytest

def test_my_feature(event_bus, state_backend):
    """Test description."""
    # Fixtures automatically available
    event_bus.emit("test.event", {})
    
    events = state_backend.get_events(limit=1)
    assert len(events) == 1
```

### Add New Fixture

```python
# tests/conftest.py
@pytest.fixture
def my_fixture(temp_dir):
    """My custom fixture."""
    # Setup
    obj = MyClass(temp_dir)
    yield obj
    # Teardown (optional)
    obj.cleanup()
```

### Run Specific Test Class

```python
# Test class
class TestMyFeature:
    def test_case_1(self):
        pass
    
    def test_case_2(self):
        pass

# Run: pytest tests/test_file.py::TestMyFeature
```

## CI/CD

Tests run automatically on:
- Every push to `main` or `develop`
- Every pull request

See test results at: **Actions** tab on GitHub

### Local CI Simulation

```bash
# Run what CI runs
pytest --cov=core --cov-report=xml
black --check core tests
mypy core
```

## Troubleshooting

### Import Errors

```bash
# Ensure package installed
pip install -e .

# Check installation
pip show liku
```

### Test Failures

```bash
# Verbose output
pytest -v

# Show print statements
pytest -s

# Drop into debugger on failure
pytest --pdb

# Last failed tests only
pytest --lf
```

### Coverage Too Low

```bash
# See what's not covered
pytest --cov=core --cov-report=term-missing

# Focus on uncovered lines
pytest --cov=core --cov-report=html
# Open htmlcov/index.html and look for red lines
```

### Windows Issues

```bash
# Use TCP mode for daemon/client tests
pytest -m "not requires_tmux"

# Or run in WSL
wsl
pytest
```

## Next Steps

1. **Read** `docs/PHASE2.5-IMPROVEMENTS.md` for architectural details
2. **Run** `pytest` to see current test status
3. **Explore** fixtures in `tests/conftest.py`
4. **Write** your first test with fixtures
5. **Contribute** by fixing failing tests or adding features

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [LIKU Architecture](docs/architecture.md)
- [Phase 2.5 Changes](docs/PHASE2.5-IMPROVEMENTS.md)
- [Contributing Guide](CONTRIBUTING.md) *(coming soon)*

## Getting Help

- **Issues**: Open a GitHub issue
- **Discussions**: GitHub Discussions
- **Docs**: See `docs/` directory

---

Happy coding! 🚀
