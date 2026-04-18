"""Presence detector — detects whether user is at the computer (webcam or activity)."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class PresenceState:
    present: bool = False
    confidence: float = 0.0
    method: str = "unknown"
    last_seen_at: float = 0.0
    away_for_s: float = 0.0


class PresenceDetector:
    """
    Detects user presence via:
    1. Webcam face detection (MediaPipe / OpenCV) — primary
    2. Keyboard/mouse activity — fallback
    3. Manual signal — always available

    Stub implementation; real one needs mediapipe + opencv.
    """

    def __init__(self, method: str = "activity") -> None:
        self._method = method
        self._state = PresenceState()
        self._last_activity = time.time()
        self._cv_available = False
        try:
            import cv2  # type: ignore
            import mediapipe  # type: ignore
            self._cv_available = True
        except ImportError:
            logger.debug("mediapipe/cv2 not available — PresenceDetector using activity method")

    async def detect(self) -> PresenceState:
        if self._cv_available:
            return await self._detect_face()
        return self._detect_activity()

    def signal_activity(self) -> None:
        self._last_activity = time.time()
        self._state.present = True
        self._state.last_seen_at = self._last_activity

    def _detect_activity(self) -> PresenceState:
        away = time.time() - self._last_activity
        present = away < 120.0
        self._state = PresenceState(
            present=present,
            confidence=0.7 if present else 0.3,
            method="activity",
            last_seen_at=self._last_activity,
            away_for_s=away if not present else 0.0,
        )
        return self._state

    async def _detect_face(self) -> PresenceState:
        try:
            result = await asyncio.get_event_loop().run_in_executor(None, self._run_face_detection)
            return result
        except Exception as exc:
            logger.warning("Face detection error: %s", exc)
            return self._detect_activity()

    def _run_face_detection(self) -> PresenceState:
        import cv2  # type: ignore
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return self._detect_activity()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        present = len(faces) > 0
        now = time.time()
        if present:
            self._last_activity = now
        return PresenceState(
            present=present,
            confidence=0.9 if present else 0.5,
            method="face",
            last_seen_at=self._last_activity if present else self._last_activity,
            away_for_s=0.0 if present else now - self._last_activity,
        )

    def get_presence_signal(self) -> dict:
        """Return a structured presence signal dict.

        Fields:
            face_detected (bool): Whether a face is currently detected.
            attention (float): Attention score 0.0–1.0.
            gaze (str): Gaze direction string (e.g. "center", "away").
            last_seen_s (float): Seconds since the user was last seen.
        """
        last_seen_s = time.time() - self._state.last_seen_at if self._state.last_seen_at else 0.0
        return {
            "face_detected": self._state.present,
            "attention": self._state.confidence,
            "gaze": "center" if self._state.present else "away",
            "last_seen_s": last_seen_s,
        }

    async def run_continuous(
        self,
        stop_event: asyncio.Event,
        callback: Callable[[dict], None],
        interval_s: float = 2.0,
    ) -> None:
        """Async loop: call ``callback(presence_signal)`` every *interval_s* seconds.

        Args:
            stop_event: Set to stop the loop cleanly.
            callback: Sync callable that receives the presence signal dict.
            interval_s: Polling interval in seconds (default 2.0).
        """
        logger.info("PresenceDetector: run_continuous started")
        while not stop_event.is_set():
            try:
                await self.detect()
                signal = self.get_presence_signal()
                try:
                    callback(signal)
                except Exception as exc:
                    logger.warning("PresenceDetector callback error: %s", exc)
            except Exception as exc:
                logger.warning("PresenceDetector run_continuous error: %s", exc)
            await asyncio.sleep(interval_s)
        logger.info("PresenceDetector: run_continuous stopped")

    @property
    def state(self) -> PresenceState:
        return self._state
