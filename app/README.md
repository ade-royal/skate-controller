# Skate Controller app

Tauri + SvelteKit UI. On launch it starts `backend/server.py`, which SSHes into the Pi,
uploads and starts `backend/pi_agent.py` (IMU over UDP + webcam MJPEG), holds the lean keys
and runs the keyboard -> Xbox bridge. Closing the window stops all of it.

## One-time setup (Windows laptop)

```
pip install aiohttp paramiko pynput vgamepad
cd app && npm install
```

Create `backend/config.json` (git-ignored):

```json
{ "pi_host": "172.20.10.6", "pi_user": "royal", "pi_password": "<password>" }
```

Laptop and Pi must be on the same hotspot.

## Run

- Dev: `cd app && npm run tauri dev`
- Standalone: `npm run tauri build -- --no-bundle`, then run `app/src-tauri/target/release/app.exe`

## Tabs

- **Bindings**: line-art board tilts with the real one. Click a key chip, press a letter to
  rebind. Calibrate = stand neutral and click. Pop (Space) stays off until the detector is
  confirmed; see `POP_AVAILABLE` / `App.detect_pop` in `backend/server.py`.
- **Ride POV**: webcam with IMU HUD. Rotate 180° if the camera is mounted upside down.
