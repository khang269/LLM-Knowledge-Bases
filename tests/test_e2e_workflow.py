import os
import subprocess
from pathlib import Path
import shutil
import pytest

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
TESTS_DIR = BASE_DIR / "tests"
KB_DIR = TESTS_DIR / "test-kb"
SAMPLE_MDS_DIR = BASE_DIR / "sample-mds"
MAIN_PY = SRC_DIR / "main.py"
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
    cmd = [str(PYTHON_EXE), str(MAIN_PY), "--dir", str(KB_DIR)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    print(f"COMMAND: {' '.join(cmd)}")
    print(f"STDOUT: {result.stdout}")
    print(f"STDERR: {result.stderr}")
    return result

def test_01_init():
    res = run_cli("init")
    assert res.returncode == 0
    assert KB_DIR.exists()
    assert (KB_DIR / "raw").exists()
    assert (KB_DIR / "wiki").exists()
    assert (KB_DIR / "wiki" / "index.md").exists()
    assert (KB_DIR / "wiki" / "log.md").exists()

def test_02_ingest_all():
    # Copy all sample files to raw directory
    for sample_file in SAMPLE_MDS_DIR.glob("*.md"):
        raw_file = KB_DIR / "raw" / sample_file.name
        shutil.copy(sample_file, raw_file)

    # Ingest all files
    res = run_cli("ingest")
    assert res.returncode == 0
    assert "Ingesting all raw notes..." in res.stdout

    # Check state DB and index
    db_file = KB_DIR / "_meta" / "state.db"
    assert db_file.exists()
    index_file = KB_DIR / "wiki" / "index.md"
    assert index_file.exists()

def test_03_lint():
    res = run_cli("lint")
    assert res.returncode == 0
    assert "Health Score:" in res.stdout

def test_04_edit_and_reingest():
    raw_file = KB_DIR / "raw" / "sale-coach.md"
    
    # Read original content
    content = raw_file.read_text(encoding='utf-8')
    
    # Make a change
    new_content = content + "\n\nThis is a test edit to check changes."
    raw_file.write_text(new_content, encoding='utf-8')
    
    # Reingest specifically the changed file with force
    res = run_cli("ingest", str(raw_file), "--force")
    assert res.returncode == 0
    assert "Ingested:" in res.stdout

    # Compile drafts
    res = run_cli("compile")
    assert res.returncode == 0
    
    # Check if drafts were created
    drafts_dir = KB_DIR / "wiki" / ".drafts"
    assert drafts_dir.exists()
    drafts = list(drafts_dir.glob("*.md"))
    assert len(drafts) > 0

def test_05_query():
    res = run_cli("query", "What is the role of an AI engineer?")
    assert res.returncode == 0
    assert "--- Answer ---" in res.stdout
