#!/usr/bin/env bash
# Stormhold launcher for macOS, Linux and Raspberry Pi.
set -e
cd "$(dirname "$0")"

PY=python3
command -v $PY >/dev/null 2>&1 || PY=python

if ! $PY -c "import pygame" >/dev/null 2>&1; then
  echo "Installing pygame (one time only)..."
  $PY -m pip install --user pygame-ce || $PY -m pip install --user pygame
fi

exec $PY -m stormhold "$@"
