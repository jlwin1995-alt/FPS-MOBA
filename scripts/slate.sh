#!/usr/bin/env bash
# One slate, end to end, after the captures are in data/raw:  scripts/slate.sh [YYYY-MM-DD]
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pipeline.selftest
python -m pipeline.build ${1:+--date "$1"}          # projects the board, freezes data/log/board_<date>.psv, rebuilds site/data
node site/test/parity.mjs
