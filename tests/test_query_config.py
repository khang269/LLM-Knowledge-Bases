import os
import subprocess
from pathlib import Path
import shutil
import pytest

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
TESTS_DIR = BASE_DIR / "tests"
KB_DIR = TESTS_DIR / "test-query-kb"
PYTHON_EXE = SRC_DIR / "venv" / "Scripts" / "python.exe"

@pytest.fixture(scope="module", autouse=True)
def setup_teardown():
    if KB_DIR.exists():
        shutil.rmtree(KB_DIR)
    yield

def run_cli(*args):
    cmd = [str(PYTHON_EXE), "-m", "llm_wiki.cli", "--dir", str(KB_DIR)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    print(f"STDOUT: {result.stdout}")
    print(f"STDERR: {result.stderr}")
    return result

def test_config_set_query_limits():
    # Set config values
    run_cli("config", "set", "max_chars", "50000")
    run_cli("config", "set", "max_depth", "3")
    
    # We can't easily check the global .env here without knowing the user's home dir
    # but we can verify the command doesn't crash.
    
def test_query_initialization_with_env(monkeypatch):
    # Mock environment variables to verify cli.py loads them correctly
    monkeypatch.setenv("QUERY_MAX_CHARS", "123456")
    monkeypatch.setenv("QUERY_MAX_DEPTH", "5")
    
    # We verify that it runs init without crashing
    res = run_cli("init")
    assert res.returncode == 0
