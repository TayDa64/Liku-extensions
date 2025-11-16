#!/usr/bin/env python3
"""
Cross-platform file watcher adapter with defensive output normalization
and debounce mechanism.
"""

import os
import platform
import shutil
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional


@dataclass
class WatchCommand:
    """Represents a platform-specific watch command configuration."""
    runner: str
    args: list[str]
    delimiter: str = '\n'


@dataclass
class WatchEvent:
    """Normalized watch event with path and event kind."""
    path: str
    kind: str
    timestamp: float


class WatcherNotAvailable(RuntimeError):
    """Raised when no suitable file watcher is available on the platform."""
    pass


class Debouncer:
    """Debounce mechanism to handle rapid-fire events."""
    
    def __init__(self, window: float = 0.5):
        """
        Initialize debouncer.
        
        Args:
            window: Time window in seconds to debounce events
        """
        self._window = window
        self._last_events: dict[str, float] = defaultdict(float)
    
    def should_emit(self, path: str, kind: str) -> bool:
        """
        Check if an event should be emitted based on debounce logic.
        
        Args:
            path: File path
            kind: Event kind
            
        Returns:
            True if event should be emitted, False if debounced
        """
        key = f"{path}:{kind}"
        now = time.time()
        last_time = self._last_events[key]
        
        if now - last_time >= self._window:
            self._last_events[key] = now
            return True
        return False
    
    def reset(self):
        """Reset debouncer state."""
        self._last_events.clear()


class WatcherFactory:
    """Factory for creating platform-specific file watchers."""
    
    def __init__(self, debounce_window: float = 0.5):
        """
        Initialize watcher factory.
        
        Args:
            debounce_window: Time window for debouncing events
        """
        self._system = platform.system()
        self._debouncer = Debouncer(window=debounce_window)
    
    def build(self, directory: str, recursive: bool = True) -> WatchCommand:
        """
        Build a platform-specific watch command.
        
        Args:
            directory: Directory to watch
            recursive: Whether to watch recursively
            
        Returns:
            WatchCommand configuration
            
        Raises:
            WatcherNotAvailable: If no watcher is available on this platform
        """
        if not os.path.exists(directory):
            raise ValueError(f"Directory does not exist: {directory}")
        
        candidates: list[Callable[[str, bool], Optional[WatchCommand]]] = [
            self._inotify_command,
            self._fswatch_command,
            self._powershell_command,
        ]
        
        for builder in candidates:
            try:
                command = builder(directory, recursive)
                if command:
                    return command
            except Exception:
                continue
        
        raise WatcherNotAvailable(
            f"No watcher available on {self._system}. "
            "Please install: inotifywait (Linux), fswatch (macOS), or PowerShell (Windows)"
        )
    
    def _inotify_command(self, directory: str, recursive: bool) -> Optional[WatchCommand]:
        """Build inotifywait command for Linux."""
        if not shutil.which("inotifywait") or self._system != "Linux":
            return None
        
        args = ["inotifywait", "-m", "-e", "modify,create,delete,move", "--format", "%w%f|%e"]
        if recursive:
            args.insert(2, "-r")
        args.append(directory)
        
        return WatchCommand("inotifywait", args, delimiter='|')
    
    def _fswatch_command(self, directory: str, recursive: bool) -> Optional[WatchCommand]:
        """Build fswatch command for macOS."""
        if not shutil.which("fswatch") or self._system != "Darwin":
            return None
        
        args = ["fswatch", "-0", "--event", "Updated", "--event", "Created"]
        if recursive:
            args.extend(["-r"])
        args.append(directory)
        
        return WatchCommand("fswatch", args, delimiter='\0')
    
    def _powershell_command(self, directory: str, recursive: bool) -> Optional[WatchCommand]:
        """Build PowerShell FileSystemWatcher command for Windows."""
        if not shutil.which("powershell") or self._system != "Windows":
            return None
        
        script = f"""
$watcher = New-Object IO.FileSystemWatcher -ArgumentList '{directory}', '*'
$watcher.IncludeSubdirectories = ${str(recursive).lower()}
$watcher.EnableRaisingEvents = $true

Register-ObjectEvent -InputObject $watcher -EventName Changed -Action {{
    Write-Output "$($Event.SourceEventArgs.FullPath)|Changed"
}} | Out-Null

Register-ObjectEvent -InputObject $watcher -EventName Created -Action {{
    Write-Output "$($Event.SourceEventArgs.FullPath)|Created"
}} | Out-Null

Register-ObjectEvent -InputObject $watcher -EventName Deleted -Action {{
    Write-Output "$($Event.SourceEventArgs.FullPath)|Deleted"
}} | Out-Null

while ($true) {{ Start-Sleep -Seconds 1 }}
"""
        
        return WatchCommand(
            "powershell",
            ["powershell", "-NoLogo", "-NoProfile", "-Command", script]
        )
    
    def normalize_output(self, raw: str, delimiter: str = '\n') -> Optional[WatchEvent]:
        """
        Normalize raw watcher output into a WatchEvent.
        
        Args:
            raw: Raw output line from watcher
            delimiter: Delimiter used to separate path and event kind
            
        Returns:
            WatchEvent if successfully parsed, None otherwise
        """
        if not raw or not raw.strip():
            return None
        
        try:
            # Handle different delimiters
            parts = raw.strip().split(delimiter)
            if len(parts) < 2:
                # Try space-separated as fallback
                parts = raw.strip().split(None, 1)
            
            if len(parts) < 2:
                return None
            
            path = parts[0].strip()
            kind = parts[1].strip()
            
            # Validate path exists or at least looks like a path
            if not path or len(path) < 2:
                return None
            
            # Map various event types to standardized kinds
            kind_map = {
                'modify': 'modified',
                'modified': 'modified',
                'changed': 'modified',
                'updated': 'modified',
                'create': 'created',
                'created': 'created',
                'delete': 'deleted',
                'deleted': 'deleted',
                'moved_to': 'created',
                'moved_from': 'deleted',
            }
            
            normalized_kind = kind_map.get(kind.lower(), kind.lower())
            
            # Apply debouncing
            if not self._debouncer.should_emit(path, normalized_kind):
                return None
            
            return WatchEvent(
                path=path,
                kind=normalized_kind,
                timestamp=time.time()
            )
        
        except (ValueError, IndexError) as e:
            # Defensive: log but don't crash on malformed input
            return None
    
    def watch(self, directory: str, recursive: bool = True) -> Iterator[WatchEvent]:
        """
        Start watching a directory and yield normalized events.
        
        Args:
            directory: Directory to watch
            recursive: Whether to watch recursively
            
        Yields:
            WatchEvent instances as files change
        """
        command = self.build(directory, recursive)
        
        process = subprocess.Popen(
            command.args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        
        try:
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                
                event = self.normalize_output(line.strip(), command.delimiter)
                if event:
                    yield event
        
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def main():
    """CLI entry point for testing the watcher."""
    import sys
    
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <directory>")
        sys.exit(1)
    
    directory = sys.argv[1]
    factory = WatcherFactory(debounce_window=0.5)
    
    try:
        print(f"Watching {directory} for changes...")
        for event in factory.watch(directory):
            print(f"{event.timestamp:.2f} {event.kind:10s} {event.path}")
    
    except KeyboardInterrupt:
        print("\nStopped watching.")
    except WatcherNotAvailable as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
