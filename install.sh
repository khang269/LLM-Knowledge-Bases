#!/bin/bash
set -e
echo "Installing LLM Knowledge Base globally..."
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed."
    exit 1
fi
if ! command -v pipx &> /dev/null; then
    echo "Installing pipx..."
    python3 -m pip install --user pipx
    python3 -m pipx ensurepath
fi
echo "Installing llm-wiki..."
python3 -m pipx install git+https://github.com/khang269/LLM-Knowledge-Bases.git --force --pip-args="--default-timeout=1000"
python3 -m pipx ensurepath
echo "Installation complete! Restart your terminal or source your profile to use the 'llm-wiki' command."
