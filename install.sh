#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

OS="$(uname -s)"
HOSTNAME="$(hostname -s 2>/dev/null || echo "your-computer")"

echo "=== EarSay Installer ==="
echo ""

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

echo "Detected $OS. Using $PYTHON ($($PYTHON --version))"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv .venv
fi

echo "Installing earsay and its dependencies..."
echo "  (faster-whisper, sounddevice, FastAPI, and others)"
.venv/bin/pip install -e . --quiet 2>&1 | tail -1

BIN_PATH="$SCRIPT_DIR/.venv/bin/earsay"

echo ""
echo "--------------------------------------------------"
echo "  EarSay is installed."
echo "  Binary: $BIN_PATH"
echo "--------------------------------------------------"
echo ""

if [ "$OS" = "Darwin" ]; then
    echo "macOS note: the first time earsay accesses your microphone,"
    echo "macOS will show a permission dialog. You must allow it."
    echo ""
fi

echo "  EarSay is ready on your computer ($HOSTNAME), but your terminal"
echo "  doesn't know where to find the 'earsay' command yet."
echo ""
echo "  Would you like to install it globally? This creates a symlink"
echo "  in ~/.local/bin and ensures that folder is on your PATH so"
echo "  'earsay' works from any directory."
echo ""
echo "    [Y] Yes — install globally (recommended, default)"
echo "        Result: earsay --help     (works everywhere)"
echo ""
echo "    [N] No — I'll manage it myself"
echo "        Result: $BIN_PATH --help  (full path required)"
echo ""

read -r -p "Your choice [Y/n]: " raw

choice="$(echo "${raw:-y}" | tr '[:upper:]' '[:lower:]')"

case "$choice" in
    y|yes)
        BIN_DIR="$HOME/.local/bin"
        mkdir -p "$BIN_DIR"
        ln -sf "$BIN_PATH" "$BIN_DIR/earsay"

        echo ""
        echo "Created: $BIN_DIR/earsay"

        if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
            SHELL_NAME="$(basename "${SHELL:-/bin/bash}")"
            EXPORT_LINE="export PATH=\"\$HOME/.local/bin:\$PATH\""

            case "$SHELL_NAME" in
                zsh)  PROFILE="${ZDOTDIR:-$HOME}/.zshrc" ;;
                bash)
                    if [ "$OS" = "Darwin" ]; then
                        PROFILE="$HOME/.bash_profile"
                        [ -f "$PROFILE" ] || PROFILE="$HOME/.bashrc"
                    else
                        PROFILE="$HOME/.bashrc"
                        [ -f "$PROFILE" ] || PROFILE="$HOME/.bash_profile"
                    fi
                    ;;
                *)    PROFILE="$HOME/.profile" ;;
            esac

            if grep -qF "$EXPORT_LINE" "$PROFILE" 2>/dev/null; then
                echo "~/.local/bin already in $PROFILE — skipping."
            else
                echo "" >> "$PROFILE"
                echo "# Added by earsay installer ($(date))" >> "$PROFILE"
                echo "$EXPORT_LINE" >> "$PROFILE"
                echo "Added ~/.local/bin to $PROFILE"
            fi

            export PATH="$BIN_DIR:$PATH"
        fi

        echo ""
        echo "'earsay' is now available on $HOSTNAME:"
        echo ""
        echo "  earsay --help"
        echo "  earsay listen"
        echo "  earsay listen --port 3009"
        CMD="earsay"
        ;;

    *)
        echo ""
        echo "Skipping global install. Use the full path to run earsay:"
        echo ""
        echo "  $BIN_PATH --help"
        echo "  $BIN_PATH listen"
        echo ""
        echo "  Or navigate here and use a shorter path:"
        echo "  cd $(pwd)"
        echo "  .venv/bin/earsay --help"
        CMD=".venv/bin/earsay"
        ;;
esac

echo ""
echo "--------------------------------------------------"
echo "  Quick reference:"
echo ""
echo "    $CMD --help"
echo "    $CMD listen               # transcribe to stdout"
echo "    $CMD listen --port 3009   # start HTTP API server"
echo "    $CMD warmup               # pre-load all dependencies"
echo "--------------------------------------------------"
echo ""
echo "To uninstall:"
echo "  ./uninstall.sh"
