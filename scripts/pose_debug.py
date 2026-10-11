"""Show calibrated squat and hand states from the laptop webcam.

Run this on the Windows laptop from the repository root:

    python scripts/pose_debug.py

Press C to calibrate a neutral stance, then Q to quit. This script does
not press game keys and does not connect to the Raspberry Pi.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vision.landmarker import DEFAULT_MODEL_PATH, PoseTracker, ensure_model
from vision.pose import (
    HAND_UP,
    POSE_CONNECTIONS,
    SIDE_NONE,
    SQUAT,
    UNKNOWN,
    Landmark,
    PoseConfig,
    PoseSession,
    PoseView,
)

WINDOW_NAME = "Pose debug"
DECISION_LANDMARKS = {11, 12, 15, 16, 23, 24, 25, 26, 27, 28}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug calibrated squat and hand poses.")
    parser.add_argument("--camera", type=int, default=0, help="Webcam index.")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--squat-enter", type=float, default=PoseConfig.squat_enter)
    parser.add_argument("--squat-exit", type=float, default=PoseConfig.squat_exit)
    parser.add_argument("--hand-enter", type=float, default=PoseConfig.hand_enter)
    parser.add_argument("--hand-exit", type=float, default=PoseConfig.hand_exit)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = PoseConfig(
        squat_enter=args.squat_enter,
        squat_exit=args.squat_exit,
        hand_enter=args.hand_enter,
        hand_exit=args.hand_exit,
    )
    cv2, np = _import_video()
    tracker = PoseTracker(ensure_model(args.model))
    camera = _open_camera(cv2, args.camera)
    session = PoseSession(config)
    print("Pose debug is running.")
    print("Stand sideways in your riding stance, press C, and hold still for 3 seconds.")
    print(
        f"Squat enter starts at {config.squat_enter:.1f} degrees of extra knee bend "
        f"(exit {config.squat_exit:.1f}). That pair is a starting point, not a finished calibration."
    )
    print("Press Q to quit.")
    started = time.perf_counter()
    last_frame = started
    last_timestamp = -1
    fps = 0.0
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                print("The webcam stopped returning frames.")
                break
            now = time.perf_counter()
            fps = 0.9 * fps + 0.1 / max(now - last_frame, 1e-6)
            last_frame = now
            height, width = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            timestamp = max(int((now - started) * 1000), last_timestamp + 1)
            last_timestamp = timestamp
            landmarks = tracker.detect(rgb, timestamp)
            view = session.update(landmarks, width / height, now)
            display = cv2.flip(frame, 1)
            if landmarks is not None:
                _draw_pose(cv2, display, landmarks, width, height)
            panel = _panel(cv2, np, height, view, config, fps)
            cv2.imshow(WINDOW_NAME, np.hstack([display, panel]))
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q")):
                break
            if key in (ord("c"), ord("C")):
                session.start_calibration(time.perf_counter())
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        tracker.close()
        camera.release()
        cv2.destroyAllWindows()


def _import_video():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise ImportError(
            "opencv-python is required for the webcam pose view. "
            "On the Windows laptop run: pip install mediapipe opencv-python"
        ) from exc
    return cv2, np


def _open_camera(cv2, camera_index: int):
    camera = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not camera.isOpened():
        camera.release()
        camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        raise RuntimeError(
            f"Could not open webcam {camera_index}. Close other apps using the camera and try again."
        )
    camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 60)
    return camera


def _draw_pose(cv2, frame, landmarks: list[Landmark], width: int, height: int) -> None:
    for start, end in POSE_CONNECTIONS:
        first = landmarks[start]
        second = landmarks[end]
        if first.visibility < 0.5 or second.visibility < 0.5:
            continue
        cv2.line(frame, _pixel(first, width, height), _pixel(second, width, height), (80, 220, 80), 2)
    for index, landmark in enumerate(landmarks):
        if landmark.visibility < 0.5:
            continue
        color = (0, 180, 255) if index in DECISION_LANDMARKS else (255, 180, 0)
        cv2.circle(frame, _pixel(landmark, width, height), 4, color, -1)


def _panel(cv2, np, height: int, view: PoseView, config: PoseConfig, fps: float):
    panel = np.zeros((height, 460, 3), np.uint8)
    lines = _lines(view, config, fps)
    y = 28
    for text, color in lines:
        if y > height - 16:
            break
        cv2.putText(panel, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)
        y += 18
    return panel


def _lines(view: PoseView, config: PoseConfig, fps: float) -> list[tuple[str, tuple[int, int, int]]]:
    squat_color = (0, 220, 0) if view.squat_state == SQUAT else (210, 210, 210)
    side_color = (0, 140, 255) if view.squat_side == SIDE_NONE else (0, 220, 0)
    hand_color = (0, 220, 0) if view.left_hand_state == HAND_UP or view.right_hand_state == HAND_UP else (210, 210, 210)
    lines = [
        (f"FPS {fps:4.0f}", (180, 180, 180)),
        (f"CALIBRATION  {view.status}", (0, 200, 255)),
        ("", (0, 0, 0)),
        (f"SIDE  {view.squat_side}", side_color),
    ]
    if view.squat_note:
        lines.append((view.squat_note, (0, 140, 255)))
    lines.extend(
        [
            (_leg_visibility_line("L", view.left_hip_visibility, view.left_knee_visibility, view.left_ankle_visibility), (200, 200, 200)),
            (_leg_visibility_line("R", view.right_hip_visibility, view.right_knee_visibility, view.right_ankle_visibility), (200, 200, 200)),
            ("", (0, 0, 0)),
            (f"NEUTRAL  {_num(view.calibrated_knee_angle, 1)} deg", (180, 180, 180)),
            (f"LIVE KNEE  {_num(view.live_knee_angle, 1)} deg", (180, 180, 180)),
            (f"CROUCH  {_signed(view.crouch_degrees, 1)} deg", squat_color),
            (f"ENTER {config.squat_enter:.1f} deg   EXIT {config.squat_exit:.1f} deg", (180, 180, 180)),
            ("starting values, not final", (140, 140, 140)),
            (f"STATE  {view.squat_state}", squat_color),
            ("", (0, 0, 0)),
            (f"L HAND rise {_signed(view.left_hand_rise)}  {view.left_hand_state}", hand_color),
            (f"R HAND rise {_signed(view.right_hand_rise)}  {view.right_hand_state}", hand_color),
            (f"enter {config.hand_enter:.2f}   exit {config.hand_exit:.2f}", (180, 180, 180)),
            (f"HANDS  {view.hands_state}", hand_color),
            ("", (0, 0, 0)),
            (f"L wrist {_flag(view.left_wrist_visible)}", _flag_color(view.left_wrist_visible)),
            (f"R wrist {_flag(view.right_wrist_visible)}", _flag_color(view.right_wrist_visible)),
            ("", (0, 0, 0)),
            ("C calibrate    Q quit", (180, 180, 180)),
            ("L/R are your left and right", (160, 160, 160)),
        ]
    )
    return lines


def _leg_visibility_line(side: str, hip: float, knee: float, ankle: float) -> str:
    return f"{side} hip {hip:.2f}  knee {knee:.2f}  ank {ankle:.2f}"


def _signed(value: float | None, digits: int = 2) -> str:
    if value is None:
        return UNKNOWN
    return f"{value:+.{digits}f}"


def _num(value: float | None, digits: int = 2) -> str:
    if value is None:
        return UNKNOWN
    return f"{value:.{digits}f}"


def _flag(visible: bool) -> str:
    return "ok" if visible else "low"


def _flag_color(visible: bool) -> tuple[int, int, int]:
    if visible:
        return (180, 180, 180)
    return (0, 140, 255)


def _pixel(landmark: Landmark, width: int, height: int) -> tuple[int, int]:
    # The preview is mirrored, so the person's left appears on the left.
    return int((1.0 - landmark.x) * width), int(landmark.y * height)


if __name__ == "__main__":
    main()
