# EarSay

Always-on speech-to-text for your terminal. Speaks to your microphone, converts
speech to text via faster-whisper, and serves the transcription through an HTTP
API with live streaming events.

---

## Quick Start

```bash
git clone https://github.com/AlastorMordrek/earsay.git
cd earsay
./install.sh
```

Answer **Y** when asked about global install. Open a new terminal:

```bash
earsay listen --port 3009
```

Speak into your microphone. Open another terminal:

```bash
earsay text           # see everything said so far
earsay stop           # shut down
```

---

## Prerequisites

- **python3** and **curl** on your system
- Working microphone (built-in, USB, or Bluetooth)

On macOS, the first microphone access triggers a permission dialog. Click Allow.

If your system Python is newer than 3.12, the installer downloads a portable
Python 3.12 via uv automatically.

---

## Installation

```bash
git clone https://github.com/AlastorMordrek/earsay.git
cd earsay
./install.sh
```

The installer:
1. Finds or downloads a compatible Python (3.10–3.12)
2. Creates a virtual environment
3. Installs earsay and its dependencies (faster-whisper, sounddevice, FastAPI)
4. Optionally creates a `~/.local/bin/earsay` symlink and adds it to your PATH

After installing, open a **new terminal** so the PATH change takes effect.

---

## Usage

### Server mode (HTTP API + streaming)

```bash
earsay listen --port 3009
```

Keeps running in the foreground. Speak — the server transcribes and exposes
the text through the HTTP API (see below). Stop with `Ctrl-C` or `earsay stop`.

### Standalone mode (stdout)

```bash
earsay listen
```

Transcribes directly to the terminal. No HTTP server. Stop with `Ctrl-C`.

### File output

```bash
earsay listen --file transcript.txt
```

Appends each transcribed chunk to a file. Combine with `--port` for both.

### Commands (all require a running server)

| Command | What it does |
|---------|-------------|
| `earsay stop` | Shut down the server and release the microphone |
| `earsay pause` | Release microphone (server stays running) |
| `earsay resume` | Start listening again |
| `earsay text` | Print all transcribed text since server start |
| `earsay checkpoint --at N` | Mark character N as read |
| `earsay re-checkpoint --at N` | Correct the last checkpoint to a new position |
| `earsay new-text` | Get text since the last checkpoint |
| `earsay subscribe --chars N --timeout MS --fullchunk` | Open a live SSE stream (prints JSON events) |
| `earsay un-subscribe TICKET` | Cancel a subscription by ticket ID |
| `earsay warmup` | Pre-load heavy dependencies (optional — `listen` works without it but loads slower) |

---

## HTTP API

When running with `--port`, these endpoints are available on `127.0.0.1`:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/text` | All transcribed text |
| `GET` | `/new-text` | Text since last checkpoint |
| `POST` | `/checkpoint?at=N` | Create a checkpoint |
| `POST` | `/re-checkpoint?at=N` | Correct the last checkpoint position |
| `POST` | `/pause` | Release microphone |
| `POST` | `/resume` | Reopen microphone |
| `POST` | `/stop` | Shut down the server process |
| `GET` | `/status` | Server stats (uptime, chars transcribed, subscriptions) |
| `POST` | `/subscribe?chars=N&timeout=MS&fullchunk=BOOL` | SSE event stream |
| `DELETE` | `/subscribe/{ticket}` | Cancel a subscription |

The `/subscribe` endpoint streams Server-Sent Events. Each `data:` line is a
JSON object with `text` (newly transcribed characters), `potential_index`, and
`trigger` (`"chars"` for threshold-based events or `"timeout"` for
silence-triggered events). Large utterances are split into multiple
`chars_threshold`-sized events for reliable batch-injection workflows.
The `chars` parameter fires events of up to N characters each. The `timeout`
parameter (default 5000 ms) fires after MS ms of silence. Set `fullchunk=true`
to send the full potential chunk instead of deltas.

---

## How It Works

EarSay is a Python process that runs three layers:

**Audio capture** — uses sounddevice to read from the system microphone.
Voice Activity Detection (VAD) filters out silence. A noise floor is
calibrated on startup so it adapts to your environment.

**Transcription engine** — runs faster-whisper (a optimized version of
OpenAI's Whisper model) on each speech segment. Default model is `tiny.en`
(~75 MB, fast). Larger models like `small`, `medium`, or `large` give better
accuracy at the cost of speed and memory.

**HTTP server** — built with FastAPI + uvicorn. Exposes the transcribed text
through a REST API and SSE streaming. Multiple programs can read the text
simultaneously — each subscription tracks its own checkpoint position.

The server writes a PID file to `~/.earsay/pid` so CLI commands can find it
without you specifying the port every time.

---

## OpenCode Integration

[opencode-earsay](https://github.com/AlastorMordrek/opencode-earsay) wires
EarSay into your OpenCode agent. Install that plugin, restart opencode, and
speak — the LLM analyzes speech autonomously.

---

## Uninstall

```bash
cd earsay
./uninstall.sh
```

Stops the server, removes the virtual environment, deletes `~/.earsay/`
and the `~/.local/bin/earsay` symlink, and cleans up PATH additions from
your shell profile. If earsay was installed by the opencode-earsay plugin,
use that plugin's `voice_uninstall` tool instead.

---

## License

MIT
