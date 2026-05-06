import os
import re
import uuid
import hashlib
from pathlib import Path
from typing import Tuple, Dict, Any, List
import frontmatter as fm_lib

def sanitize_filename(name: str) -> str:
    """Make string safe for file names."""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = name.strip()
    return name

def sanitize_tag(tag: str) -> str:
    """Obsidian tags cannot contain spaces or special chars."""
    tag = tag.lower().strip()
    tag = re.sub(r'[^a-z0-9_-]', '-', tag)
    tag = re.sub(r'-+', '-', tag)
    return tag.strip('-')

def sanitize_tags(tags: List[str]) -> List[str]:
    return sorted(list(set(filter(None, [sanitize_tag(t) for t in tags]))))

def parse_note(path: Path) -> Tuple[Dict[str, Any], str]:
    """Parse a markdown note returning frontmatter dictionary and body string."""
    try:
        post = fm_lib.load(path)
        return dict(post.metadata), post.content
    except Exception as e:
        print(f"Error parsing note {path}: {e}")
        return {}, path.read_text(encoding='utf-8')

def atomic_write(path: Path, content: str):
    """Write to file atomically using a temporary file in the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_text(content, encoding='utf-8')
        temp_path.replace(path)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise e

def write_note(path: Path, meta: Dict[str, Any], body: str):
    """Write frontmatter and body to markdown file atomically."""
    post = fm_lib.Post(body, **meta)
    atomic_write(path, fm_lib.dumps(post) + "\n")

def extract_wikilinks(body: str) -> List[str]:
    """Extract [[wikilinks]] from a body of text."""
    pattern = re.compile(r"\[\[(.*?)\]\]")
    links = []
    for match in pattern.finditer(body):
        target = match.group(1).split('|')[0]  # Get the target, not the alias
        links.append(target.strip())
    return links

def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
    """Simple character-based chunking."""
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i + chunk_size])
        i += chunk_size - overlap
    return chunks

def content_hash(text: str) -> str:
    """Hash the body of the note (excluding frontmatter) to detect manual edits."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def ensure_directories(config):
    paths = [
        config.raw_path / "images",
        config.raw_path / "articles",
        config.raw_path / "papers",
        config.raw_path / "videos",
        config.raw_path / "repos",
        config.raw_path / "audio",
        config.raw_path / "feeds",
        config.wiki_path / "concepts",
        config.output_path,
        config.meta_path,
        config.drafts_dir,
        config.drafts_sources_dir,
        config.drafts_concepts_dir,
        config.drafts_connections_dir,
        config.sources_dir,
        config.qa_dir,
        config.connections_dir,
        config.daily_dir,
    ]
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)
