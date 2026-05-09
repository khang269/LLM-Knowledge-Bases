import os
import subprocess
from pathlib import Path
import shutil
import pytest

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
TESTS_DIR = BASE_DIR / "tests"
KB_DIR = TESTS_DIR / "test-incremental-kb"
PYTHON_EXE = SRC_DIR / "venv" / "Scripts" / "python.exe"

@pytest.fixture(scope="session", autouse=True)
def setup_teardown():
    # Setup
    if KB_DIR.exists():
        shutil.rmtree(KB_DIR)
    yield
    # Teardown
    # if KB_DIR.exists():
    #     shutil.rmtree(KB_DIR)

def run_cli(*args):
    cmd = [str(PYTHON_EXE), "-m", "llm_wiki.cli", "--dir", str(KB_DIR), "--provider", "google"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    print(f"\n--- COMMAND: {' '.join(cmd)}")
    print(f"STDOUT:\n{result.stdout}")
    print(f"STDERR:\n{result.stderr}")
    return result

def test_01_init():
    res = run_cli("init")
    assert res.returncode == 0
    assert KB_DIR.exists()

def test_02_first_import_and_build():
    # Create a dummy markdown file
    dummy1_path = KB_DIR / "dummy1.md"
    dummy1_path.write_text("# First Document\nThis document talks about the concept of Machine Learning.", encoding="utf-8")
    
    # Import it (defaults to daily)
    res_import = run_cli("import", str(dummy1_path))
    assert res_import.returncode == 0
    
    # Build it
    res_build = run_cli("build")
    assert res_build.returncode == 0
    
    # Verify outputs
    sources_dir = KB_DIR / "wiki" / "sources"
    concepts_dir = KB_DIR / "wiki" / "concepts"
    
    assert sources_dir.exists()
    assert concepts_dir.exists()
    
    source_files = list(sources_dir.glob("*.md"))
    concept_files = list(concepts_dir.glob("*.md"))
    
    assert len(source_files) == 1
    assert len(concept_files) > 0

def test_03_second_build_does_nothing():
    # Capture the state of the wiki before second build
    sources_dir = KB_DIR / "wiki" / "sources"
    concepts_dir = KB_DIR / "wiki" / "concepts"
    source_files_before = list(sources_dir.glob("*.md"))
    concept_files_before = list(concepts_dir.glob("*.md"))
    
    # Run build again
    res_build = run_cli("build")
    assert res_build.returncode == 0
    
    # Check that it said "No new updates were needed" or similar in stdout
    assert "No new updates were needed" in res_build.stdout or "Compiling 0 concept" in res_build.stdout or "No concepts needing compile" in res_build.stdout
    
    # Ensure no duplicate files were created
    source_files_after = list(sources_dir.glob("*.md"))
    concept_files_after = list(concepts_dir.glob("*.md"))
    
    assert len(source_files_before) == len(source_files_after)
    assert len(concept_files_before) == len(concept_files_after)
    
    # Ensure .drafts is empty
    drafts_files = list((KB_DIR / "wiki" / ".drafts").rglob("*.md"))
    assert len(drafts_files) == 0

def test_04_second_import_and_build_reuses_concepts():
    # Create a second dummy file that mentions the same concept
    dummy2_path = KB_DIR / "dummy2.md"
    dummy2_path.write_text("# Second Document\nThis document also talks about Machine Learning and adds deep learning.", encoding="utf-8")
    
    res_import = run_cli("import", str(dummy2_path))
    assert res_import.returncode == 0
    
    sources_dir = KB_DIR / "wiki" / "sources"
    concepts_dir = KB_DIR / "wiki" / "concepts"
    
    source_files_before = list(sources_dir.glob("*.md"))
    concept_files_before = list(concepts_dir.glob("*.md"))
    
    # Build it
    res_build = run_cli("build")
    assert res_build.returncode == 0
    
    # Verify sources
    source_files_after = list(sources_dir.glob("*.md"))
    assert len(source_files_after) == 2 # dummy1 and dummy2
    
    # Ensure no duplicates like "dummy1 (1).md" or "Machine Learning (1).md"
    for f in source_files_after:
        assert "(1)" not in f.name
        assert "(2)" not in f.name
        
    concept_files_after = list(concepts_dir.glob("*.md"))
    for f in concept_files_after:
        assert "(1)" not in f.name
        assert "(2)" not in f.name
        
    # The number of concepts should have increased (because of "deep learning"), but the old ones should be updated, not duplicated.
    assert len(concept_files_after) >= len(concept_files_before)
    
    # Ensure .drafts is empty
    drafts_files = list((KB_DIR / "wiki" / ".drafts").rglob("*.md"))
    assert len(drafts_files) == 0