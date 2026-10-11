# Live Egocentric Capture

The current repository supports a local FR1/FR2 capture path in addition to the existing batch-video and Modal pipeline.

## Architecture

```text
Android/IP Webcam MJPEG stream
        -> OpenCVMjpegSource
        -> ingest_live sampling/reconnect loop
        -> LiveSessionWriter
        -> captures/<session-id>/{frame_*.jpg,index.jsonl,session.json}
```

The source boundary is `aegis.ingestion.FrameSource`. Future wearable or RTSP adapters can implement the same `frames()` interface without changing session persistence.

## Run locally

Install the project environment with `uv`, then provide an MJPEG URL:

```bash
uv sync
uv run aegis-ingest \
  --url 'http://PHONE_IP:8080/video' \
  --source-id android-ip-webcam-01 \
  --output-root ./captures \
  --sample-fps 2 \
  --max-duration 600
```

The URL may also be supplied as `AEGIS_STREAM_URL`. Other supported environment variables are:

- `AEGIS_SOURCE_ID`
- `AEGIS_OUTPUT_ROOT`
- `AEGIS_SAMPLE_FPS`
- `AEGIS_MAX_DURATION_SECONDS`
- `AEGIS_RECONNECT_INTERVAL_SECONDS`
- `AEGIS_RECONNECT_TIMEOUT_SECONDS`

Credentials are accepted by the URL if the camera application requires them, but the CLI and manifests redact URL userinfo. Do not commit credentials.

## Session contract

Each run gets a unique directory containing:

- `frame_XXXXXXXX_<timestamp>.jpg`: sampled JPEG frames;
- `index.jsonl`: one downstream-readable record per frame;
- `session.json`: run status, source metadata, reconnect count, and frame count.

The JSONL contract records the session ID, sequence, relative frame path, source ID, laptop receive/decode timestamp, ingestion timestamp, dimensions, encoding, target sampling rate, and source protocol. This is the handoff boundary for future FR3 processing.

## Status and reconnect behavior

The live pipeline supports these terminal statuses:

- `time_limit`: configured duration elapsed;
- `stopped`: operator interrupted the process;
- `disconnected`: source failure continued beyond the reconnect timeout;
- `completed`: source ended after a successful run, although a finite source is normally treated as a disconnect.

A stream failure is retried at the configured interval for the configured timeout. The CLI exits non-zero for `disconnected` and zero for other terminal statuses.

## Testing

Live ingestion tests use an injected deterministic source and do not require a phone or network:

```bash
uv run pytest tests/test_live_ingestion.py -q
```

Physical testing should verify camera orientation, WiFi stability, frame quality, expected sample count, reconnect behavior, local-only storage, and storage retention before connecting sessions to reconstruction or memory construction.
