#!/usr/bin/env bash
# Start the deployed Aegis gateway and make sure the demo graph is present.
# Safe to run any time: it is idempotent.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

DATASET="${AEGIS_DATASET_ID:-my_room}"
BASE_URL="https://sans42699--aegis-memory-api-serve-memory-api.us-east.modal.run"

graph="outputs/${DATASET}/objects/r4d_scene_graph.json"
if [[ -f "$graph" ]]; then
    echo "==> Restoring scene graph from $graph"
    uv run modal volume put aegis-poc-data "$graph" \
        "${DATASET}/outputs/objects/r4d_scene_graph.json" --force
fi

echo "==> Deploying Aegis gateway (dataset: $DATASET)"
AEGIS_DATASET_ID="$DATASET" uv run modal deploy src/aegis/remote/serve.py

echo "==> Waiting for $BASE_URL/api/v1/health"
for _ in $(seq 1 30); do
    if curl -fsS -m 10 "$BASE_URL/api/v1/health" >/dev/null 2>&1; then
        echo "API is live: $BASE_URL"
        exit 0
    fi
    sleep 2
done
echo "API did not come up; check 'uv run modal app list'." >&2
exit 1
