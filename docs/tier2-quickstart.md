# LIKU Tier-2 Quick Start Guide

## For New Users

### Installation

```bash
# Clone the repository
git clone https://github.com/TayDa64/Liku-extensions.git
cd Liku-extensions

# Run enhanced installer
bash install.sh

# Activate environment
source ~/.bashrc
```

### Verify Installation

```bash
# Run health checks
liku doctor

# Check installed components
ls -la ~/.liku/

# View pre-flight results
cat ~/.liku/preflight-results.json | python3 -m json.tool
```

### First Agent Spawn

```bash
# Start the Bookkeeper TUI
liku bookkeeper

# In another terminal, spawn an agent
liku spawn build-agent

# Execute a command
liku exec --window general -- echo "Hello from LIKU!"

# View pane activity
bash ~/.liku/core/tmux-agent.sh list
```

## For Developers

### Running Tests

```bash
# Run watcher factory tests
cd tests
python3 test_watcher_factory.py

# Test state backend
python3 ~/.liku/core/state_backend.py ~/.liku/db/test.db

# Test recovery system
bash ~/.liku/core/tmux-recovery.sh scan
```

### Working with the State Backend

```python
from core.state_backend import StateBackend

# Initialize
db = StateBackend("~/.liku/db/liku.db")

# Create agent session
session_id = db.create_agent_session(
    "my-agent",
    "session-1",
    terminal_id="liku:0.0",
    pid=12345
)

# Log an event
db.log_event(
    "agent.spawn",
    {"agent": "my-agent", "terminal": "liku:0.0"},
    session_key="session-1"
)

# Query events
events = db.get_events(event_type="agent.spawn", limit=10)
for event in events:
    print(f"{event['event_type']}: {event['payload']}")
```

### Using the File Watcher

```python
from core.watcher_factory import WatcherFactory

# Create watcher with 0.5s debounce
factory = WatcherFactory(debounce_window=0.5)

# Watch a directory
for event in factory.watch("/path/to/watch", recursive=True):
    print(f"{event.kind}: {event.path}")
```

### Generating Documentation

```bash
# Generate all documentation
python3 ~/.liku/core/doc_generator.py $(pwd)

# View generated docs
ls -la docs/
cat docs/agent-reference.md
cat docs/core-reference.md
cat docs/event-catalog.md
```

### Adding Agent Metadata

In your agent's `run.sh` or `handler.sh`:

```bash
#!/usr/bin/env bash
# @description: My custom agent that does awesome things
# @listens: custom.event.trigger
# @emits: custom.event.completed
# @depends: curl, jq

# Your agent code here
```

Or create `agent.json`:

```json
{
  "description": "My custom agent that does awesome things",
  "events_listen": ["custom.event.trigger"],
  "events_emit": ["custom.event.completed"],
  "dependencies": ["curl", "jq"]
}
```

### Configuring Security Policies

Edit `~/.liku/config/agents.yaml`:

```yaml
agents:
  - name: my-agent
    description: "Custom agent"
    approval_mode: ask
    policies:
      allow_network: true
      allowed_commands: ["curl", "wget", "jq"]
      blocked_paths: ["/etc", "/sys"]
      timeout_seconds: 300
      sandbox_mode: tmux
```

### Running Recovery

```bash
# Scan for issues
bash ~/.liku/core/tmux-recovery.sh scan

# Run recovery
bash ~/.liku/core/tmux-recovery.sh run

# View recovery log
bash ~/.liku/core/tmux-recovery.sh log 50
```

## For Contributors

### Project Structure

```
Liku-extensions/
├── core/                    # Core system modules
│   ├── preflight-check.sh   # Environment validation
│   ├── watcher_factory.py   # Cross-platform watchers
│   ├── state_backend.py     # SQLite state management
│   ├── tmux-recovery.sh     # Recovery automation
│   └── doc_generator.py     # Documentation generation
├── schemas/                 # JSON schemas
│   ├── events.schema.json   # Event payload definitions
│   └── agents.schema.json   # Agent configuration schema
├── tests/                   # Test suites
│   └── test_watcher_factory.py
├── agents/                  # Agent implementations
├── bookkeeper/              # TUI components
├── config/                  # Configuration files
└── docs/                    # Documentation

```

### Development Workflow

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/my-optimization
   ```

2. **Implement Changes**
   - Follow existing code style
   - Add type hints to Python code
   - Write unit tests
   - Update documentation

3. **Test Locally**
   ```bash
   # Run all tests
   python3 tests/test_watcher_factory.py
   
   # Test installation
   bash install.sh
   
   # Validate against schemas
   # (TODO: Add validation script)
   ```

4. **Generate Documentation**
   ```bash
   python3 core/doc_generator.py .
   ```

5. **Submit PR**
   - Reference related issues
   - Include test results
   - Update CHANGELOG.md

### Code Style Guidelines

**Shell Scripts**:
- Use `set -euo pipefail`
- Quote all variables
- Use `local` for function variables
- Add comments for complex logic

**Python**:
- Type hints for all functions
- Docstrings (Google style)
- PEP 8 formatting
- Error handling with specific exceptions

**Example Python Function**:
```python
def process_event(event_type: str, payload: Dict[str, Any]) -> bool:
    """
    Process an event and update state.
    
    Args:
        event_type: Type of event (e.g., 'agent.spawn')
        payload: Event payload dictionary
        
    Returns:
        True if processed successfully, False otherwise
        
    Raises:
        ValueError: If event_type is invalid
    """
    if not event_type:
        raise ValueError("event_type cannot be empty")
    
    # Processing logic here
    return True
```

## Common Tasks

### View Event Stream

```bash
# Real-time event streaming
liku event stream

# Filter by type (manual grep)
liku event stream | grep "agent.spawn"
```

### Check Agent Status

```bash
# Via Bookkeeper TUI
liku bookkeeper
# Press 'D' to describe selected agent

# Via CLI
bash ~/.liku/core/tmux-agent.sh list
```

### Debug Issues

```bash
# Check logs
tail -f ~/.liku/logs/tmux-recovery.log

# Inspect database
sqlite3 ~/.liku/db/liku.db "SELECT * FROM event_log ORDER BY created_at DESC LIMIT 10"

# Run doctor
liku doctor
```

### Manual Recovery

```bash
# List dead panes
tmux list-panes -a -F '#{session_name}:#{window_index}.#{pane_index} #{pane_dead}' | grep " 1$"

# Kill specific pane
tmux kill-pane -t <pane_id>

# Or run automated recovery
bash ~/.liku/core/tmux-recovery.sh run
```

## Troubleshooting

### "Pre-flight checks failed"

Check `~/.liku/preflight-results.json`:
```bash
cat ~/.liku/preflight-results.json | python3 -m json.tool
```

Install missing dependencies based on recommendations.

### "Database locked"

SQLite uses WAL mode, but if you see locks:
```bash
# Check for long-running connections
lsof ~/.liku/db/liku.db

# Force checkpoint
sqlite3 ~/.liku/db/liku.db "PRAGMA wal_checkpoint(FULL)"
```

### "Watcher not available"

Install platform-specific watcher:
- **Linux**: `sudo apt-get install inotify-tools`
- **macOS**: `brew install fswatch`
- **Windows**: PowerShell should be available by default

### "Recovery not working"

Check tmux is running:
```bash
tmux list-sessions

# If empty, create base session:
bash ~/.liku/core/tmux-recovery.sh run
```

## Performance Tuning

### SQLite Optimization

```bash
# Vacuum database (reclaim space)
sqlite3 ~/.liku/db/liku.db "VACUUM"

# Analyze for query optimization
sqlite3 ~/.liku/db/liku.db "ANALYZE"
```

### Event Log Rotation

```bash
# Archive old events (manual)
sqlite3 ~/.liku/db/liku.db "DELETE FROM event_log WHERE created_at < date('now', '-30 days')"
```

### Debounce Configuration

Adjust debounce window in Python:
```python
factory = WatcherFactory(debounce_window=1.0)  # Increase to 1 second
```

## Resources

- **Architecture**: `docs/architecture.md`
- **Protocol**: `docs/protocol.md`
- **Implementation Roadmap**: `docs/tier2-implementation-roadmap.md`
- **Full Review**: `docs/tier2-optimization-review.md`
- **Bookkeeper Guide**: `docs/bookkeeper.md`

## Getting Help

1. **Documentation**: Check the `docs/` directory
2. **Issues**: Open an issue on GitHub
3. **Discussions**: Use GitHub Discussions for questions
4. **Events**: Use `liku event stream` to debug in real-time

## Next Steps

After getting familiar with the basics:

1. Read the [Architecture Document](architecture.md)
2. Explore the [Protocol Specification](protocol.md)
3. Review the [Implementation Roadmap](tier2-implementation-roadmap.md)
4. Contribute to Phase 3 features!

---

**Happy orchestrating!** 🚀
