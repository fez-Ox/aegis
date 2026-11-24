#!/usr/bin/env bash
# Stop the deployed Aegis gateway. The apps will show NOT LIVE until start_api.sh.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
uv run modal app stop aegis-memory-api --yes
echo "Aegis gateway stopped. Restart with: scripts/start_api.sh"
