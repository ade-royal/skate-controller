"""HTTP/WebSocket routes for the phone remote (backend/phone.py)."""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path

import segno
from aiohttp import WSMsgType, web

from backend import pi_link

HERE = Path(__file__).resolve().parent
FONTS_DIR = HERE.parent / "app" / "static" / "fonts"
STATE_PUSH_S = 0.25


def phone_url(app, port: int) -> str:
    """Address the iPhone uses: the laptop's IP on the hotspot (same route the Pi uses)."""
    ip = app.laptop_ip
    if not ip:
        try:
            ip = pi_link.laptop_ip_for(app.config["pi_host"])
        except pi_link.PiError:
            ip = "127.0.0.1"
    return f"http://{ip}:{port}/phone"


def _state(app) -> str:
    return json.dumps({**app.phone.status(), "keys": app.keys_enabled})


async def page(request: web.Request) -> web.FileResponse:
    return web.FileResponse(HERE / "phone.html", headers={"Cache-Control": "no-store"})


async def font(request: web.Request) -> web.StreamResponse:
    path = (FONTS_DIR / request.match_info["name"]).resolve()
    if path.parent != FONTS_DIR.resolve() or not path.exists():
        raise web.HTTPNotFound()
    return web.FileResponse(path)


async def qr(request: web.Request) -> web.Response:
    app = request.app["app"]
    url = phone_url(app, request.app["port"])
    buf = io.BytesIO()  # full SVG with xmlns, required when loaded via <img>
    segno.make(url, error="m").save(buf, kind="svg", scale=5, border=2, dark="#0b0b0b", light="#f4f4f4")
    return web.Response(body=buf.getvalue(), content_type="image/svg+xml", headers={"Cache-Control": "no-store"})


async def ws(request: web.Request) -> web.WebSocketResponse:
    app = request.app["app"]
    sock = web.WebSocketResponse(heartbeat=5)
    await sock.prepare(request)
    app.phone.clients += 1

    async def push_state() -> None:
        last = None
        while True:
            message = _state(app)
            if message != last:
                await sock.send_str(message)
                last = message
            await asyncio.sleep(STATE_PUSH_S)

    pusher = asyncio.create_task(push_state())
    try:
        async for msg in sock:
            if msg.type != WSMsgType.TEXT:
                continue
            cmd = json.loads(msg.data)
            kind = cmd.get("cmd")
            if not app.keys_enabled:
                continue
            if kind == "y":
                await app.phone.press_y()
            elif kind == "walk":
                app.phone.set_walk(bool(cmd.get("on")))
            elif kind == "push":
                app.phone.set_push(bool(cmd.get("on")))
            await sock.send_str(_state(app))
    finally:
        pusher.cancel()
        app.phone.clients -= 1
        if app.phone.clients <= 0:
            app.phone.clients = 0
            app.phone.stop()  # phone gone: never leave W or push running
    return sock


def add_routes(webapp: web.Application) -> None:
    webapp.router.add_get("/phone", page)
    webapp.router.add_get("/phone/ws", ws)
    webapp.router.add_get("/phone/qr.svg", qr)
    webapp.router.add_get("/phone/fonts/{name}", font)
