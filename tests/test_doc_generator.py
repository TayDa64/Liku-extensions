
import pytest
from pathlib import Path
import json
from unittest.mock import MagicMock

# Add core to path to allow import
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from doc_generator import DocumentationGenerator, AgentMetadata, CoreModule

@pytest.fixture
def mock_project(tmp_path: Path) -> Path:
    """Creates a mock project structure in a temporary directory."""
    project_root = tmp_path
    
    # Create core dir and a mock script
    core_dir = project_root / "core"
    core_dir.mkdir()
    core_script_content = """
# This is a description of the core script.

my_func_one() {
    echo "hello"
}

another_func() {
    echo "world"
}
"""
    (core_dir / "core_script.sh").write_text(core_script_content)

    # Create agents dir
    agents_dir = project_root / "agents"
    agents_dir.mkdir()

    # Agent 1: Uses agent.json
    agent1_dir = agents_dir / "agent-one"
    agent1_dir.mkdir()
    agent1_json = {
        "description": "Agent One from JSON.",
        "events_listen": ["event.one.listen"],
        "events_emit": ["event.one.emit"],
        "dependencies": ["jq"]
    }
    (agent1_dir / "agent.json").write_text(json.dumps(agent1_json))

    # Agent 2: Uses shell script comments
    agent2_dir = agents_dir / "agent-two"
    agent2_dir.mkdir()
    agent2_script_content = """
#!/usr/bin/env bash
# @description: Agent Two from comments.
# @listens: event.two.listen
# @emits: event.two.emit
# @depends: tmux

liku_event_emit "event.two.inferred"
"""
    (agent2_dir / "run.sh").write_text(agent2_script_content)
    
    # Agent 3: Malformed json, should fallback
    agent3_dir = agents_dir / "agent-three"
    agent3_dir.mkdir()
    (agent3_dir / "agent.json").write_text("{ not valid json }")
    agent3_script_content = "# @description: Agent Three fallback."
    (agent3_dir / "handler.sh").write_text(agent3_script_content)

    # Create docs dir
    (project_root / "docs").mkdir()
    
    return project_root

def test_generator_initialization(tmp_path):
    """Test DocumentationGenerator initializes paths correctly."""
    gen = DocumentationGenerator(tmp_path)
    assert gen.project_root == tmp_path
    assert gen.agents_dir == tmp_path / "agents"
    assert gen.core_dir == tmp_path / "core"
    assert gen.docs_dir == tmp_path / "docs"

def test_parse_agent_from_json(mock_project):
    """Test parsing agent metadata from a valid agent.json."""
    gen = DocumentationGenerator(mock_project)
    agent_dir = mock_project / "agents" / "agent-one"
    
    metadata = gen.parse_agent_metadata(agent_dir)
    
    assert metadata is not None
    assert metadata.name == "agent-one"
    assert metadata.description == "Agent One from JSON."
    assert metadata.events_listen == ["event.one.listen"]
    assert metadata.events_emit == ["event.one.emit"]
    assert metadata.dependencies == ["jq"]

def test_parse_agent_from_shell(mock_project):
    """Test parsing agent metadata from comments in .sh files."""
    gen = DocumentationGenerator(mock_project)
    agent_dir = mock_project / "agents" / "agent-two"
    
    metadata = gen.parse_agent_metadata(agent_dir)
    
    assert metadata is not None
    assert metadata.name == "agent-two"
    assert metadata.description == "Agent Two from comments."
    assert metadata.events_listen == ["event.two.listen"]
    # Should include both explicit and inferred events
    assert "event.two.emit" in metadata.events_emit
    assert "event.two.inferred" in metadata.events_emit
    assert metadata.dependencies == ["tmux"]

def test_parse_agent_fallback(mock_project):
    """Test that parsing falls back to shell if agent.json is malformed."""
    gen = DocumentationGenerator(mock_project)
    agent_dir = mock_project / "agents" / "agent-three"
    
    metadata = gen.parse_agent_metadata(agent_dir)
    
    assert metadata is not None
    assert metadata.description == "Agent Three fallback."

def test_parse_agent_non_existent(tmp_path):
    """Test parsing a non-existent agent directory returns None."""
    gen = DocumentationGenerator(tmp_path)
    metadata = gen.parse_agent_metadata(tmp_path / "non-existent-agent")
    assert metadata is None

def test_parse_core_module(mock_project):
    """Test parsing metadata from a core shell script."""
    gen = DocumentationGenerator(mock_project)
    script_path = mock_project / "core" / "core_script.sh"
    
    module = gen.parse_core_module(script_path)
    
    assert module.name == "core_script"
    assert module.description == "This is a description of the core script."
    assert "my_func_one" in module.functions
    assert "another_func" in module.functions

def test_generate_agent_reference(mock_project):
    """Test the generated markdown for the agent reference."""
    gen = DocumentationGenerator(mock_project)
    markdown = gen.generate_agent_reference()
    
    assert "# LIKU Agent Reference" in markdown
    assert "## agent-one" in markdown
    assert "Agent One from JSON." in markdown
    assert "`event.one.listen`" in markdown
    assert "## agent-two" in markdown
    assert "Agent Two from comments." in markdown
    assert "`event.two.inferred`" in markdown

def test_generate_core_reference(mock_project):
    """Test the generated markdown for the core reference."""
    gen = DocumentationGenerator(mock_project)
    markdown = gen.generate_core_reference()
    
    assert "# LIKU Core Modules Reference" in markdown
    assert "## core_script" in markdown
    assert "This is a description of the core script." in markdown
    assert "`my_func_one()`" in markdown

def test_generate_event_catalog(mock_project):
    """Test the generated markdown for the event catalog."""
    gen = DocumentationGenerator(mock_project)
    markdown = gen.generate_event_catalog()
    
    assert "# LIKU Event Catalog" in markdown
    assert "### `event.one.emit`" in markdown
    assert "- agent-one (emit)" in markdown
    assert "### `event.two.listen`" in markdown
    assert "- agent-two (listen)" in markdown

def test_generate_all_docs(mock_project):
    """Test that all doc files are written to the correct location."""
    gen = DocumentationGenerator(mock_project)
    gen.generate_all_docs()
    
    docs_dir = mock_project / "docs"
    assert (docs_dir / "agent-reference.md").exists()
    assert (docs_dir / "core-reference.md").exists()
    assert (docs_dir / "event-catalog.md").exists()
    
    content = (docs_dir / "agent-reference.md").read_text()
    assert "agent-one" in content
    assert "agent-two" in content
    assert "agent-three" in content
