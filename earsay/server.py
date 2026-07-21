from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
import uvicorn

from earsay.models import (
    Checkpoint,
    NewText,
    PidFile,
    Status,
    SubscriptionEvent,
    SubscriptionRequest,
)
from earsay.text_manager import TextManager
from earsay.transcriber import Transcriber

PID_DIR = os.path.expanduser("~/.earsay")
PID_FILE = os.path.join(PID_DIR, "pid")


def _write_pid(port: int) -> None:
    os.makedirs(PID_DIR, exist_ok=True)
    data = PidFile(
        port=port,
        pid=os.getpid(),
        started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    import dataclasses
    with open(PID_FILE, "w") as f:
        json.dump(dataclasses.asdict(data), f)


def _remove_pid() -> None:
    try:
        os.remove(PID_FILE)
    except OSError:
        pass


def _read_pid() -> Optional[PidFile]:
    try:
        with open(PID_FILE) as f:
            data = json.load(f)
        return PidFile(**data)
    except (OSError, TypeError, KeyError):
        return None


def create_app(
    text_manager: TextManager,
    transcriber: Transcriber,
) -> FastAPI:

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        transcriber.stop()

    app = FastAPI(lifespan=lifespan)

    async def _timeout_loop():
        while transcriber.is_paused is not None:
            if text_manager.subscription_count() > 0:
                text_manager.fire_timeout_subscriptions()
            await asyncio.sleep(0.1)

    @app.on_event("startup")
    async def startup():
        asyncio.create_task(_timeout_loop())

    @app.get("/text")
    async def get_text():
        return {"text": text_manager.all_text()}

    @app.get("/new-text")
    async def get_new_text():
        result = text_manager.new_text()
        return {"potential_index": result.potential_index, "text": result.text}

    @app.post("/checkpoint")
    async def set_checkpoint(at: int = Query(..., description="Character position")):
        try:
            cp = text_manager.set_checkpoint(at)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        clamped = at > len(text_manager.all_text())
        resp = {"index": cp.index, "text": cp.text}
        if clamped:
            return resp, 200, {"X-Clamped": "true"}
        return resp

    @app.post("/re-checkpoint")
    async def re_checkpoint(at: int = Query(..., description="New character position")):
        try:
            cp = text_manager.re_checkpoint(at)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        clamped = at > len(text_manager.all_text())
        resp = {"index": cp.index, "text": cp.text}
        if clamped:
            return resp, 200, {"X-Clamped": "true"}
        return resp

    @app.post("/pause")
    async def pause():
        transcriber.pause()
        return {"status": "paused"}

    @app.post("/resume")
    async def resume():
        transcriber.resume()
        return {"status": "listening"}

    @app.post("/stop")
    async def stop():
        transcriber.stop()
        _remove_pid()
        return {"status": "stopped"}

    @app.get("/status")
    async def status():
        s = text_manager.status
        s["status"] = "paused" if transcriber.is_paused else "listening"
        return s

    @app.post("/subscribe")
    async def subscribe(
        chars: int = Query(30, description="Characters threshold"),
        timeout: int = Query(3000, description="Silence timeout in ms"),
        fullchunk: bool = Query(False, description="Send full chunk instead of delta"),
    ):
        req = SubscriptionRequest(chars=chars, timeout_ms=timeout, fullchunk=fullchunk)
        sub = text_manager.add_subscription(req)

        async def event_stream():
            yield f"data: {json.dumps({'ticket': sub.ticket})}\n\n"
            try:
                while True:
                    event = await sub.event_queue.get()
                    if event is None:
                        break
                    payload = json.dumps({
                        "potential_index": event.potential_index,
                        "text": event.text,
                    })
                    yield f"data: {payload}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                text_manager.remove_subscription(sub.ticket)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.delete("/subscribe/{ticket}")
    async def unsubscribe(ticket: str):
        found = text_manager.remove_subscription(ticket)
        if not found:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return {"ticket": ticket}

    return app


def run_server(port: int, text_manager: TextManager, transcriber: Transcriber) -> None:
    _write_pid(port)
    app = create_app(text_manager, transcriber)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.run()
    _remove_pid()
