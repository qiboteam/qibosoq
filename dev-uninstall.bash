#!/usr/bin/env bash

PYTHON=/usr/local/share/pynq-venv/bin/python

env_path=$($PYTHON -c "import site; print(site.getsitepackages()[0])")
rm "$env_path/qibosoq.pth"

echo "File qibosoq.pth removed from site-packages"
