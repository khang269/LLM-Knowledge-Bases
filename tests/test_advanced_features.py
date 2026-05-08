import os
import subprocess
from pathlib import Path
import shutil
import pytest
from datetime import datetime

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
TESTS_DIR = BASE_DIR / "tests"
KB_DIR = TESTS_DIR / "test-adv-kb"
PYTHON_EXE = SRC_DIR / "venv" / "Scripts" / "python.exe"

@pytest.fixture(scope="session", autouse=True)
def setup_teardown():
    # Setup: Clean up test KB if it exists
    if KB_DIR.exists():
        shutil.rmtree(KB_DIR)
    yield
    pass

def run_cli(*args):
    """Helper to run the CLI."""
    cmd = [str(PYTHON_EXE), "-m", "llm_wiki.cli", "--dir", str(KB_DIR), "--provider", "google"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    print(f"COMMAND: {' '.join(cmd)}")
    print(f"STDOUT: {result.stdout}")
    print(f"STDERR: {result.stderr}")
    return result

def test_01_init():
    res = run_cli("init")
    assert res.returncode == 0
    assert KB_DIR.exists()
    assert (KB_DIR / "raw" / "daily").exists()
    assert (KB_DIR / "wiki" / "qa").exists()

def test_02_flush_memory():
    # Create a dummy transcript
    transcript_path = KB_DIR / "dummy_transcript.txt"
    transcript_path.write_text("User: Should we use Postgres or MySQL?\nAssistant: Let's use Postgres for its JSONB support.", encoding="utf-8")

    res = run_cli("flush", str(transcript_path))
    assert res.returncode == 0
    assert "Memory flush saved to daily log" in res.stdout or "Result" in res.stdout

    # Check if daily log was created
    today = datetime.now().strftime('%Y-%m-%d')
    daily_log = KB_DIR / "raw" / "daily" / f"{today}.md"
    assert daily_log.exists()
    
    content = daily_log.read_text(encoding="utf-8")
    assert "Postgres" in content

def test_03_session_context():
    res = run_cli("session-context")
    assert res.returncode == 0
    assert "## Knowledge Base Index" in res.stdout
    assert "## Recent Daily Log" in res.stdout
    assert "Postgres" in res.stdout  # Since the flush test added this

def test_04_query_file_back():
    question = "What database should we use?"
    res = run_cli("query", question, "--file-back")
    assert res.returncode == 0
    assert "Answer filed successfully to qa directory." in res.stdout

    # Check qa directory for the file
    qa_dir = KB_DIR / "wiki" / "qa"
    qa_files = list(qa_dir.glob("*.md"))
    assert len(qa_files) > 0
    
    # Check if the index got updated with the Q&A
    index_file = KB_DIR / "wiki" / "index.md"
    index_content = index_file.read_text(encoding="utf-8")
    assert "## Q&A" in index_content
    assert "What database should we use" in index_content

def test_05_lint_llm():
    # Run lint with --llm flag
    res = run_cli("lint", "--llm")
    assert res.returncode == 0
    assert "Running health check (lint) with LLM" in res.stdout
    assert "Health Score:" in res.stdout
