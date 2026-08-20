#!/usr/bin/env bash
set -euo pipefail

PORT_VALUE="${PORT:-8501}"
exec streamlit run streamlit_app.py --server.port "$PORT_VALUE" --server.address 0.0.0.0
