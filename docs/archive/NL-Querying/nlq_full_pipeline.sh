#!/usr/bin/env bash
# Full pathway:
#   input video -> Modal (auth: ~/.modal.toml / MODAL_PROFILE)
#   -> spatio-temporal inference on Modal
#   -> download artifacts
#   -> stage into NL Querying/outputs/<dataset>
#   -> local deterministic NLQ (+ local Ollama LLM escape hatch)
#
# Usage:
#   ./NL\ Querying/nlq_full_pipeline.sh
#   ./NL\ Querying/nlq_full_pipeline.sh --video path/to.mp4 --dataset my_room \
#       --ask "where is my laptop"
#   AEGIS_GPU=cpu ./NL\ Querying/nlq_full_pipeline.sh --gpu cpu

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_env.sh"
cd "${REPO_ROOT}"

VIDEO="${VIDEO:-${SCRIPT_DIR}/sample_input_video.mp4}"
DATASET="${DATASET:-nlq_sample}"
ASK="${ASK:-where is my laptop}"
PROFILE="${MODAL_PROFILE:-i230683}"
GPU="${AEGIS_GPU:-cpu}"
VGGT_MODEL="${AEGIS_VGGT_MODEL:-wincentIsMe/VGGT-Omega}"
KEYFRAME_STRIDE="${AEGIS_KEYFRAME_STRIDE:-}"
NO_LLM=()
SKIP_RUN=0

usage() {
  cat <<'EOF'
Usage: nlq_full_pipeline.sh [options]

  --video PATH           Input video (default: NL Querying/sample_input_video.mp4)
  --dataset, -d ID       Dataset id (default: nlq_sample)
  --ask, -q TEXT         Question after download (default: "where is my laptop")
  --profile NAME         Modal profile in ~/.modal.toml (default: $MODAL_PROFILE or i230683)
  --gpu VALUE            Modal accelerator: cpu, L4, ... (default: $AEGIS_GPU or cpu)
  --vggt-model REPO      VGGT checkpoint override (default: wincentIsMe/VGGT-Omega)
  --keyframe-stride N    VGGT keyframe stride override
  --skip-run             Skip Modal; only re-stage already-downloaded outputs, then NLQ
  --no-llm               Dictionary-only NLQ (no local Ollama)
  -h, --help             Show this help

Modal token is read from ~/.modal.toml. GPU jobs need a billed workspace;
use --gpu cpu when that is unavailable.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --video)
      VIDEO="${2:?--video requires a path}"
      shift 2
      ;;
    --dataset|-d)
      DATASET="${2:?--dataset requires a value}"
      shift 2
      ;;
    --ask|-q)
      ASK="${2:?--ask requires a value}"
      shift 2
      ;;
    --profile)
      PROFILE="${2:?--profile requires a value}"
      shift 2
      ;;
    --gpu)
      GPU="${2:?--gpu requires a value}"
      shift 2
      ;;
    --vggt-model)
      VGGT_MODEL="${2:?--vggt-model requires a value}"
      shift 2
      ;;
    --keyframe-stride)
      KEYFRAME_STRIDE="${2:?--keyframe-stride requires a value}"
      shift 2
      ;;
    --skip-run)
      SKIP_RUN=1
      shift
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

MODAL_TOML="${HOME}/.modal.toml"
if [[ "${SKIP_RUN}" -eq 0 ]]; then
  if [[ ! -f "${MODAL_TOML}" ]]; then
    echo "Modal auth file missing: ${MODAL_TOML}" >&2
    exit 1
  fi
  if [[ ! -f "${VIDEO}" ]]; then
    echo "input video not found: ${VIDEO}" >&2
    exit 1
  fi
fi

BUILD_ARGS=(
  --dataset-id "${DATASET}"
  --profile "${PROFILE}"
  --gpu "${GPU}"
)
if [[ "${SKIP_RUN}" -eq 1 ]]; then
  BUILD_ARGS+=(--skip-run)
else
  BUILD_ARGS+=(
    --video "${VIDEO}"
    --vggt-model "${VGGT_MODEL}"
  )
  if [[ -n "${KEYFRAME_STRIDE}" ]]; then
    BUILD_ARGS+=(--keyframe-stride "${KEYFRAME_STRIDE}")
  fi
fi

echo "=== 1/2  Modal pipeline (upload, infer, download, stage) ==="
echo "profile=${PROFILE}  gpu=${GPU}  dataset=${DATASET}"
if [[ "${SKIP_RUN}" -eq 0 ]]; then
  echo "video=${VIDEO}"
fi
echo

nlq_python "${SCRIPT_DIR}/build_memory.py" "${BUILD_ARGS[@]}"

echo
echo "=== 2/2  Local NLQ on staged outputs ==="
echo "question=${ASK}"
echo

nlq_python "${SCRIPT_DIR}/smoke_test.py" \
  --transport local \
  --dataset "${DATASET}" \
  --ask "${ASK}" \
  "${NO_LLM[@]}"
