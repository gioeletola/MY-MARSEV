"""Face tracking — MediaPipe-based face landmark detection for HUD awareness."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FaceData:
    detected: bool = False
    x: float = 0.5
    y: float = 0.5
    size: float = 0.0
    gaze_direction: str = "center"
    attention: float = 0.0


class FaceTracker:
    """
    Uses MediaPipe FaceMesh to detect and track user's face in real time.
    Falls back gracefully if mediapipe/cv2 not installed.
    """

    def __init__(self, camera_index: int = 0) -> None:
        self._camera_index = camera_index
        self._available = False
        self._cap = None
        self._face_mesh = None
        try:
            import cv2  # type: ignore
            import mediapipe  # type: ignore
            self._available = True
            logger.info("FaceTracker: mediapipe available")
        except ImportError:
            logger.debug("mediapipe/cv2 not available — FaceTracker in stub mode")

    async def get_frame(self) -> FaceData:
        if not self._available:
            return FaceData(detected=False)
        return await asyncio.get_event_loop().run_in_executor(None, self._detect)

    def _detect(self) -> FaceData:
        import cv2  # type: ignore
        import mediapipe as mp  # type: ignore
        if self._cap is None:
            self._cap = cv2.VideoCapture(self._camera_index)
        if self._face_mesh is None:
            self._face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False, max_num_faces=1, min_detection_confidence=0.5
            )
        ret, frame = self._cap.read()
        if not ret:
            return FaceData(detected=False)
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._face_mesh.process(rgb)
        if not results.multi_face_landmarks:
            return FaceData(detected=False)
        lm = results.multi_face_landmarks[0].landmark
        nose = lm[1]
        return FaceData(
            detected=True,
            x=nose.x,
            y=nose.y,
            size=abs(lm[10].y - lm[152].y),
            gaze_direction="center",
            attention=0.9,
        )

    def release(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None
