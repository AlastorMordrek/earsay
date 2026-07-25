#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== EarSay Uninstaller ==="
echo ""

STOPPED=0

if [ -f ~/.earsay/pid ]; then
    PORT=$(python3 -c "import json; print(json.load(open('$HOME/.earsay/pid')).get('port',0))" 2>/dev/null || echo 0)
    PID=$(python3 -c "import json; print(json.load(open('$HOME/.earsay/pid')).get('pid',0))" 2>/dev/null || echo 0)

    if [ "$PID" -gt 0 ] && kill -0 "$PID" 2>/dev/null; then
        echo "EarSay is running (pid $PID). Stopping..."

        if [ "$PORT" -gt 0 ]; then
            curl -s -X POST "http://127.0.0.1:$PORT/stop" 2>/dev/null || true
            sleep 1
        fi

        if kill -0 "$PID" 2>/dev/null; then
            echo "Graceful stop failed. Force-killing..."
            kill "$PID" 2>/dev/null || true
            sleep 1
            kill -9 "$PID" 2>/dev/null || true
        fi

        STOPPED=1
        echo "Stopped."
    fi
fi

REMOVED=0

if [ -d ".venv" ]; then
    echo "Removing virtual environment..."
    rm -rf .venv
    REMOVED=1
fi

if [ -d ~/.earsay ]; then
    echo "Removing pid directory (~/.earsay)..."
    rm -rf ~/.earsay
    REMOVED=1
fi

if [ -d "$SCRIPT_DIR/.earsay-uv" ]; then
    echo "Removing uv download directory..."
    rm -rf "$SCRIPT_DIR/.earsay-uv"
    REMOVED=1
fi

if [ -L ~/.local/bin/earsay ]; then
    echo "Removing symlink (~/.local/bin/earsay)..."
    rm -f ~/.local/bin/earsay
    REMOVED=1
fi

for profile in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile"; do
    if [ -f "$profile" ]; then
        if grep -q "# Added by earsay installer" "$profile" 2>/dev/null; then
            echo "Removing installer entries from $profile..."
            if [[ "$(uname -s)" == "Darwin" ]]; then
                sed -i '' '/# Added by earsay installer/d' "$profile"
                sed -i '' '/^$/N;/^\n$/d' "$profile"
            else
                sed -i '/# Added by earsay installer/d' "$profile"
                sed -i '/^$/N;/^\n$/d' "$profile"
            fi
            REMOVED=1
        fi
    fi
done

if [ "$STOPPED" -eq 0 ] && [ "$REMOVED" -eq 0 ]; then
    echo "Nothing to uninstall. EarSay is not installed here."
else
    echo ""
    echo "EarSay has been removed."
    echo ""
    echo "Note: the 'earsay' command will stop working when you open"
    echo "a new terminal. If the installer downloaded a portable"
    echo "Python 3.12 via uv, the files are at:"
    echo "  ~/.local/share/uv/python/cpython-3.12*"
    echo "Remove them if no other tool on your system uses uv:"
fi
