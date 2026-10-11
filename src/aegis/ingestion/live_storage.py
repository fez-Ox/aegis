"""Local live-capture session persistence and FR3 handoff records."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class LiveSessionWriter:
    """Persist sampled live frames as JPEGs plus JSONL/session metadata."""

    def __init__(self, root: Path, session_id: str, manifest: dict[str, Any]):
        self.session_dir = root / session_id
        self.session_dir.mkdir(parents=True, exist_ok=False)
        self.index_path = self.session_dir / "index.jsonl"
        self._index = self.index_path.open("w", encoding="utf-8")
        self.manifest = dict(manifest)
        self.count = 0

    def write(
        self,
        image: Any,
        *,
        received_at: datetime,
        source_id: str,
        sample_rate: float,
        source_protocol: str,
    ) -> dict[str, Any]:
        """Write one JPEG frame and append its JSONL metadata record."""

        import cv2

        height, width = image.shape[:2]
        timestamp = received_at.astimezone(UTC)
        stamp = timestamp.strftime("%Y%m%dT%H%M%S.%fZ")[:-3]
        filename = f"frame_{self.count:08d}_{stamp}.jpg"
        path = self.session_dir / filename
        if not cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, 90]):
            raise OSError(f"could not write frame: {path}")

        record = {
            "session_id": self.session_dir.name,
            "sequence": self.count,
            "frame_path": filename,
            "source_id": source_id,
            "capture_timestamp": timestamp.isoformat().replace("+00:00", "Z"),
            "timestamp_source": "laptop_receive_decode",
            "ingestion_timestamp": datetime.now(UTC).isoformat().replace(
                "+00:00", "Z"
            ),
            "width": int(width),
            "height": int(height),
            "encoding": "jpeg",
            "sample_rate_target_hz": float(sample_rate),
            "source_protocol": source_protocol,
        }
        self._index.write(json.dumps(record, sort_keys=True) + "\n")
        self._index.flush()
        self.count += 1
        return record

    def close(
        self,
        *,
        status: str,
        ended_at: datetime,
        error: str | None = None,
    ) -> None:
        """Finalize the session manifest and close the index file."""

        if not self._index.closed:
            self._index.close()
        self.manifest.update(
            {
                "ended_at": ended_at.astimezone(UTC).isoformat().replace(
                    "+00:00", "Z"
                ),
                "emitted_frame_count": self.count,
                "status": status,
            }
        )
        if error:
            self.manifest["last_error"] = error
        (self.session_dir / "session.json").write_text(
            json.dumps(self.manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
