import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..config import WikiConfig
from ..models import AnalysisResult, RawNoteRecord
from ..llm import LLMClient
from ..state import StateDB
from ..storage import parse_note, content_hash, sanitize_filename, write_note

log = logging.getLogger(__name__)

_SYSTEM = (
    "You are a knowledge analyst. Read the provided note and extract structured information. "
    "Be concise and accurate. Do not invent information not present in the note. "
    "Detect the primary language of the note and return its ISO 639-1 code in the 'language' field "
    "(e.g. 'en', 'fr', 'de'). Use null if uncertain."
)

def _build_analysis_prompt(body: str, existing_concepts: List[str]) -> str:
    concepts_hint = ", ".join(existing_concepts[:30]) if existing_concepts else "none yet"
    return (
        f"Analyze this note and extract structured metadata.\n\n"
        f"Existing wiki concepts (reuse these names where applicable): {concepts_hint}\n\n"
        f"NOTE CONTENT:\n{body}"
    )

def _normalize_concept_names(raw_names: List[str], db: StateDB) -> List[str]:
    """Case-insensitive match against existing canonical concept names."""
    existing = {n.lower(): n for n in db.list_all_concept_names()}
    seen = set()
    normalized = []
    for name in raw_names:
        name = name.strip()
        if not name: continue
        canonical = existing.get(name.lower(), name)
        if canonical not in seen:
            seen.add(canonical)
            normalized.append(canonical)
    return normalized

def _create_source_summary_page(path: Path, src_meta: dict, result: AnalysisResult, config: WikiConfig) -> Path:
    """Generate wiki/sources/{Title}.md from AnalysisResult."""
    title = src_meta.get("title") or path.stem.replace("-", " ").title()
    safe_name = sanitize_filename(title)
    out_path = config.sources_dir / f"{safe_name}.md"
    
    now = datetime.now().strftime("%Y-%m-%d")
    try:
        rel_raw = str(path.relative_to(config.root_path))
    except ValueError:
        rel_raw = str(path.name)
        
    source_url = src_meta.get("source") or src_meta.get("url") or ""

    concept_lines = "\n".join(f"- [[{c}]]" for c in result.key_concepts[:8] if c.strip())

    out_meta = {
        "title": title,
        "tags": ["source"],
        "status": "published",
        "source_file": rel_raw,
        "quality": result.quality,
        "created": now,
    }
    if source_url:
        out_meta["source_url"] = source_url

    body_parts = [
        f"# {title}", "",
        "## Summary", result.summary, "",
        "## Concepts", concept_lines, "",
        "## Source Info",
        f"- **Quality:** {result.quality}",
        f"- **Raw file:** {rel_raw}",
        f"- **Ingested:** {now}",
    ]
    if source_url:
        body_parts.append(f"- **URL:** {source_url}")

    write_note(out_path, out_meta, "\n".join(body_parts))
    return out_path

def ingest_note(path: Path, config: WikiConfig, client: LLMClient, db: StateDB, force: bool = False) -> Optional[AnalysisResult]:
    """Ingest a single raw note."""
    meta, body = parse_note(path)
    h = content_hash(body)
    
    # Try to get relative path, fallback to just name if it's outside
    try:
        rel_path = str(path.relative_to(config.root_path))
    except ValueError:
        rel_path = str(path.name)

    existing = db.get_raw_by_hash(h)
    if existing and existing.path != rel_path:
        print(f"Duplicate of {existing.path}, skipping {path.name}")
        return None

    record = db.get_raw(rel_path)
    if record and record.status == "ingested" and not force:
        if record.content_hash == h:
            print(f"Already ingested: {path.name}")
            return None
        else:
            print(f"File modified, re-ingesting: {path.name}")

    existing_topics = db.list_all_concept_names()
    prompt = _build_analysis_prompt(body, existing_topics)
    
    try:
        result = client.generate_structured(
            prompt=prompt,
            response_schema=AnalysisResult,
            system_instruction=_SYSTEM
        )
    except Exception as e:
        print(f"Analysis failed for {path.name}: {e}")
        db.upsert_raw(RawNoteRecord(path=rel_path, content_hash=h, status="failed", error=str(e)))
        return None

    # Update state DB
    db.upsert_raw(RawNoteRecord(
        path=rel_path,
        content_hash=h,
        status="ingested",
        summary=result.summary,
        quality=result.quality,
        language=result.language,
        ingested_at=datetime.now(),
    ))

    normalized_concepts = _normalize_concept_names(result.key_concepts[:8], db)
    db.upsert_concepts(rel_path, normalized_concepts)

    # Create source summary
    try:
        _create_source_summary_page(path, meta, result, config)
    except Exception as e:
        print(f"Source summary page failed for {path.name}: {e}")

    print(f"Ingested: {path.name} (quality={result.quality}, concepts={result.key_concepts[:3]})")
    return result

def ingest_all(config: WikiConfig, client: LLMClient, db: StateDB, force: bool = False) -> List[Path]:
    """Ingest all .md files in raw/ and daily/."""
    raw_files = [p for p in config.raw_path.rglob("*.md") if not p.name.startswith(".")]
    daily_files = [p for p in config.daily_dir.rglob("*.md") if not p.name.startswith(".")] if config.daily_dir.exists() else []
    
    all_files = raw_files + daily_files
    processed = []
    for path in sorted(all_files):
        res = ingest_note(path, config, client, db, force=force)
        if res:
            processed.append(path)
    return processed
