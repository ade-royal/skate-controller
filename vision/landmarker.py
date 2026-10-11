"""Run MediaPipe Pose Landmarker on laptop webcam frames.

The pose decisions live in vision.pose. This module only loads the model
and turns a frame into landmarks.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

from vision.pose import LANDMARK_COUNT, Landmark

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)
DEFAULT_MODEL_PATH = Path("models") / "pose_landmarker_lite.task"


def ensure_model(path: Path = DEFAULT_MODEL_PATH) -> Path:
    """Return the local model file, downloading it on first use."""
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    print(f"Downloading pose model to {path}...")
    try:
        urllib.request.urlretrieve(MODEL_URL, temporary)
        temporary.replace(path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise
    return path


class PoseTracker:
    """Video-mode Pose Landmarker for one person."""

    def __init__(self, model_path: Path) -> None:
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise ImportError(
                "mediapipe is required for the webcam pose view. "
                "On the Windows laptop run: pip install mediapipe opencv-python"
            ) from exc

        self._mp = mp
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_poses=1,
        )
        self._landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)
        self._last_timestamp_ms = -1

    def detect(self, rgb_frame, timestamp_ms: int) -> list[Landmark] | None:
        """Return the first pose, or None when nobody is detected."""
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms
        image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB,
            data=rgb_frame,
        )
        result = self._landmarker.detect_for_video(image, timestamp_ms)
        poses = result.pose_landmarks
        if not poses:
            return None
        return [_to_landmark(point) for point in poses[0][:LANDMARK_COUNT]]

    def close(self) -> None:
        self._landmarker.close()


def _to_landmark(point) -> Landmark:
    visibility = getattr(point, "visibility", None)
    if visibility is None:
        visibility = 1.0
    return Landmark(point.x, point.y, point.z, visibility)
