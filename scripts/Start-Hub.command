#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo "First follow the Mac environment setup in README.md."
  exit 1
fi
.venv/bin/python -m smt2 gui hub
