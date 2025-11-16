#!/usr/bin/env python3
"""
Automated documentation generation from agent metadata and codebase structure.
Parses comment blocks from agent scripts and generates comprehensive guides.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class AgentMetadata:
    """Metadata extracted from an agent."""
    name: str
    description: str
    events_listen: List[str]
    events_emit: List[str]
    commands: List[str]
    dependencies: List[str]
    path: Path


@dataclass
class CoreModule:
    """Metadata for a core system module."""
    name: str
    description: str
    functions: List[str]
    path: Path


class DocumentationGenerator:
    """Generate documentation from codebase structure and metadata."""
    
    def __init__(self, project_root: Path):
        """
        Initialize documentation generator.
        
        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root)
        self.agents_dir = self.project_root / "agents"
        self.core_dir = self.project_root / "core"
        self.docs_dir = self.project_root / "docs"
    
    def parse_agent_metadata(self, agent_dir: Path) -> Optional[AgentMetadata]:
        """
        Parse metadata from agent directory.
        
        Args:
            agent_dir: Path to agent directory
            
        Returns:
            AgentMetadata if successfully parsed, None otherwise
        """
        if not agent_dir.is_dir():
            return None
        
        agent_name = agent_dir.name
        
        # Look for metadata in agent.json first
        agent_json = agent_dir / "agent.json"
        if agent_json.exists():
            try:
                with open(agent_json) as f:
                    data = json.load(f)
                    
                return AgentMetadata(
                    name=agent_name,
                    description=data.get("description", "No description available"),
                    events_listen=data.get("events_listen", []),
                    events_emit=data.get("events_emit", []),
                    commands=data.get("commands", []),
                    dependencies=data.get("dependencies", []),
                    path=agent_dir
                )
            except json.JSONDecodeError:
                pass
        
        # Fall back to parsing run.sh and handler.sh
        description = "No description available"
        events_listen = []
        events_emit = []
        commands = []
        dependencies = []
        
        for script_name in ["run.sh", "handler.sh"]:
            script_path = agent_dir / script_name
            if not script_path.exists():
                continue
            
            with open(script_path) as f:
                content = f.read()
            
            # Parse special comment blocks
            # @description: Agent description
            desc_match = re.search(r'##?\s*@description:\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
            if desc_match:
                description = desc_match.group(1).strip()
            
            # @listens: event.type
            listens_matches = re.finditer(r'##?\s*@listens:\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
            for match in listens_matches:
                events_listen.append(match.group(1).strip())
            
            # @emits: event.type
            emits_matches = re.finditer(r'##?\s*@emits:\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
            for match in emits_matches:
                events_emit.append(match.group(1).strip())
            
            # @depends: dependency
            dep_matches = re.finditer(r'##?\s*@depends:\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
            for match in dep_matches:
                dependencies.append(match.group(1).strip())
            
            # Extract liku_event_emit calls
            emit_calls = re.finditer(r'liku_event_emit\s+"([^"]+)"', content)
            for match in emit_calls:
                event_type = match.group(1)
                if event_type not in events_emit:
                    events_emit.append(event_type)
        
        return AgentMetadata(
            name=agent_name,
            description=description,
            events_listen=events_listen,
            events_emit=events_emit,
            commands=commands,
            dependencies=dependencies,
            path=agent_dir
        )
    
    def parse_core_module(self, script_path: Path) -> CoreModule:
        """
        Parse metadata from a core module script.
        
        Args:
            script_path: Path to core script
            
        Returns:
            CoreModule metadata
        """
        name = script_path.stem
        description = "Core system module"
        functions = []
        
        if not script_path.exists():
            return CoreModule(name, description, functions, script_path)
        
        with open(script_path) as f:
            content = f.read()
        
        # Parse description from header comment
        desc_match = re.search(r'^#\s*(.+?)(?:\n\n|\n#|$)', content, re.MULTILINE)
        if desc_match:
            description = desc_match.group(1).strip()
        
        # Extract function definitions
        func_matches = re.finditer(r'^(\w+)\(\)\s*\{', content, re.MULTILINE)
        for match in func_matches:
            functions.append(match.group(1))
        
        return CoreModule(name, description, functions, script_path)
    
    def generate_agent_reference(self) -> str:
        """Generate agent reference documentation."""
        if not self.agents_dir.exists():
            return "# Agent Reference\n\nNo agents directory found.\n"
        
        agents = []
        for agent_dir in sorted(self.agents_dir.iterdir()):
            if agent_dir.is_dir() and not agent_dir.name.startswith('.'):
                metadata = self.parse_agent_metadata(agent_dir)
                if metadata:
                    agents.append(metadata)
        
        # Build markdown
        lines = [
            "# LIKU Agent Reference",
            "",
            "This document provides a comprehensive reference for all agents in the LIKU system.",
            "",
            "## Table of Contents",
            ""
        ]
        
        for agent in agents:
            lines.append(f"- [{agent.name}](#{agent.name.lower().replace('-', '')})")
        
        lines.append("")
        
        # Agent details
        for agent in agents:
            lines.extend([
                f"## {agent.name}",
                "",
                f"**Description:** {agent.description}",
                "",
                f"**Location:** `{agent.path.relative_to(self.project_root)}`",
                ""
            ])
            
            if agent.events_listen:
                lines.append("**Listens to events:**")
                for event in agent.events_listen:
                    lines.append(f"- `{event}`")
                lines.append("")
            
            if agent.events_emit:
                lines.append("**Emits events:**")
                for event in agent.events_emit:
                    lines.append(f"- `{event}`")
                lines.append("")
            
            if agent.dependencies:
                lines.append("**Dependencies:**")
                for dep in agent.dependencies:
                    lines.append(f"- `{dep}`")
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_core_reference(self) -> str:
        """Generate core modules reference documentation."""
        if not self.core_dir.exists():
            return "# Core Modules Reference\n\nNo core directory found.\n"
        
        modules = []
        for script_path in sorted(self.core_dir.glob("*.sh")):
            if script_path.is_file():
                module = self.parse_core_module(script_path)
                modules.append(module)
        
        # Build markdown
        lines = [
            "# LIKU Core Modules Reference",
            "",
            "This document provides details on core system modules.",
            "",
            "## Table of Contents",
            ""
        ]
        
        for module in modules:
            lines.append(f"- [{module.name}](#{module.name.lower().replace('-', '').replace('_', '')})")
        
        lines.append("")
        
        # Module details
        for module in modules:
            lines.extend([
                f"## {module.name}",
                "",
                f"**Description:** {module.description}",
                "",
                f"**Location:** `{module.path.relative_to(self.project_root)}`",
                ""
            ])
            
            if module.functions:
                lines.append("**Functions:**")
                for func in module.functions:
                    lines.append(f"- `{func}()`")
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_event_catalog(self) -> str:
        """Generate event catalog from all agents and modules."""
        events: Dict[str, List[str]] = {}
        
        # Collect events from agents
        if self.agents_dir.exists():
            for agent_dir in self.agents_dir.iterdir():
                if agent_dir.is_dir() and not agent_dir.name.startswith('.'):
                    metadata = self.parse_agent_metadata(agent_dir)
                    if not metadata:
                        continue
                    
                    for event in metadata.events_emit:
                        if event not in events:
                            events[event] = []
                        events[event].append(f"{metadata.name} (emit)")
                    
                    for event in metadata.events_listen:
                        if event not in events:
                            events[event] = []
                        events[event].append(f"{metadata.name} (listen)")
        
        # Build markdown
        lines = [
            "# LIKU Event Catalog",
            "",
            "This document catalogs all events used in the LIKU system.",
            "",
            "## Events",
            ""
        ]
        
        for event_type in sorted(events.keys()):
            lines.extend([
                f"### `{event_type}`",
                "",
                "**Used by:**"
            ])
            
            for usage in events[event_type]:
                lines.append(f"- {usage}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_all_docs(self):
        """Generate all documentation files."""
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate agent reference
        agent_ref = self.generate_agent_reference()
        (self.docs_dir / "agent-reference.md").write_text(agent_ref)
        print(f"Generated: {self.docs_dir / 'agent-reference.md'}")
        
        # Generate core reference
        core_ref = self.generate_core_reference()
        (self.docs_dir / "core-reference.md").write_text(core_ref)
        print(f"Generated: {self.docs_dir / 'core-reference.md'}")
        
        # Generate event catalog
        event_catalog = self.generate_event_catalog()
        (self.docs_dir / "event-catalog.md").write_text(event_catalog)
        print(f"Generated: {self.docs_dir / 'event-catalog.md'}")


def main():
    """CLI entry point."""
    import sys
    
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <project_root>")
        sys.exit(1)
    
    project_root = Path(sys.argv[1])
    if not project_root.exists():
        print(f"Error: Project root does not exist: {project_root}")
        sys.exit(1)
    
    generator = DocumentationGenerator(project_root)
    generator.generate_all_docs()
    print("\nDocumentation generation complete!")


if __name__ == "__main__":
    main()
