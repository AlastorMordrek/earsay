#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== EarSay Uninstaller ==="
echo ""

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

if [ -L ~/.local/bin/earsay ]; then
    echo "Removing symlink (~/.local/bin/earsay)..."
    rm -f ~/.local/bin/earsay
    REMOVED=1
fi

VENV_BIN="$SCRIPT_DIR/.venv/bin"
EXPORT_LINE="export PATH=\"$VENV_BIN:\$PATH\""

for profile in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile"; do
    if [ -f "$profile" ] && grep -qF "$EXPORT_LINE" "$profile" 2>/dev/null; then
        echo "Removing PATH entry from $profile..."
        if [[ "$(uname -s)" == "Darwin" ]]; then
            sed -i '' "/# Added by earsay installer/d" "$profile"
            sed -i '' "\|$EXPORT_LINE|d" "$profile"
        else
            sed -i "/# Added by earsay installer/d" "$profile"
            sed -i "\|$EXPORT_LINE|d" "$profile"
        fi
        REMOVED=1
    fi
done

if [ "$REMOVED" -eq 0 ]; then
    echo "Nothing to uninstall. EarSay is not installed here."
else
    echo ""
    echo "EarSay has been removed."
    echo ""
    echo "Note: if you added earsay to your PATH in this terminal session,"
    echo "the 'earsay' command will stop working when you open a new terminal."
fi
