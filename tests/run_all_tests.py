#!/usr/bin/env python3
"""
Test runner for all LIKU tests.
Discovers and runs all unit and integration tests.
"""

import sys
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))


def run_tests(test_type="all", verbose=2):
    """
    Run LIKU tests.
    
    Args:
        test_type: Type of tests to run ('unit', 'integration', or 'all')
        verbose: Verbosity level (0-2)
    
    Returns:
        True if all tests passed, False otherwise
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Discover tests
    if test_type in ("unit", "all"):
        print("Discovering unit tests...")
        unit_tests = loader.discover(
            start_dir=str(Path(__file__).parent),
            pattern="test_*.py",
            top_level_dir=str(Path(__file__).parent)
        )
        suite.addTests(unit_tests)
    
    if test_type in ("integration", "all"):
        print("Discovering integration tests...")
        integration_tests = loader.discover(
            start_dir=str(Path(__file__).parent / "integration"),
            pattern="test_*.py",
            top_level_dir=str(Path(__file__).parent)
        )
        suite.addTests(integration_tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=verbose)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✅ All tests passed!")
        return True
    else:
        print("\n❌ Some tests failed!")
        return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run LIKU tests")
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "all"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=2,
        help="Increase verbosity"
    )
    
    args = parser.parse_args()
    
    success = run_tests(test_type=args.type, verbose=args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
