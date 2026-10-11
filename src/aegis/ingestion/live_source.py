"""Replaceable live frame-source adapters for egocentric capture.

This module is intentionally independent from the batch video pipeline. It
provides the FR1/FR2 boundary used by local live capture: a source yields
validated decoded frames, while downstream ingestion decides how to sample and
persist them.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True, slots=True)
class DecodedFrame:
    """A decoded image frame and the laptop receive/decode timestamp."""

    image: Any
    received_at: datetime


class FrameSource(Protocol):
    """Generic live frame source boundary.

    Implementations may read from IP Webcam MJPEG, RTSP, a wearable SDK, a test
    fixture, or any future live source without changing storage code.
    """

    def frames(self) -> Iterator[DecodedFrame]:
        """Yield decoded frames until the source ends or fails."""


class OpenCVMjpegSource:
    """Read decoded frames from an HTTP/MJPEG URL using OpenCV."""

    def __init__(self, url: str):
        self.url = url

    def frames(self) -> Iterator[DecodedFrame]:
        """Open the stream and yield decoded frames.

        OpenCV is imported lazily so environments that only run tests or the
        Modal batch pipeline do not import it until live capture is used.
        """

        import cv2

        capture = cv2.VideoCapture(self.url)
        try:
            if not capture.isOpened():
                raise ConnectionError(f"could not open stream: {safe_url(self.url)}")
            while True:
                ok, image = capture.read()
                if not ok or image is None:
                    raise ConnectionError("stream ended or frame decode failed")
                yield DecodedFrame(image=image, received_at=datetime.now(UTC))
        finally:
            capture.release()


def safe_url(url: str) -> str:
    """Return a URL with username/password stripped for logs and manifests."""

    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        host += f":{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))
