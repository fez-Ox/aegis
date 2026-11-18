#!/usr/bin/env bash
# Local NLQ only: answer from already-downloaded scene graphs.
# Does not upload video, call Modal inference, or download artifacts.
#
# Reads (in order) NL Querying/outputs, sample_outputs, outputs, tests/fixtures.
#
# Usage (from repo root or this folder):
#   ./NL\ Querying/nlq_local.sh
#   ./NL\ Querying/nlq_local.sh --dataset nlq_sample --ask "where is my laptop"
#   ./NL\ Querying/nlq_local.sh --no-llm --ask "where are my shoes"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_env.sh"
cd "${REPO_ROOT}"

DATASET="${DATASET:-nlq_sample}"
ASK="${ASK:-where is my laptop}"
NO_LLM=()

usage() {
  cat <<'EOF'
Usage: nlq_local.sh [options]

  --dataset, -d ID   Dataset id (default: nlq_sample, or $DATASET)
  --ask, -q TEXT     Question to answer (default: "where is my laptop", or $ASK)
  --no-llm           Dictionary-only; skip local Ollama escape hatch
  -h, --help         Show this help

Requires an existing r4d_scene_graph.json for that dataset. Does not run Modal.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dataset|-d)
      DATASET="${2:?--dataset requires a value}"
      shift 2
      ;;
    --ask|-q)
      ASK="${2:?--ask requires a value}"
      shift 2
      ;;
    --no-llm)
      NO_LLM=(--no-llm)
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

SCENE_REL="objects/r4d_scene_graph.json"
FOUND=""
for root in \
  "${SCRIPT_DIR}/outputs/${DATASET}" \
  "${REPO_ROOT}/sample_outputs/${DATASET}" \
  "${REPO_ROOT}/outputs/${DATASET}" \
  "${REPO_ROOT}/tests/fixtures/${DATASET}"; do
  if [[ -f "${root}/${SCENE_REL}" ]]; then
    FOUND="${root}/${SCENE_REL}"
    break
  fi
done

if [[ -z "${FOUND}" ]]; then
  echo "no local scene graph for dataset '${DATASET}'." >&2
  echo "looked for ${SCENE_REL} under NL Querying/outputs, sample_outputs, outputs, tests/fixtures." >&2
  echo "build memory first, or run nlq_full_pipeline.sh." >&2
  exit 1
fi

echo "Local NLQ  dataset=${DATASET}  graph=${FOUND}"
echo "Question:  ${ASK}"
echo

nlq_python "${SCRIPT_DIR}/smoke_test.py" \
  --transport local \
  --dataset "${DATASET}" \
  --ask "${ASK}" \
  "${NO_LLM[@]}"
