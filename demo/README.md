# Live showcase harness

This directory adds **only orchestration, status and narration** around the
existing system. It does not change `src/`, the Modal pipeline, or the Flutter
app. The authoritative setup and verification procedures are in
[`docs/running_aegis.md`](../docs/running_aegis.md) — read Parts A and B first.

## What is here

| File | Purpose |
|---|---|
| `run_demo.sh` | One command to start capture, the live pipeline, the API and Rerun. Prefer tmux; falls back to background processes with logs. `--stop` tears it down. |
| `preflight.py` | Automates running_aegis B1/B2/B7: toolchain, tests, Modal profile/secret/volumes, `HF_TOKEN`, one frame from the phone stream, disk, and a measured VGGT window. Exits non-zero on any NO-GO. |
| `pipeline_status.py` | Read-only, one-screen view of capture → segments → GPU stage timings → home store → room names, from artifacts already on disk. |
| `talk_track.md` | Minute-by-minute narration, the "why it works this way" table, and the honest "not built yet" slide. |

## Before the show (once)

1. `docs/running_aegis.md` Part A §§1–3: code, `uv sync --dev --group viewer`, Modal profile, `aegis-secrets`, `.env` with `HF_TOKEN`.
2. **Calibrate — one command replaces three manual scripts:**

   ```bash
   uv run python -m demo.calibrate --capture captures/<short-walk>
   ```

   It reads the stage timings already in `outputs/*/benchmark_stats.json`
   (your real runs already prove 100–117 keyframes at ~67% of L4 VRAM), reads
   the kept-frame rate from the short capture, prints **"USE --segment-frames
   N"** in plain language, and writes `outputs/evaluation/vggt_window.json`
   plus `demo/demo.conf`. `run_demo.sh` and `preflight.py` pick both up
   automatically — you do not pass the number around yourself.

   Without a capture it still works, but labels the frame rate as an
   assumption. Add `--measure` only if you want a fresh GPU sweep; it streams
   progress instead of going silent for eight minutes (the raw
   `measure_vggt_window.py` prints only at the very end, after image build and
   model load).

3. **Part B2 — first real Modal run / fallback + warm:** run the `put_shoes`
   preset with `--stage all` into a throwaway home so a valid graph, `.rrd`
   and warm GPU containers exist even if Wi-Fi fails.

## On the day

```bash
export AEGIS_STREAM_URL='http://192.168.1.23:8080/video'
uv run python -m demo.preflight --segment-frames 60 \
  --vggt-window-result outputs/evaluation/vggt_window.json

demo/run_demo.sh --stream-url "$AEGIS_STREAM_URL" \
  --session-id demo-$(date -u +%Y%m%dT%H%M%SZ) \
  --dataset-id live_demo --home-id aegis-demo --segment-frames 60
```

The launcher prints the exact status and query commands once the first segment
is ready. Follow `demo/talk_track.md`.

## Cost

Modal Starter gives $30/month of compute; this workspace also has a **$5 usage
cap** (verified 2026-11-17). Verified rates: L4 `$0.000222/s`, CPU
`$0.0000131/core/s`. Measured stage times are ~2 s/keyframe for VGGT and
~0.6–1.8 s/keyframe for detect. Expected total for measurement + fallback +
a 15-minute live show is **≈ $1.5–2.0**. Warm GPU containers
(`scaledown_window=300`) are the main cost driver, so keep the show short and
stop the `--follow` process when the talk ends. Do not run the one-hour soak
as part of this demo.

## Known limits of what you are showing

No auth/TLS, no speech, no temporal questions, no computed confidence or
abstention, no evidence image in the app, no room-rename screen. Those are
planned in `context/plan.md` Part II (WP16–WP35), not present today. The app
sends `dataset_id` on every query, so it shows **one segment's graph**;
durable cross-segment memory is shown through the API with `home_id`. The
"Tap to Ask by Voice" button is a stub — do not press it on stage.
