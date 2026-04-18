"""Camera feed — async OpenCV frame capture for the SOVEREIGN HUD."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Frame:
    width: int
    height: int
    channels: int
    data: bytes           # raw BGR bytes (or empty if no camera)
    timestamp: float = field(default_factory=time.time)
    camera_index: int = 0

    @property
    def available(self) -> bool:
        return len(self.data) > 0

    def to_jpeg_bytes(self) -> bytes:
        """Encode frame to JPEG bytes (requires cv2)."""
        if not self.available:
            return b""
        try:
            import cv2, numpy as np  # type: ignore
            arr = np.frombuffer(self.data, dtype=np.uint8).reshape(self.height, self.width, self.channels)
            _, buf = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return buf.tobytes()
        except Exception as exc:
            logger.debug("Frame.to_jpeg_bytes: %s", exc)
            return b""


_EMPTY_FRAME = Frame(width=0, height=0, channels=3, data=b"")


class CameraFeed:
    """
    Async wrapper around OpenCV VideoCapture.

    Captures frames in a background executor thread and exposes
    ``get_frame()`` / ``run_loop()`` for the HUD overlay pipeline.
    Falls back gracefully if cv2 is not installed.
    """

    def __init__(self, camera_index: int = 0, fps: float = 15.0) -> None:
        self._index = camera_index
        self._fps = fps
        self._interval = 1.0 / fps
        self._cap = None
        self._running = False
        self._latest: Frame = _EMPTY_FRAME
        self._available = False
        self._lock = asyncio.Lock()

        try:
            import cv2  # type: ignore
            self._available = True
            logger.info("CameraFeed: cv2 available (index=%d, fps=%.1f)", camera_index, fps)
        except ImportError:
            logger.debug("CameraFeed: cv2 not installed — running in stub mode")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_frame(self) -> Frame:
        """Return the latest captured frame (non-blocking)."""
        async with self._lock:
            return self._latest

    async def capture_once(self) -> Frame:
        """Capture a single frame synchronously (blocks for one frame)."""
        if not self._available:
            return _EMPTY_FRAME
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._capture_sync)

    async def run_loop(self, stop_event: asyncio.Event | None = None) -> None:
        """Background capture loop — updates self._latest at target FPS."""
        self._running = True
        logger.info("CameraFeed: starting capture loop")
        loop = asyncio.get_event_loop()
        while self._running:
            if stop_event and stop_event.is_set():
                break
            if self._available:
                frame = await loop.run_in_executor(None, self._capture_sync)
                async with self._lock:
                    self._latest = frame
            await asyncio.sleep(self._interval)
        self._release()

    def stop(self) -> None:
        self._running = False

    @property
    def is_available(self) -> bool:
        return self._available

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _capture_sync(self) -> Frame:
        try:
            import cv2  # type: ignore
            if self._cap is None:
                self._cap = cv2.VideoCapture(self._index)
            ret, frame = self._cap.read()
            if not ret or frame is None:
                return _EMPTY_FRAME
            h, w, c = frame.shape
            return Frame(width=w, height=h, channels=c, data=frame.tobytes())
        except Exception as exc:
            logger.debug("CameraFeed._capture_sync: %s", exc)
            return _EMPTY_FRAME

    def _release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        logger.info("CameraFeed: released")
