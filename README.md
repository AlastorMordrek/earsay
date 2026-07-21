# EarSay

Continuous voice-to-text terminal utility with HTTP API and streaming subscriptions.

EarSay listens to your microphone, transcribes speech to text using [faster-whisper](https://github.com/SYSTRAN/faster-whisper), and exposes the transcript via a local HTTP API. Subscribe to real-time events as you speak, set checkpoints to split transcripts into chunks, and control the server from any terminal.

## Features

- **Continuous transcription** — microphone → VAD → STT, runs until you stop it
- **HTTP API** — query text, set checkpoints, control pause/resume/stop
- **SSE subscriptions** — real-time text events with character threshold + silence timeout
- **Checkpoints** — split transcripts into chunks, re-define the last one
- **File persistence** — optionally append all text to a file
- **Standalone mode** — stream to stdout without a server

## Installation

### Recommended: pipx

[pipx](https://pipx.pypa.io/) installs earsay in an isolated environment with a compatible Python version automatically:

```bash
pipx install earsay
```

After install, `earsay` is available from any terminal:

```bash
earsay --help
```

### Alternative: pip + venv

If you prefer a manual virtual environment with Python 3.10, 3.11, or 3.12:

```bash
python3 -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
pip install earsay
```

On first run, faster-whisper downloads the model automatically (~75MB for `tiny.en`).

### Requirements

- Python 3.10, 3.11, or 3.12
- Working microphone
- macOS, Linux, or Windows

### Troubleshooting

**"No matching distribution found" or dependency resolution error?**

faster-whisper (the speech recognition engine) depends on compiled packages that do not ship wheels for Python 3.13 or 3.14 yet. Check your Python version:

```bash
python3 --version
```

If it is 3.13 or newer, install a compatible Python version first. The easiest way is [pyenv](https://github.com/pyenv/pyenv):

```bash
pyenv install 3.12
pyenv local 3.12
pipx install earsay
```

Or specify the Python version directly with pipx:

```bash
pipx install --python python3.12 earsay
```

**"Port already in use"?**

Another earsay instance is already running on that port. Stop it first:

```bash
earsay stop
```

Or pick a different port:

```bash
earsay listen --port 3008
```

## Quick Start

```bash
# Server mode — start listening on port 3009
earsay listen --port 3009

# In another terminal:
earsay text                          # get all transcribed text
earsay checkpoint --at 301           # checkpoint at char 301
earsay new-text                      # text since last checkpoint
earsay subscribe --chars 30 --timeout 3000   # real-time events

# Control
earsay pause
earsay resume
earsay stop
```

```bash
# Standalone mode — stream to stdout and file
earsay listen --file transcript.txt
```

## Commands

| Command | Description |
|---------|-------------|
| `earsay listen` | Start transcription server or standalone mode |
| `earsay stop` | Stop the server |
| `earsay pause` | Pause transcription (releases mic) |
| `earsay resume` | Resume transcription |
| `earsay text` | Get all transcribed text |
| `earsay checkpoint --at N` | Set checkpoint at character N |
| `earsay re-checkpoint --at N` | Correct last checkpoint position |
| `earsay new-text` | Get text since last checkpoint |
| `earsay subscribe` | Subscribe to SSE text events |
| `earsay un-subscribe TICKET` | Cancel a subscription |

## HTTP API

The server binds to `127.0.0.1` only. No authentication needed.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/text` | All transcribed text |
| `GET` | `/new-text` | Text since last checkpoint |
| `POST` | `/checkpoint?at=N` | Create checkpoint |
| `POST` | `/re-checkpoint?at=N` | Resize last checkpoint |
| `POST` | `/pause` | Pause transcription |
| `POST` | `/resume` | Resume transcription |
| `POST` | `/stop` | Shutdown server |
| `GET` | `/status` | Server status |
| `POST` | `/subscribe?chars=N&timeout=MS&fullchunk=BOOL` | SSE event stream |
| `DELETE` | `/subscribe/{ticket}` | Cancel subscription |

## Requirements

- Python 3.10+
- Working microphone
- macOS, Linux, or Windows

## License

MIT
