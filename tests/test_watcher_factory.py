#!/usr/bin/env python3
"""
Unit tests for the WatcherFactory module.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from watcher_factory import Debouncer, WatchCommand, WatcherFactory, WatcherNotAvailable


class DebouncerTests(unittest.TestCase):
    """Tests for the Debouncer class."""
    
    def test_initial_event_is_emitted(self):
        """First event should always be emitted."""
        debouncer = Debouncer(window=0.5)
        self.assertTrue(debouncer.should_emit("/path/file.txt", "modified"))
    
    def test_rapid_events_are_debounced(self):
        """Rapid successive events should be debounced."""
        debouncer = Debouncer(window=0.5)
        self.assertTrue(debouncer.should_emit("/path/file.txt", "modified"))
        self.assertFalse(debouncer.should_emit("/path/file.txt", "modified"))
    
    def test_different_paths_not_debounced(self):
        """Events for different paths should not interfere."""
        debouncer = Debouncer(window=0.5)
        self.assertTrue(debouncer.should_emit("/path/file1.txt", "modified"))
        self.assertTrue(debouncer.should_emit("/path/file2.txt", "modified"))
    
    def test_reset_clears_state(self):
        """Reset should clear debouncer state."""
        debouncer = Debouncer(window=0.5)
        debouncer.should_emit("/path/file.txt", "modified")
        debouncer.reset()
        self.assertTrue(debouncer.should_emit("/path/file.txt", "modified"))


class WatcherFactoryTests(unittest.TestCase):
    """Tests for the WatcherFactory class."""
    
    def test_selects_inotify_on_linux(self):
        """Should select inotifywait on Linux systems."""
        factory = WatcherFactory()
        with patch("platform.system", return_value="Linux"), \
             patch("shutil.which", return_value="/usr/bin/inotifywait"), \
             tempfile.TemporaryDirectory() as tmpdir:
            
            factory._system = "Linux"
            cmd = factory.build(tmpdir)
            self.assertEqual(cmd.runner, "inotifywait")
            self.assertIn("inotifywait", cmd.args[0])
    
    def test_selects_fswatch_on_macos(self):
        """Should select fswatch on macOS systems."""
        factory = WatcherFactory()
        with patch("platform.system", return_value="Darwin"), \
             patch("shutil.which", return_value="/usr/local/bin/fswatch"), \
             tempfile.TemporaryDirectory() as tmpdir:
            
            factory._system = "Darwin"
            cmd = factory.build(tmpdir)
            self.assertEqual(cmd.runner, "fswatch")
            self.assertIn("fswatch", cmd.args[0])
    
    def test_raises_when_no_watcher_available(self):
        """Should raise WatcherNotAvailable when no watcher found."""
        factory = WatcherFactory()
        with patch("platform.system", return_value="Unknown"), \
             patch("shutil.which", return_value=None), \
             tempfile.TemporaryDirectory() as tmpdir:
            
            factory._system = "Unknown"
            with self.assertRaises(WatcherNotAvailable):
                factory.build(tmpdir)
    
    def test_recursive_flag_included(self):
        """Should include recursive flag when requested."""
        factory = WatcherFactory()
        with patch("platform.system", return_value="Linux"), \
             patch("shutil.which", return_value="/usr/bin/inotifywait"), \
             tempfile.TemporaryDirectory() as tmpdir:
            
            factory._system = "Linux"
            cmd = factory.build(tmpdir, recursive=True)
            self.assertIn("-r", cmd.args)
    
    def test_normalize_output_pipe_delimiter(self):
        """Should parse pipe-delimited output correctly."""
        factory = WatcherFactory()
        event = factory.normalize_output("/path/to/file.txt|modified", delimiter='|')
        
        self.assertIsNotNone(event)
        self.assertEqual(event.path, "/path/to/file.txt")
        self.assertEqual(event.kind, "modified")
    
    def test_normalize_output_space_delimiter(self):
        """Should parse space-delimited output as fallback."""
        factory = WatcherFactory()
        event = factory.normalize_output("/path/to/file.txt modify", delimiter='\n')
        
        self.assertIsNotNone(event)
        self.assertEqual(event.path, "/path/to/file.txt")
        self.assertEqual(event.kind, "modified")
    
    def test_normalize_output_handles_malformed_input(self):
        """Should handle malformed input gracefully."""
        factory = WatcherFactory()
        
        # Empty input
        self.assertIsNone(factory.normalize_output("", delimiter='|'))
        
        # Single token
        self.assertIsNone(factory.normalize_output("just-one-token", delimiter='|'))
        
        # Whitespace only
        self.assertIsNone(factory.normalize_output("   \n  ", delimiter='|'))
    
    def test_normalize_output_maps_event_kinds(self):
        """Should map various event kinds to standardized types."""
        factory = WatcherFactory()
        
        test_cases = [
            ("file.txt|modify", "modified"),
            ("file.txt|changed", "modified"),
            ("file.txt|create", "created"),
            ("file.txt|delete", "deleted"),
            ("file.txt|moved_to", "created"),
            ("file.txt|moved_from", "deleted"),
        ]
        
        for raw, expected_kind in test_cases:
            factory._debouncer.reset()  # Reset to avoid debouncing
            event = factory.normalize_output(raw, delimiter='|')
            self.assertIsNotNone(event, f"Failed to parse: {raw}")
            self.assertEqual(event.kind, expected_kind, f"Wrong kind for: {raw}")
    
    def test_directory_validation(self):
        """Should validate directory exists before building watcher."""
        factory = WatcherFactory()
        with self.assertRaises(ValueError):
            factory.build("/nonexistent/directory/path")


class IntegrationTests(unittest.TestCase):
    """Integration tests for the watcher system."""
    
    @patch("subprocess.Popen")
    def test_watch_yields_events(self, mock_popen):
        """Should yield events when watching a directory."""
        factory = WatcherFactory()
        
        # Mock process with test output
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = [
            "/tmp/test.txt|modified\n",
            "/tmp/test2.txt|created\n",
            ""  # End of output
        ]
        mock_popen.return_value = mock_process
        
        with patch("platform.system", return_value="Linux"), \
             patch("shutil.which", return_value="/usr/bin/inotifywait"), \
             tempfile.TemporaryDirectory() as tmpdir:
            
            factory._system = "Linux"
            events = list(factory.watch(tmpdir))
            
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0].path, "/tmp/test.txt")
            self.assertEqual(events[0].kind, "modified")
            self.assertEqual(events[1].path, "/tmp/test2.txt")
            self.assertEqual(events[1].kind, "created")


def run_tests():
    """Run all test suites."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(DebouncerTests))
    suite.addTests(loader.loadTestsFromTestCase(WatcherFactoryTests))
    suite.addTests(loader.loadTestsFromTestCase(IntegrationTests))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    exit(run_tests())
