#!/usr/bin/env bash
set -euo pipefail

GOAL="$*"

echo "SnapshotAgent: Received goal: $GOAL"

# --- Simple Parsing Logic ---
# We expect a goal like: "Capture the '...' window and save to '...'"
# This uses 'sed' to extract the content between the single quotes.
WINDOW_TITLE=$(echo "$GOAL" | sed -n "s/.*Capture the '\(.*\)' window.*/\1/p")
OUTPUT_FILE=$(echo "$GOAL" | sed -n "s/.*save to '\(.*\)'/\1/p")

# --- Validation ---
if [ -z "$WINDOW_TITLE" ] || [ -z "$OUTPUT_FILE" ]; then
  echo "SnapshotAgent Error: Could not parse window title or output file from goal."
  echo "Please provide a goal in the format: \"Capture the 'WINDOW_TITLE' window and save to 'OUTPUT_FILE'\""
  exit 1
fi

echo "SnapshotAgent: Parsed window title: '$WINDOW_TITLE'"
echo "SnapshotAgent: Parsed output file: '$OUTPUT_FILE'"

# --- Command Construction ---
# Construct the full input string for the CLI tool
INPUT_STRING="-f gdigrab -i title='$WINDOW_TITLE'"

# Get the absolute path to the project root (assuming this script is in agents/snapshot-agent)
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"
CLI_PATH="$PROJECT_ROOT/liku_cli.py"

echo "SnapshotAgent: Executing snapshot command..."

# --- Execution ---
python3 "$CLI_PATH" stream snapshot --input "$INPUT_STRING" --output "$OUTPUT_FILE"

if [ $? -eq 0 ]; then
  echo "SnapshotAgent: Task completed successfully. Snapshot saved to $OUTPUT_FILE"
else
  echo "SnapshotAgent: Task failed."
  exit 1
fi
