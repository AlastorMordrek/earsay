from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error

import click
from earsay.text_manager import TextManager

PID_DIR = os.path.expanduser("~/.earsay")
PID_FILE = os.path.join(PID_DIR, "pid")


def _read_pid() -> dict | None:
    try:
        with open(PID_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _get_server_port(explicit_port: int | None) -> int:
    if explicit_port:
        return explicit_port
    data = _read_pid()
    if data:
        return data["port"]
    print("No earsay server running. Start one with: earsay listen --port PORT", file=sys.stderr)
    sys.exit(1)


def _api(method: str, path: str, port: int, query: str = "") -> dict:
    url = f"http://127.0.0.1:{port}{path}"
    if query:
        url += "?" + query
    try:
        req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            print(f"Error: {err.get('detail', body)}", file=sys.stderr)
        except json.JSONDecodeError:
            print(f"Error: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Cannot connect to earsay on port {port}: {e.reason}", file=sys.stderr)
        sys.exit(1)


@click.group()
def main():
    """EarSay — continuous voice-to-text terminal utility."""


@main.command()
@click.option("--download-model", is_flag=True, default=False, help="Also download the whisper model")
def warmup(download_model):
    """Pre-load all heavy dependencies so 'earsay listen' starts instantly.

    Useful in scripts or CI where you want to control when the 15-30
    second cold-import delay happens. Without this, the first call to
    'earsay listen' will incur the delay automatically.

    Example:

        earsay warmup && earsay listen --port 3009
    """
    print("Loading speech recognition engine...", file=sys.stderr)
    from earsay.transcriber import warmup as _transcriber_warmup
    _transcriber_warmup()
    print("Loading server stack...", file=sys.stderr)
    from earsay.server import warmup as _server_warmup
    _server_warmup()

    if download_model:
        print("Downloading whisper model (tiny.en, ~75MB)...", file=sys.stderr)
        from faster_whisper import WhisperModel
        WhisperModel("tiny.en", device="cpu", compute_type="int8", download_root=None)
        print("Model downloaded.", file=sys.stderr)

    print("All dependencies loaded. earsay listen will start instantly.", file=sys.stderr)


@main.command()
@click.option("--port", "-p", type=int, default=None, help="HTTP server port")
@click.option("--file", "-f", "file_path", type=click.Path(), default=None, help="Append transcript to file")
@click.option("--model", "-m", default="tiny.en", help="Whisper model name (default: tiny.en)")
def listen(port, file_path, model):
    """Start continuous transcription.

    Heavy dependencies are imported here on first use. Run 'earsay
    warmup' beforehand to pre-load them and avoid the cold-start delay.
    """
    if not port and not file_path:
        print("Error: at least one of --port or --file is required.", file=sys.stderr)
        print("  earsay listen --port 3009            # server mode", file=sys.stderr)
        print("  earsay listen --file transcript.txt  # standalone mode", file=sys.stderr)
        sys.exit(1)

    from earsay.transcriber import Transcriber
    from earsay.server import run_server

    def on_text(text: str):
        if port:
            tm.append(text)
        else:
            sys.stdout.write(text)
            sys.stdout.flush()

    tm = TextManager(on_append=on_text if port else None)

    if file_path:
        fh = open(file_path, "a")
        def file_on_text(text: str):
            fh.write(text)
            fh.flush()
        if port:
            orig = tm._on_append
            def combined(text: str):
                orig(text)
                file_on_text(text)
            tm._on_append = combined
        else:
            tm._on_append = file_on_text

    transcriber = Transcriber(on_text=on_text, model_name=model)
    transcriber.start()

    if port:
        run_server(port, tm, transcriber)
    else:
        print("Listening... Press Ctrl-C to stop.", file=sys.stderr)
        try:
            while True:
                import time
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            transcriber.stop()


@main.command()
@click.option("--port", "-p", type=int, default=None, help="Server port (default: from pid file)")
def stop(port):
    """Stop the transcription server."""
    port = _get_server_port(port)
    _api("POST", "/stop", port)
    print("Stopped.")


@main.command()
@click.option("--port", "-p", type=int, default=None, help="Server port (default: from pid file)")
def pause(port):
    """Pause transcription (releases the microphone)."""
    port = _get_server_port(port)
    _api("POST", "/pause", port)
    print("Paused.")


@main.command()
@click.option("--port", "-p", type=int, default=None, help="Server port (default: from pid file)")
def resume(port):
    """Resume transcription (opens the microphone)."""
    port = _get_server_port(port)
    _api("POST", "/resume", port)
    print("Resumed.")


@main.command()
@click.option("--port", "-p", type=int, default=None, help="Server port (default: from pid file)")
def text(port):
    """Get all transcribed text since server start."""
    port = _get_server_port(port)
    result = _api("GET", "/text", port)
    print(result["text"])


@main.command()
@click.option("--port", "-p", type=int, default=None, help="Server port (default: from pid file)")
@click.option("--at", "-a", type=int, required=True, help="Character position for checkpoint")
def checkpoint(port, at):
    """Set a checkpoint at the given character position."""
    port = _get_server_port(port)
    result = _api("POST", "/checkpoint", port, f"at={at}")
    print(json.dumps(result, indent=2))


@main.command()
@click.option("--port", "-p", type=int, default=None, help="Server port (default: from pid file)")
@click.option("--at", "-a", type=int, required=True, help="New character position for last checkpoint")
def re_checkpoint(port, at):
    """Correct the last checkpoint to a new position."""
    port = _get_server_port(port)
    result = _api("POST", "/re-checkpoint", port, f"at={at}")
    print(json.dumps(result, indent=2))


@main.command()
@click.option("--port", "-p", type=int, default=None, help="Server port (default: from pid file)")
def new_text(port):
    """Get text since the last checkpoint."""
    port = _get_server_port(port)
    result = _api("GET", "/new-text", port)
    print(json.dumps(result, indent=2))


@main.command()
@click.option("--port", "-p", type=int, default=None, help="Server port (default: from pid file)")
@click.option("--chars", "-c", type=int, default=30, help="Fire when N+ new characters accumulated (default: 30)")
@click.option("--timeout", "-t", type=int, default=3000, help="Fire after MS ms of silence (default: 3000)")
@click.option("--fullchunk", "-F", is_flag=True, default=False, help="Send full potential chunk, not just delta")
def subscribe(port, chars, timeout, fullchunk):
    """Subscribe to real-time transcription events via SSE."""
    port = _get_server_port(port)
    query = f"chars={chars}&timeout={timeout}&fullchunk={'true' if fullchunk else 'false'}"
    url = f"http://127.0.0.1:{port}/subscribe?{query}"

    import urllib.request
    req = urllib.request.Request(url, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=None) as resp:
            for line in resp:
                line = line.decode().strip()
                if line.startswith("data: "):
                    data = line[6:]
                    print(data)
                    sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Error: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Cannot connect to earsay on port {port}: {e.reason}", file=sys.stderr)
        sys.exit(1)


@main.command("un-subscribe")
@click.option("--port", "-p", type=int, default=None, help="Server port (default: from pid file)")
@click.argument("ticket")
def un_subscribe(port, ticket):
    """Cancel a subscription by ticket ID."""
    port = _get_server_port(port)
    result = _api("DELETE", f"/subscribe/{ticket}", port)
    print(json.dumps(result))
