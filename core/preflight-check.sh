#!/usr/bin/env bash
# Pre-flight environment validation with version checks
# Outputs JSON for machine-readable results

set -euo pipefail

# Minimum required versions
MIN_TMUX_VERSION="3.0"
MIN_SQLITE_VERSION="3.30.0"

# Detect platform
OS_NAME="$(uname -s 2>/dev/null || echo unknown)"
case "${OS_NAME}" in
    Linux)
        PLATFORM="linux"
        WATCH_PROBES=("inotifywait")
        WATCH_PACKAGES=("inotify-tools")
        ;;
    Darwin)
        PLATFORM="macos"
        WATCH_PROBES=("fswatch")
        WATCH_PACKAGES=("fswatch")
        ;;
    MINGW*|MSYS*|CYGWIN*)
        PLATFORM="windows"
        WATCH_PROBES=("powershell.exe")
        WATCH_PACKAGES=("PowerShell")
        ;;
    *)
        PLATFORM="unknown"
        WATCH_PROBES=()
        WATCH_PACKAGES=()
        ;;
esac

# Check binary presence and version
check_binary() {
    local binary="$1"
    local min_version="${2:-}"
    
    if ! command -v "$binary" >/dev/null 2>&1; then
        echo "missing"
        return 1
    fi
    
    if [ -z "$min_version" ]; then
        echo "ok"
        return 0
    fi
    
    # Get version based on binary
    local version=""
    case "$binary" in
        tmux)
            version=$(tmux -V 2>/dev/null | grep -oP '\d+\.\d+' | head -1 || echo "0.0")
            ;;
        sqlite3)
            version=$(sqlite3 --version 2>/dev/null | grep -oP '^\d+\.\d+\.\d+' | head -1 || echo "0.0.0")
            ;;
        python3)
            version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1 || echo "0.0")
            ;;
        *)
            echo "ok"
            return 0
            ;;
    esac
    
    # Version comparison (simplified - works for major.minor)
    if [ -n "$version" ]; then
        if printf '%s\n%s\n' "$min_version" "$version" | sort -V -C; then
            echo "ok:$version"
            return 0
        else
            echo "outdated:$version"
            return 1
        fi
    fi
    
    echo "version_unknown"
    return 1
}

# Build results array
declare -a missing_binaries=()
declare -a outdated_binaries=()
declare -a present_binaries=()

# Check core dependencies
for binary in tmux sqlite3 python3 bash; do
    case "$binary" in
        tmux)
            result=$(check_binary "$binary" "$MIN_TMUX_VERSION")
            ;;
        sqlite3)
            result=$(check_binary "$binary" "$MIN_SQLITE_VERSION")
            ;;
        *)
            result=$(check_binary "$binary")
            ;;
    esac
    
    status=$?
    if [ $status -ne 0 ]; then
        if [[ "$result" == outdated:* ]]; then
            outdated_binaries+=("$binary:${result#outdated:}")
        else
            missing_binaries+=("$binary")
        fi
    else
        present_binaries+=("$binary:${result#ok:}")
    fi
done

# Check platform-specific watchers
for probe in "${WATCH_PROBES[@]}"; do
    result=$(check_binary "$probe")
    status=$?
    if [ $status -ne 0 ]; then
        missing_binaries+=("$probe")
    else
        present_binaries+=("$probe")
    fi
done

# Determine overall status
if [ "${#missing_binaries[@]}" -gt 0 ] || [ "${#outdated_binaries[@]}" -gt 0 ]; then
    STATUS="fail"
    EXIT_CODE=2
else
    STATUS="ok"
    EXIT_CODE=0
fi

# Build JSON output
python3 - "$STATUS" "$PLATFORM" "${present_binaries[@]}" "${missing_binaries[@]}" "${outdated_binaries[@]}" "${WATCH_PACKAGES[@]}" <<'PY'
import json, sys

status = sys.argv[1]
platform = sys.argv[2]

# Parse arrays - they're separated by special marker in argv
present_str = []
missing_str = []
outdated_str = []
packages_str = []

idx = 3
while idx < len(sys.argv):
    arg = sys.argv[idx]
    if arg.startswith('MISSING:'):
        idx += 1
        break
    present_str.append(arg)
    idx += 1

while idx < len(sys.argv):
    arg = sys.argv[idx]
    if arg.startswith('OUTDATED:'):
        idx += 1
        break
    missing_str.append(arg)
    idx += 1

while idx < len(sys.argv):
    arg = sys.argv[idx]
    if arg.startswith('PACKAGES:'):
        idx += 1
        break
    outdated_str.append(arg)
    idx += 1

while idx < len(sys.argv):
    packages_str.append(sys.argv[idx])
    idx += 1

result = {
    "status": status,
    "platform": platform,
    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")",
    "checks": {
        "present": present_str,
        "missing": missing_str,
        "outdated": outdated_str
    },
    "recommendations": []
}

if missing_str:
    result["recommendations"].append({
        "type": "install_missing",
        "message": f"Install missing dependencies: {', '.join(missing_str)}",
        "packages": packages_str
    })

if outdated_str:
    result["recommendations"].append({
        "type": "upgrade_outdated",
        "message": f"Upgrade outdated dependencies: {', '.join(outdated_str)}"
    })

print(json.dumps(result, indent=2))
PY

# Simplified output without complex parsing
cat <<JSON
{
  "status": "$STATUS",
  "platform": "$PLATFORM",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")",
  "checks": {
    "present": [$(printf '"%s",' "${present_binaries[@]}" | sed 's/,$//')],
    "missing": [$(printf '"%s",' "${missing_binaries[@]}" | sed 's/,$//')],
    "outdated": [$(printf '"%s",' "${outdated_binaries[@]}" | sed 's/,$//')]
  },
  "recommendations": [
    $(if [ "${#missing_binaries[@]}" -gt 0 ]; then
      echo '{"type":"install_missing","message":"Install missing dependencies: '"$(printf '%s, ' "${missing_binaries[@]}" | sed 's/, $//')"'","packages":['"$(printf '"%s",' "${WATCH_PACKAGES[@]}" | sed 's/,$//')"']}'
    fi)
    $(if [ "${#outdated_binaries[@]}" -gt 0 ]; then
      [ "${#missing_binaries[@]}" -gt 0 ] && echo ','
      echo '{"type":"upgrade_outdated","message":"Upgrade outdated dependencies: '"$(printf '%s, ' "${outdated_binaries[@]}" | sed 's/, $//')"'"}'
    fi)
  ]
}
JSON

exit $EXIT_CODE
