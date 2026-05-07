import os
import subprocess
from pathlib import Path
import shutil
import pytest

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
TESTS_DIR = BASE_DIR / "tests"
KB_DIR = TESTS_DIR / "test-restructure-kb"
PYTHON_EXE = SRC_DIR / "venv" / "Scripts" / "python.exe"

@pytest.fixture(scope="module", autouse=True)
def setup_teardown():
    if KB_DIR.exists():
        shutil.rmtree(KB_DIR)
    yield
    # Keep it for manual inspection if needed, or clean up
    # shutil.rmtree(KB_DIR)

def run_cli(*args):
    cmd = [str(PYTHON_EXE), "-m", "llm_wiki.cli", "--dir", str(KB_DIR)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    print(f"STDOUT: {result.stdout}")
    print(f"STDERR: {result.stderr}")
    return result

def test_01_init():
    res = run_cli("init")
    assert res.returncode == 0
    assert (KB_DIR / "raw" / "daily").exists()
    assert not (KB_DIR / "daily").exists()

def test_02_default_import_to_daily():
    # Create a dummy file to import
    dummy_file = KB_DIR / "dummy.md"
    dummy_file.write_text("# Dummy Content\nThis is a test.", encoding="utf-8")
    
    # Import without --dest
    res = run_cli("import", str(dummy_file))
    assert res.returncode == 0
    
    # Verify it went to raw/daily
    daily_files = list((KB_DIR / "raw" / "daily").rglob("dummy.md"))
    assert len(daily_files) == 1
    assert "raw/daily" in str(daily_files[0]).replace("\\", "/")

def test_03_duplicate_detection():
    dummy_file = KB_DIR / "dummy_dup.md"
    dummy_file.write_text("# Duplicate Content", encoding="utf-8")
    
    # First ingest
    run_cli("import", str(dummy_file))
    run_cli("ingest")
    
    # Import same content again (different filename)
    dummy_file_2 = KB_DIR / "dummy_dup_2.md"
    dummy_file_2.write_text("# Duplicate Content", encoding="utf-8")
    run_cli("import", str(dummy_file_2))
    
    res = run_cli("ingest")
    assert "Skipping dummy_dup_2.md: Content matches existing record" in res.stdout

def test_04_concept_reuse_prompt():
    # This is a bit hard to verify automatically without mocking the LLM, 
    # but we checked the code edit. 
    # We'll just verify a build runs smoothly with the new structure.
    res = run_cli("build")
    assert res.returncode == 0
    assert (KB_DIR / "wiki" / "sources").exists()
    assert (KB_DIR / "wiki" / "concepts").exists()
