# EarSay

Continuous voice-to-text for your terminal. Speak into your microphone and EarSay transcribes everything in real time, exposing the text through an HTTP API with streaming events.

## What is EarSay?

EarSay listens to your microphone, converts speech to text using [faster-whisper](https://github.com/SYSTRAN/faster-whisper), and makes the text available as:
- **HTTP API** — other programs can read the text over HTTP
- **Streaming events** — subscribe via SSE and get text in real time
- **stdout** — transcribed text appears in your terminal

## Installation

Requires **python3** and **curl** on your system. The installer handles everything else — if your Python version is too new, it downloads a portable one via [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/AlastorMordrek/earsay.git
cd earsay
./install.sh
```

Answer **Y** when asked about global install, then open a new terminal:

```bash
earsay listen --port 3009
```

## Quick Start

```bash
earsay listen                    # transcribe to stdout
earsay listen --port 3009        # start HTTP API server
earsay listen --model large      # use a larger whisper model (better accuracy, slower)
earsay warmup                    # pre-load dependencies so listen starts instantly
```

### From another terminal:

```bash
earsay text                      # see everything said so far
earsay checkpoint --at 301       # mark a position as "read"
earsay re-checkpoint --at 150    # correct the last checkpoint to a new position
earsay new-text                  # get text since last checkpoint
earsay pause                     # release microphone
earsay resume                    # start listening again
earsay subscribe --chars 30 --timeout 3000 --fullchunk
earsay un-subscribe <ticket>     # cancel a subscription
earsay stop                      # shut down
```

### OpenCode Integration

[opencode-earsay](https://github.com/AlastorMordrek/opencode-earsay) wires EarSay into your OpenCode agent. See that repo's README for install instructions. After setup, just speak — the LLM analyzes speech autonomously.

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

## Commands

| Command | What it does |
|---------|-------------|
| `earsay listen` | Start transcribing (`--port` for HTTP API, `--file` for file output, `--model` for whisper model) |
| `earsay stop` | Shut down the server |
| `earsay pause` | Release the microphone (server stays running) |
| `earsay resume` | Start listening again |
| `earsay text` | Print all transcribed text |
| `earsay checkpoint --at N` | Mark a position as read |
| `earsay re-checkpoint --at N` | Correct the last checkpoint to a new position |
| `earsay new-text` | Get text since last checkpoint |
| `earsay subscribe --chars N --timeout MS --fullchunk` | Open a live SSE stream |
| `earsay un-subscribe TICKET` | Cancel a subscription by ticket ID |
| `earsay warmup` | Pre-load dependencies so the first `listen` starts without delay |

## HTTP API

When running in server mode (`--port`), EarSay exposes these endpoints on `127.0.0.1`:

| Method | Path | What it does |
|--------|------|-------------|
| `GET` | `/text` | All transcribed text |
| `GET` | `/new-text` | Text since last checkpoint |
| `POST` | `/checkpoint?at=N` | Create a checkpoint |
| `POST` | `/re-checkpoint?at=N` | Correct the last checkpoint to a new position |
| `POST` | `/pause` | Release microphone |
| `POST` | `/resume` | Reopen microphone |
| `POST` | `/stop` | Shut down (kills the server process) |
| `GET` | `/status` | Server status and statistics |
| `POST` | `/subscribe?chars=N&timeout=MS&fullchunk=BOOL` | SSE event stream |
| `DELETE` | `/subscribe/{ticket}` | Cancel a subscription |

## Uninstall

```bash
cd earsay
./uninstall.sh
```

The uninstaller stops the server, removes the virtual environment and uv download, deletes `~/.earsay/` and the `~/.local/bin/earsay` symlink, and cleans up profile PATH additions. See also the [opencode-earsay plugin](https://github.com/AlastorMordrek/opencode-earsay) if earsay was installed by it.

## Requirements

- **Python 3.10, 3.11, or 3.12** — the installer downloads one if not found
- **Working microphone** — built-in, USB, or Bluetooth
- **macOS, Linux, or Windows (WSL)**

On macOS, the first microphone access triggers a permission dialog. Click Allow.

## License

MIT
