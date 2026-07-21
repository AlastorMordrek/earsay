# EarSay

Continuous voice-to-text for your terminal. Speak into your microphone and EarSay transcribes everything in real time, exposing the text through an HTTP API with streaming events.

## What is EarSay?

EarSay is a voice dictation tool that runs in your terminal. It listens to your microphone, converts speech to text using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (a fast, open-source speech recognition engine), and makes the transcribed text available in several ways:

- **As a server** — other programs can read the text over HTTP
- **As a file** — append every word to a text file
- **As streaming events** — subscribe and get text in real time as you speak

EarSay is built for developers who want to add voice input to their tools, especially AI coding agents like OpenCode.

## How it works

```
Your voice → Microphone → EarSay (faster-whisper) → Transcribed text
                                                         │
                                    ┌────────────────────┼────────────────────┐
                                    │                    │                     │
                              HTTP API              Append to file         Stream to stdout
                           (other programs        (optional, with          (standalone mode,
                            can read it)            --file flag)           no --port)
```

When you run `earsay listen --port 3009`, EarSay starts a local web server. Other programs (or you, from another terminal) can query it for the transcribed text. No data leaves your computer — the server only listens on `127.0.0.1` (localhost).

## Features

- **Continuous transcription** — listens until you stop it. No push-to-talk, no time limits.
- **HTTP API** — query text, set checkpoints, control pause/resume/stop from any program
- **Real-time events** — subscribe via SSE (Server-Sent Events) and get text as it arrives
- **Checkpoints** — split transcripts into chunks (like bookmarks in a document)
- **File persistence** — optionally save everything to a file
- **Standalone mode** — stream directly to stdout, no server needed

## Installation

### Option 1: pipx (recommended, one command)

[pipx](https://pipx.pypa.io/) installs EarSay in an isolated environment. It handles Python version detection automatically:

```bash
pipx install git+https://github.com/AlastorMordrek/earsay.git
```

After install, `earsay` is available from any terminal:

```bash
earsay --help
```

### Option 2: clone and run the install script

```bash
git clone https://github.com/AlastorMordrek/earsay.git
cd earsay
./install.sh
```

The install script will:
1. Find a compatible Python version (3.10, 3.11, or 3.12) on your system
2. Create a virtual environment (a sandboxed workspace)
3. Install EarSay and all its dependencies
4. Offer to add `earsay` to your PATH so you can run it from anywhere

On first run, faster-whisper downloads the speech recognition model automatically (~75MB for `tiny.en`).

### Requirements

- **Python 3.10, 3.11, or 3.12** — newer versions (3.13+) are not yet supported by the speech recognition engine
- **Working microphone** — built-in, USB, or Bluetooth
- **macOS, Linux, or Windows**

### Troubleshooting

**"No matching distribution found" or dependency resolution error?**

This means your Python version is too new. faster-whisper depends on compiled packages that don't have builds for Python 3.13 or 3.14 yet.

Check your version:
```bash
python3 --version
```

If it's 3.13 or newer, install a compatible version with [pyenv](https://github.com/pyenv/pyenv):
```bash
pyenv install 3.12
pyenv local 3.12
pipx install git+https://github.com/AlastorMordrek/earsay.git
```

Or tell pipx which Python to use:
```bash
pipx install --python python3.12 git+https://github.com/AlastorMordrek/earsay.git
```

**"Port already in use"?**

Another instance of EarSay is already running on that port. Stop it first:
```bash
earsay stop
```

Or use a different port:
```bash
earsay listen --port 3008
```

**"Permission denied" on macOS?**

The first time EarSay accesses your microphone, macOS will show a permission dialog. You must click "Allow." If you accidentally denied it, go to System Settings → Privacy & Security → Microphone and enable it for your terminal app.

## Quick Start

### Server mode (API + file)

Start EarSay as a background server. It will listen on port 3009 and append all text to a file:

```bash
earsay listen --port 3009 --file ~/transcript.txt
```

In another terminal, interact with it:

```bash
# See everything that's been said so far
earsay text

# Set a checkpoint at character 301 (mark it as "already read")
earsay checkpoint --at 301

# Get only the new text since the last checkpoint
earsay new-text

# Subscribe to real-time events — text arrives as you speak
earsay subscribe --chars 30 --timeout 3000

# Control the server
earsay pause       # release the microphone temporarily
earsay resume      # start listening again
earsay stop        # shut down completely
```

### Standalone mode (terminal only)

Stream transcription directly to your terminal. No server, no API. Great for quick dictation:

```bash
earsay listen --file ~/notes.txt
```

Text appears in the terminal as you speak and is also saved to `~/notes.txt`. Press Ctrl-C to stop.

## Commands

| Command | What it does | Example |
|---------|-------------|---------|
| `earsay listen` | Start transcribing. Add `--port` for API access, `--file` to save to disk. | `earsay listen --port 3009 --file ~/transcript.txt` |
| `earsay stop` | Shut down the server. | `earsay stop` |
| `earsay pause` | Release the microphone (server stays running). | `earsay pause` |
| `earsay resume` | Start listening again after a pause. | `earsay resume` |
| `earsay text` | Print all transcribed text since the server started. | `earsay text` |
| `earsay checkpoint` | Mark a position in the text as "read." Future `new-text` calls only return text after this point. | `earsay checkpoint --at 301` |
| `earsay re-checkpoint` | Change the position of the last checkpoint (make it larger or smaller). | `earsay re-checkpoint --at 295` |
| `earsay new-text` | Print text since the last checkpoint, plus its potential index. | `earsay new-text` |
| `earsay subscribe` | Open a live stream of text events. Fires when N new characters arrive or after a silence timeout. | `earsay subscribe --chars 30 --timeout 3000` |
| `earsay un-subscribe` | Cancel a subscription by its ticket ID. | `earsay un-subscribe a1b2c3d4-...` |

## HTTP API

When running in server mode (`--port`), EarSay exposes these endpoints. The server only listens on `127.0.0.1` (localhost) — no external access, no authentication needed.

| Method | Path | What it does |
|--------|------|-------------|
| `GET` | `/text` | Returns all transcribed text as JSON |
| `GET` | `/new-text` | Returns text since last checkpoint, with its potential index |
| `POST` | `/checkpoint?at=N` | Creates a checkpoint at character position N |
| `POST` | `/re-checkpoint?at=N` | Resizes the last checkpoint to position N |
| `POST` | `/pause` | Releases the microphone |
| `POST` | `/resume` | Reopens the microphone |
| `POST` | `/stop` | Shuts down the server |
| `GET` | `/status` | Returns server status and statistics |
| `POST` | `/subscribe?chars=N&timeout=MS&fullchunk=BOOL` | Opens an SSE event stream |
| `DELETE` | `/subscribe/{ticket}` | Cancels a subscription |

## License

MIT
