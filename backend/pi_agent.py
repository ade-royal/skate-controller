"""Runs on the Raspberry Pi. Uploaded and started by the laptop app over SSH.

Streams raw MPU-6050 readings to the laptop over UDP and, when a USB webcam is
plugged in, serves it as an MJPEG stream on http://<pi>:8081/stream.

Packets are JSON: {"a": [x, y, z] g, "g": [x, y, z] deg/s, "cam": state, "err": msg}
Classification happens on the laptop using controller/movement.py.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mpu6050 import MPU6050  # noqa: E402  (uploaded beside this file)

SAMPLE_HZ = 50
SENSOR_RETRY_S = 1.0
CAMERA_RETRY_S = 3.0
CAMERA_SIZE = "640x480"
CAMERA_FPS = "30"


class Camera:
    """Keeps the newest JPEG from ffmpeg. Re-detects the webcam if it's unplugged."""

    def __init__(self) -> None:
        self.state = "none"  # none | ok | error
        self.frame: bytes | None = None
        self.cond = threading.Condition()
        threading.Thread(target=self._run, daemon=True).start()

    @staticmethod
    def find_device() -> str | None:
        by_id = sorted(glob.glob("/dev/v4l/by-id/*-video-index0"))
        if by_id:
            return by_id[0]
        return "/dev/video0" if os.path.exists("/dev/video0") else None

    def _run(self) -> None:
        while True:
            device = self.find_device()
            if device is None:
                self.state = "none"
                time.sleep(CAMERA_RETRY_S)
                continue
            # Most UVC webcams output MJPEG directly: copy it, no re-encode.
            for codec_args in (["-input_format", "mjpeg"], []):
                self._stream(device, codec_args)
            self.state = "error"
            time.sleep(CAMERA_RETRY_S)

    def _stream(self, device: str, input_args: list[str]) -> None:
        output = ["-c:v", "copy"] if input_args else ["-c:v", "mjpeg", "-q:v", "7"]
        cmd = ["ffmpeg", "-loglevel", "error", "-f", "v4l2", *input_args,
               "-video_size", CAMERA_SIZE, "-framerate", CAMERA_FPS, "-i", device,
               *output, "-f", "mjpeg", "pipe:1"]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError:
            return
        buf = b""
        try:
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                buf += chunk
                while True:
                    start = buf.find(b"\xff\xd8")
                    end = buf.find(b"\xff\xd9", start + 2)
                    if start < 0 or end < 0:
                        break
                    with self.cond:
                        self.frame = buf[start:end + 2]
                        self.state = "ok"
                        self.cond.notify_all()
                    buf = buf[end + 2:]
                if len(buf) > 4_000_000:
                    buf = b""
        finally:
            proc.kill()


def make_handler(camera: Camera):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        def do_GET(self) -> None:
            if self.path.split("?")[0] != "/stream":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            last = None
            try:
                while True:
                    with camera.cond:
                        camera.cond.wait_for(lambda: camera.frame is not last, timeout=2)
                        frame = camera.frame
                    if frame is None or frame is last:
                        continue
                    last = frame
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                    self.wfile.write(frame + b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass

    return Handler


def open_sensor(sock, target, camera) -> MPU6050:
    while True:
        try:
            return MPU6050()
        except (OSError, ImportError) as exc:
            send(sock, target, {"err": f"sensor: {exc}", "cam": camera.state})
            time.sleep(SENSOR_RETRY_S)


def send(sock, target, packet: dict) -> None:
    try:
        sock.sendto(json.dumps(packet).encode(), target)
    except OSError:
        pass  # hotspot blip; keep going


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=5006)
    parser.add_argument("--cam-port", type=int, default=8081)
    args = parser.parse_args()

    camera = Camera()
    server = ThreadingHTTPServer(("0.0.0.0", args.cam_port), make_handler(camera))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (args.host, args.port)
    sensor = open_sensor(sock, target, camera)
    period = 1.0 / SAMPLE_HZ
    next_tick = time.monotonic()
    while True:
        try:
            a = sensor.get_acceleration()
            g = sensor.get_gyroscope()
            send(sock, target, {
                "a": [round(a["x"], 4), round(a["y"], 4), round(a["z"], 4)],
                "g": [round(g["x"], 2), round(g["y"], 2), round(g["z"], 2)],
                "cam": camera.state,
            })
        except OSError as exc:
            send(sock, target, {"err": f"sensor: {exc}", "cam": camera.state})
            time.sleep(SENSOR_RETRY_S)
        next_tick += period
        delay = next_tick - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            next_tick = time.monotonic()


if __name__ == "__main__":
    main()
