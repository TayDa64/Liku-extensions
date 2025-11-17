#!/usr/bin/env python3
"""
Quick setup script for LIKU development environment.
Installs the package in editable mode with all dependencies.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Install LIKU package in development mode."""
    project_root = Path(__file__).parent
    
    print("=" * 60)
    print("LIKU Development Environment Setup")
    print("=" * 60)
    print()
    
    # Check Python version
    if sys.version_info < (3, 9):
        print("❌ Error: Python 3.9 or higher required")
        print(f"   Current version: {sys.version}")
        sys.exit(1)
    
    print(f"✅ Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print()
    
    # Upgrade pip
    print("📦 Upgrading pip...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    print()
    
    # Install package in editable mode with dev dependencies
    print("📦 Installing LIKU package in editable mode...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
        cwd=project_root,
        check=True
    )
    print()
    
    # Verify installation
    print("🔍 Verifying installation...")
    try:
        import liku
        import pytest
        print(f"✅ liku package installed (version {liku.__version__})")
        print(f"✅ pytest installed (version {pytest.__version__})")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("✅ Setup complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Run tests:           pytest")
    print("  2. Run with coverage:   pytest --cov=core")
    print("  3. Format code:         black core tests")
    print("  4. Check types:         mypy core")
    print()
    print("See docs/PHASE2.5-IMPROVEMENTS.md for more information.")
    print()


if __name__ == "__main__":
    main()
