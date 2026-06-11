#!/usr/bin/env bash
# Render build — resilient pip install (PyPI read timeouts are common on Render builders).
set -euo pipefail
cd "$(dirname "$0")/.."

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-180}"
export PIP_RETRIES="${PIP_RETRIES:-20}"

python -m pip install --upgrade pip setuptools wheel

pip_install() {
  python -m pip install \
    --default-timeout="${PIP_DEFAULT_TIMEOUT}" \
    --retries="${PIP_RETRIES}" \
    --no-cache-dir \
    "$@"
}

# Seed packages that frequently timeout during full resolver passes.
for pkg in tzdata==2025.3 httpcore==1.0.9; do
  pip_install "$pkg"
done

pip_install -r requirements.txt
