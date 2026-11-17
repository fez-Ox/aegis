#!/usr/bin/env bash
# Start the four local processes of the Aegis live showcase.
# See demo/README.md and docs/running_aegis.md Parts A/B before running.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SESSION_NAME="aegis-demo"
STREAM_URL="${AEGIS_STREAM_URL:-}"
SESSION_ID="demo-$(date -u +%Y%m%dT%H%M%SZ)"
DATASET_ID="live_demo"
HOME_ID="aegis-demo"
CAPTURES="captures"
SEGMENT_FRAMES=60
PORT=8000
MAX_DURATION=900
SIMULATOR=1
RERUN=1
PREFLIGHT=1
DETACHED=0
STOP=0

usage() {
  cat <<'EOF'
Start the four local processes of the Aegis live showcase.
See demo/README.md and docs/running_aegis.md Parts A/B before running.

Options:
  --stream-url URL       IP Webcam MJPEG URL (default: AEGIS_STREAM_URL)
  --session-id ID        capture session id (default: demo-<UTC timestamp>)
  --dataset-id ID        base dataset id for segments (default: live_demo)
  --home-id ID           home store id (default: aegis-demo)
  --captures DIR         capture output root (default: captures)
  --segment-frames N     frames per segment (default: 60; measure before choosing)
  --max-duration N       capture duration seconds (default: 900)
  --port N               API port (default: 8000)
  --no-simulator         do not expose /simulate/* routes
  --no-rerun             skip the per-segment Rerun recording
  --skip-preflight       do not run demo/preflight.py
  --detached             leave processes running in tmux instead of attaching
  --stop                 stop an existing demo session and exit
  -h, --help             this help
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --stream-url) STREAM_URL="$2"; shift 2 ;;
    --session-id) SESSION_ID="$2"; shift 2 ;;
    --dataset-id) DATASET_ID="$2"; shift 2 ;;
    --home-id) HOME_ID="$2"; shift 2 ;;
    --captures) CAPTURES="$2"; shift 2 ;;
    --segment-frames) SEGMENT_FRAMES="$2"; shift 2 ;;
    --max-duration) MAX_DURATION="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --no-simulator) SIMULATOR=0; shift ;;
    --no-rerun) RERUN=0; shift ;;
    --skip-preflight) PREFLIGHT=0; shift ;;
    --detached) DETACHED=1; shift ;;
    --stop) STOP=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ "$STOP" -eq 1 ]; then
  if command -v tmux >/dev/null 2>&1; then
    tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
  fi
  echo "Stopped $SESSION_NAME (background processes, if any, were signalled on exit)."
  exit 0
fi

if [ -z "$STREAM_URL" ]; then
  echo "error: pass --stream-url or set AEGIS_STREAM_URL" >&2
  exit 2
fi

PAUSE_FILE="$CAPTURES/.pause"
SESSION_DIR="$CAPTURES/$SESSION_ID"
FIRST_SEGMENT="${DATASET_ID}_seg0001"

if [ "$PREFLIGHT" -eq 1 ]; then
  echo "==> preflight"
  uv run python -m demo.preflight \
    --stream-url "$STREAM_URL" \
    --segment-frames "$SEGMENT_FRAMES" \
    || { echo "preflight failed — fix the NO-GO items above" >&2; exit 1; }
fi

CAPTURE_CMD=(
  uv run aegis-ingest
  --url "$STREAM_URL"
  --output-root "$CAPTURES"
  --session-id "$SESSION_ID"
  --config-path config/live.yaml
  --sample-fps 2
  --keyframe-selection
  --pause-file "$PAUSE_FILE"
  --max-duration "$MAX_DURATION"
)
PIPELINE_CMD=(
  uv run python run_pipeline.py
  --config-path config/live.yaml
  --live-session "$SESSION_DIR"
  --dataset-id "$DATASET_ID"
  --home-id "$HOME_ID"
  --stage live
  --follow
  --segment-frames "$SEGMENT_FRAMES"
)
if [ "$RERUN" -eq 1 ]; then PIPELINE_CMD+=(--rerun); fi
SERVER_CMD=(
  env
  "AEGIS_HOME_ID=$HOME_ID"
  "AEGIS_CAPTURE_DIR=$CAPTURES"
  "AEGIS_CAPTURE_PAUSE_FILE=$PAUSE_FILE"
  uv run python run_server.py
  --dataset-id "$FIRST_SEGMENT"
  --port "$PORT"
)
if [ "$SIMULATOR" -eq 1 ]; then SERVER_CMD+=(--enable-simulator); fi
RERUN_CMD=(uv run --group viewer rerun "outputs/${FIRST_SEGMENT}/viewer/demo.rrd")

cmdstr() { printf '%q ' "$@"; }

echo "==> capture   : $SESSION_DIR"
echo "==> pipeline  : $DATASET_ID (segments of $SEGMENT_FRAMES frames)"
echo "==> home store: outputs/_homes/$HOME_ID"
echo "==> first segment: $FIRST_SEGMENT"

PIDS=()
cleanup() {
  local pid
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

if command -v tmux >/dev/null 2>&1; then
  tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
  tmux new-session -d -s "$SESSION_NAME" -n capture
  tmux send-keys -t "$SESSION_NAME:capture" "$(cmdstr "${CAPTURE_CMD[@]}")" C-m
  tmux new-window -t "$SESSION_NAME" -n pipeline
  tmux send-keys -t "$SESSION_NAME:pipeline" "$(cmdstr "${PIPELINE_CMD[@]}")" C-m
  MODE=tmux
else
  LOG_DIR="outputs/demo_logs"
  mkdir -p "$LOG_DIR"
  nohup "${CAPTURE_CMD[@]}" >"$LOG_DIR/capture.log" 2>&1 & PIDS+=("$!")
  sleep 2
  nohup "${PIPELINE_CMD[@]}" >"$LOG_DIR/pipeline.log" 2>&1 & PIDS+=("$!")
  MODE=background
  echo "==> no tmux; logs in $LOG_DIR/"
fi

# Wait for the first segment to finish before starting the API and viewer,
# so the app starts against a graph that actually exists.
echo "==> waiting for $FIRST_SEGMENT (up to 12 minutes)..."
READY=0
for _ in $(seq 1 144); do
  if [ -f "outputs/$FIRST_SEGMENT/objects/r4d_scene_graph.json" ]; then
    READY=1
    break
  fi
  sleep 5
done

if [ "$READY" -eq 0 ]; then
  echo "error: first segment did not appear in time; check the pipeline log" >&2
  exit 1
fi

echo "==> first segment ready; starting API and Rerun"
if [ "$MODE" = "tmux" ]; then
  tmux new-window -t "$SESSION_NAME" -n api
  tmux send-keys -t "$SESSION_NAME:api" "$(cmdstr "${SERVER_CMD[@]}")" C-m
  if [ "$RERUN" -eq 1 ]; then
    tmux new-window -t "$SESSION_NAME" -n rerun
    tmux send-keys -t "$SESSION_NAME:rerun" "$(cmdstr "${RERUN_CMD[@]}")" C-m
  fi
else
  nohup "${SERVER_CMD[@]}" >"outputs/demo_logs/api.log" 2>&1 & PIDS+=("$!")
  if [ "$RERUN" -eq 1 ]; then
    nohup "${RERUN_CMD[@]}" >"outputs/demo_logs/rerun.log" 2>&1 & PIDS+=("$!")
  fi
fi

LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo 127.0.0.1)"
cat <<EOF

===============================================================================
  AEGIS LIVE SHOWCASE IS RUNNING
===============================================================================
  Backbone status:
    uv run python -m demo.pipeline_status --session "$SESSION_DIR" \
      --base-dataset-id "$DATASET_ID" --home-id "$HOME_ID"

  API / Swagger:
    http://$LAN_IP:$PORT/docs

  App: open Settings and enter $LAN_IP (port $PORT is added automatically).

  Per-segment answer (what the app shows):
    curl "http://localhost:$PORT/api/v1/query?item=keys&dataset_id=$FIRST_SEGMENT"

  Durable home memory (what the app cannot show today):
    curl "http://localhost:$PORT/api/v1/query?item=keys"
    curl "http://localhost:$PORT/api/v1/timeline"
    curl "http://localhost:$PORT/api/v1/rooms"

  Pause / resume capture:
    touch "$PAUSE_FILE"  /  rm "$PAUSE_FILE"

  Stop:
    demo/run_demo.sh --stop
===============================================================================
EOF

if [ "$MODE" = "tmux" ] && [ "$DETACHED" -eq 0 ]; then
  tmux attach -t "$SESSION_NAME"
elif [ "$MODE" = "background" ]; then
  echo "Processes running in background (PIDs: ${PIDS[*]}). Press Ctrl-C to stop."
  wait
else
  echo "Detached. Attach with: tmux attach -t $SESSION_NAME"
fi
