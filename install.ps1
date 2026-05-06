$ErrorActionPreference = "Stop"
Write-Host "Installing LLM Knowledge Base globally..."

if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Error "Python is required but not installed."
    exit 1
}

if (-not (Get-Command "pipx" -ErrorAction SilentlyContinue)) {
    Write-Host "Installing pipx..."
    python -m pip install --user pipx
    python -m pipx ensurepath
}

Write-Host "Installing llm-wiki..."
python -m pipx install git+https://github.com/khang269/LLM-Knowledge-Bases.git --force --pip-args="--default-timeout=1000"
python -m pipx ensurepath

Write-Host "Installation complete! Restart your terminal to use the 'llm-wiki' command."
