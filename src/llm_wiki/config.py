import os
from pathlib import Path
from pydantic import BaseModel, Field

GLOBAL_CONFIG_DIR = Path.home() / ".llm-wiki"
GLOBAL_ENV_FILE = GLOBAL_CONFIG_DIR / ".env"

def ensure_global_config():
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not GLOBAL_ENV_FILE.exists():
        GLOBAL_ENV_FILE.touch()

class WikiConfig(BaseModel):
    root_path: Path = Field(default_factory=lambda: Path(os.getcwd()) / "my-research")
    
    @property
    def raw_path(self) -> Path:
        return self.root_path / "raw"
        
    @property
    def wiki_path(self) -> Path:
        return self.root_path / "wiki"
        
    @property
    def output_path(self) -> Path:
        return self.root_path / "output"
        
    @property
    def meta_path(self) -> Path:
        return self.root_path / "_meta"
        
    @property
    def index_file(self) -> Path:
        return self.wiki_path / "index.md"  # Moved to wiki per Obsidian structure
        
    @property
    def log_file(self) -> Path:
        return self.wiki_path / "log.md"

    @property
    def drafts_dir(self) -> Path:
        return self.wiki_path / ".drafts"

    @property
    def drafts_sources_dir(self) -> Path:
        return self.drafts_dir / "sources"

    @property
    def drafts_concepts_dir(self) -> Path:
        return self.drafts_dir / "concepts"

    @property
    def drafts_connections_dir(self) -> Path:
        return self.drafts_dir / "connections"

    @property
    def sources_dir(self) -> Path:
        return self.wiki_path / "sources"
        
    @property
    def qa_dir(self) -> Path:
        return self.wiki_path / "qa"
        
    @property
    def concepts_dir(self) -> Path:
        return self.wiki_path / "concepts"
        
    @property
    def connections_dir(self) -> Path:
        return self.wiki_path / "connections"
        
    @property
    def daily_dir(self) -> Path:
        return self.root_path / "daily"
        
    @property
    def db_path(self) -> Path:
        return self.meta_path / "state.db"

default_config = WikiConfig()
