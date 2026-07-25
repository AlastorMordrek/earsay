#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

OS="$(uname -s)"
HOSTNAME="$(hostname -s 2>/dev/null || echo "your-computer")"

echo "=== EarSay Installer ==="
echo ""

# ── find or install a compatible Python (3.10–3.12) ──────────────────────

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
    echo "No compatible Python (3.10–3.12) found on this system."
    echo "Current: $(python3 --version 2>/dev/null || echo 'no python3')"
    echo ""
    echo "Downloading a portable Python via uv ..."

    # Detect platform for uv binary
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  UV_TARGET="x86_64" ;;
        arm64|aarch64) UV_TARGET="aarch64" ;;
        *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
    esac
    case "$OS" in
        Darwin) UV_TARGET="${UV_TARGET}-apple-darwin" ;;
        Linux)  UV_TARGET="${UV_TARGET}-unknown-linux-gnu" ;;
        *) echo "Unsupported OS: $OS"; exit 1 ;;
    esac

    UV_DIR="$SCRIPT_DIR/.earsay-uv"
    UV_BIN="$UV_DIR/uv"
    mkdir -p "$UV_DIR"

    echo "  Downloading uv ..."
    curl -sL "https://github.com/astral-sh/uv/releases/latest/download/uv-${UV_TARGET}.tar.gz" \
      -o "$UV_DIR/uv.tar.gz"
    tar -xzf "$UV_DIR/uv.tar.gz" -C "$UV_DIR"
    # uv tarball extracts into a subdir named uv-<target>
    EXTRACTED=$(ls "$UV_DIR" | grep -E '^uv-' | head -1)
    if [ -n "$EXTRACTED" ]; then
        mv "$UV_DIR/$EXTRACTED/uv" "$UV_BIN"
        rm -rf "$UV_DIR/$EXTRACTED"
    fi
    rm -f "$UV_DIR/uv.tar.gz"
    chmod +x "$UV_BIN"

    echo "  Installing Python 3.12 via uv ..."
    "$UV_BIN" python install 3.12 2>&1 | sed 's/^/  /'

    PYTHON=$("$UV_BIN" python find 3.12 2>/dev/null)
    if [ -z "$PYTHON" ]; then
        echo "Error: uv failed to install Python 3.12."
        exit 1
    fi

    echo "  Using $($PYTHON --version) at $PYTHON"
    echo ""
fi

echo "Using $($PYTHON --version)"

# ── install earsay ────────────────────────────────────────────────────────

if [ -d ".venv" ]; then
    echo "Removing old virtual environment..."
    rm -rf .venv
fi

echo "Creating virtual environment..."
"$PYTHON" -m venv .venv

INSTALLER=".venv/bin/pip"
echo "Installing earsay and its dependencies..."
echo "  (faster-whisper, sounddevice, FastAPI, and others)"
$INSTALLER install -e . --quiet 2>&1 | tail -1

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
echo "    [N] No — I'll manage it yourself"
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

# ── clean up uv artifacts ─────────────────────────────────────────────────
rm -rf "$SCRIPT_DIR/.earsay-uv" 2>/dev/null

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
