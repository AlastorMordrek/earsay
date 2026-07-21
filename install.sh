#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== EarSay Installer ==="

PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        major=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null) || continue
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null) || continue
        if [ "$major" -eq 3 ] && [ "$minor" -ge 10 ] && [ "$minor" -le 12 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.10, 3.11, or 3.12 required but none found."
    echo ""
    echo "Install a compatible version:"
    echo "  pyenv install 3.12 && pyenv local 3.12"
    echo "  then re-run: ./install.sh"
    exit 1
fi

echo "Using $PYTHON ($($PYTHON --version))"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv .venv
fi

echo "Installing earsay and dependencies..."
.venv/bin/pip install -e . --quiet 2>&1 | tail -1

BIN_PATH="$SCRIPT_DIR/.venv/bin/earsay"

echo ""
echo "Installation complete."
echo ""
echo "Binary location: $BIN_PATH"
echo ""
echo "You can always run earsay with its full path:"
echo "  $BIN_PATH --help"
echo "  $BIN_PATH listen --port 3009"
echo ""
echo "For easier access, choose an option:"
echo ""
echo "  [N] None — always use the full path above (default)"
echo "      No changes are made to your system. You must type the"
echo "      full path each time, or cd to this directory first."
echo ""
echo "  [P] Add to PATH — adds .venv/bin to your shell profile"
echo "      'earsay' will be available from any directory after"
echo "      opening a new terminal. Also activates immediately"
echo "      in this session."
echo ""
echo "  [B] Install binary — creates a symlink in ~/.local/bin"
echo "      'earsay' will be available immediately if ~/.local/bin"
echo "      is already on your PATH."
echo ""

read -r -p "Which option? [N/p/b]: " choice

case "${choice:-N}" in
    [Pp])
        SHELL_NAME="$(basename "${SHELL:-/bin/bash}")"
        VENV_BIN="$SCRIPT_DIR/.venv/bin"
        EXPORT_LINE="export PATH=\"$VENV_BIN:\$PATH\""

        case "$SHELL_NAME" in
            zsh)
                PROFILE="${ZDOTDIR:-$HOME}/.zshrc"
                ;;
            bash)
                if [[ "$(uname -s)" == "Darwin" ]]; then
                    PROFILE="$HOME/.bash_profile"
                    [ -f "$PROFILE" ] || PROFILE="$HOME/.bashrc"
                else
                    PROFILE="$HOME/.bashrc"
                    [ -f "$PROFILE" ] || PROFILE="$HOME/.bash_profile"
                fi
                ;;
            *)
                PROFILE="$HOME/.profile"
                ;;
        esac

        if grep -qF "$EXPORT_LINE" "$PROFILE" 2>/dev/null; then
            echo "PATH entry already exists in $PROFILE. Skipping."
        else
            echo "" >> "$PROFILE"
            echo "# Added by earsay installer" >> "$PROFILE"
            echo "$EXPORT_LINE" >> "$PROFILE"
            echo "Added PATH entry to $PROFILE"
        fi

        export PATH="$VENV_BIN:$PATH"
        echo ""
        echo "Done. 'earsay' is now available in this session."
        echo "New terminals will pick it up automatically."
        echo ""
        echo "  earsay --help"
        ;;

    [Bb])
        BIN_DIR="$HOME/.local/bin"
        mkdir -p "$BIN_DIR"
        ln -sf "$BIN_PATH" "$BIN_DIR/earsay"
        echo ""
        echo "Symlink created: $BIN_DIR/earsay -> $BIN_PATH"

        if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
            echo ""
            echo "Note: ~/.local/bin is not on your PATH."
            echo "Add it manually to your shell profile:"
            echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        else
            echo ""
            echo "'earsay' should be available now:"
            echo "  earsay --help"
        fi
        ;;

    *)
        echo ""
        echo "Skipping PATH setup. Use the full path to run earsay:"
        echo "  $BIN_PATH --help"
        echo "  $BIN_PATH listen --port 3009"
        ;;
esac

echo ""
echo "To uninstall: rm -rf $SCRIPT_DIR/.venv"
