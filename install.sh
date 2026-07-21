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
    echo "Creating virtual environment (a sandboxed Python workspace)..."
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

echo "What happens next?"
echo ""
echo "  EarSay is now ready on your computer ($HOSTNAME), but your terminal"
echo "  doesn't know where to find the 'earsay' command yet."
echo ""
echo "  Think of it like installing an app that didn't get added to your"
echo "  dock or start menu — you can still open it, you just need to know"
echo "  where it lives."
echo ""
echo "Choose how you want to access earsay from the terminal:"
echo ""
echo "  ┌─────────────────────────────────────────────────────────────"
echo "  │ [N] None — always use the full path (default, safest)"
echo "  │"
echo "  │     Nothing is changed on your system. You run earsay by"
echo "  │     typing its full location each time. This means you"
echo "  │     always know exactly what you're running."
echo "  │"
echo "  │     Example:"
echo "  │       $BIN_PATH --help"
echo "  │       $BIN_PATH listen --port 3009"
echo "  │"
echo "  │     Tip: if you 'cd' into this directory first, you can"
echo "  │          use a shorter path: .venv/bin/earsay --help"
echo "  ├─────────────────────────────────────────────────────────────"
echo "  │ [P] Add to PATH — make earsay available everywhere"
echo "  │"
echo "  │     The install location is added to your shell's PATH"
echo "  │     (a list of folders your terminal searches for commands)."
echo "  │     After this, you can just type 'earsay' from anywhere."
echo "  │"
echo "  │     This session: works immediately."
echo "  │     Future sessions: works automatically."
echo "  │"
echo "  │     After choosing this, you can run:"
echo "  │       earsay --help"
echo "  │       earsay listen --port 3009"
echo "  ├─────────────────────────────────────────────────────────────"
echo "  │ [B] Install binary — shortcut in ~/.local/bin"
echo "  │"
echo "  │     Creates a link to earsay in ~/.local/bin, a standard"
echo "  │     folder for user-installed programs. If this folder is"
echo "  │     already on your PATH, 'earsay' works immediately."
echo "  │"
echo "  │     After choosing this, you can run:"
echo "  │       earsay --help"
echo "  │       earsay listen --port 3009"
echo "  │"
echo "  │     (if ~/.local/bin is on your PATH)"
echo "  └─────────────────────────────────────────────────────────────"
echo ""

read -r -p "Which option? [N/p/b]: " choice

case "${choice:-N}" in
    [Pp])
        VENV_BIN="$SCRIPT_DIR/.venv/bin"
        EXPORT_LINE="export PATH=\"$VENV_BIN:\$PATH\""

        case "$(basename "${SHELL:-/bin/bash}")" in
            zsh)
                PROFILE="${ZDOTDIR:-$HOME}/.zshrc"
                ;;
            bash)
                if [ "$OS" = "Darwin" ]; then
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
            echo "Already in $PROFILE — skipping."
        else
            echo "" >> "$PROFILE"
            echo "# Added by earsay installer ($(date))" >> "$PROFILE"
            echo "$EXPORT_LINE" >> "$PROFILE"
            echo "Added to $PROFILE"
        fi

        export PATH="$VENV_BIN:$PATH"
        echo ""
        echo "Done. 'earsay' is now ready to use:"
        echo ""
        echo "  earsay --help"
        echo "  earsay listen --port 3009"
        echo ""
        echo "Try it now! Your terminal on $HOSTNAME can find it."
        ;;

    [Bb])
        BIN_DIR="$HOME/.local/bin"
        mkdir -p "$BIN_DIR"
        ln -sf "$BIN_PATH" "$BIN_DIR/earsay"

        if [ "$OS" = "Darwin" ]; then
            echo "Created: /Users/$USER/.local/bin/earsay -> $BIN_PATH"
        else
            echo "Created: $BIN_DIR/earsay -> $BIN_PATH"
        fi

        if [[ ":$PATH:" == *":$BIN_DIR:"* ]]; then
            echo ""
            echo "'earsay' is ready now:"
            echo "  earsay --help"
            echo "  earsay listen --port 3009"
        else
            echo ""
            echo "~/.local/bin is not on your PATH yet."
            echo "To fix this, add this line to your shell profile:"
            echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
            echo ""
            echo "Until then, use the full path:"
            echo "  $BIN_PATH --help"
            echo "  $BIN_PATH listen --port 3009"
        fi
        ;;

    *)
        echo "Using default: full path only (no system changes)."
        echo ""
        echo "To run earsay, always use its full location:"
        echo ""
        echo "  $BIN_PATH --help"
        echo "  $BIN_PATH listen --port 3009"
        echo ""
        echo "Or navigate to this folder and use a shorter path:"
        echo "  cd $(pwd)"
        echo "  .venv/bin/earsay --help"
        echo "  .venv/bin/earsay listen --port 3009"
        ;;
esac

echo ""
echo "--------------------------------------------------"
echo "  Quick reference — what you can do with earsay:"
echo ""
echo "    Start transcribing:"
echo "      $( [ "${choice:-N}" = "p" ] || [ "${choice:-N}" = "P" ] || [ "${choice:-N}" = "b" ] || [ "${choice:-N}" = "B" ] && echo "earsay" || echo ".venv/bin/earsay") listen --port 3009"
echo ""
echo "    Get transcribed text:"
echo "      $( [ "${choice:-N}" = "p" ] || [ "${choice:-N}" = "P" ] || [ "${choice:-N}" = "b" ] || [ "${choice:-N}" = "B" ] && echo "earsay" || echo ".venv/bin/earsay") text"
echo ""
echo "    See all commands:"
echo "      $( [ "${choice:-N}" = "p" ] || [ "${choice:-N}" = "P" ] || [ "${choice:-N}" = "b" ] || [ "${choice:-N}" = "B" ] && echo "earsay" || echo ".venv/bin/earsay") --help"
echo ""
echo "--------------------------------------------------"
echo "To uninstall:"
echo "  ./uninstall.sh"
echo "--------------------------------------------------"
