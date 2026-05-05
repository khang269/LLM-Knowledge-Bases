import re
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from datetime import datetime
import json

from ..config import WikiConfig
from ..models import SingleArticle, WikiArticleRecord, CompileResult
from ..llm import LLMClient
from ..state import StateDB
from ..storage import parse_note, write_note, atomic_write, content_hash, sanitize_filename, sanitize_tags, extract_wikilinks

_WRITE_SYSTEM = (
    "You are a wiki editor. Write a single wiki article from the provided source material. "
    "Be accurate, cite sources via [[wikilinks]] in body text, use ## section headings, "
    "write in evergreen style. Put [[wikilinks]] inline in prose — do not save them for later."
)

_STUB_WRITE_SYSTEM = (
    "You are a wiki editor. Write a brief stub article for a wiki concept that was referenced "
    "by other articles but has no source material yet. Keep it under 150 words. Be factual. "
)

def _gather_sources(source_paths: List[str], config: WikiConfig) -> Tuple[str, List[str]]:
    parts = []
    resolved = []
    for sp in source_paths:
        p = config.root_path / sp
        if not p.exists():
            continue
        try:
            _, body = parse_note(p)
            parts.append(f"## Source: {p.name}\n{body}")
            resolved.append(sp)
        except Exception as e:
            print(f"Could not read {sp}: {e}")
    return "\n\n---\n\n".join(parts), resolved

def _inject_body_sections(body: str, source_paths: List[str], config: WikiConfig) -> str:
    body = re.sub(r"\n## Sources\b.*", "", body, flags=re.DOTALL).rstrip()
    body = re.sub(r"\n## See Also\b.*", "", body, flags=re.DOTALL).rstrip()

    source_lines = []
    for sp in source_paths:
        p = config.root_path / sp
        src_title = p.stem.replace("-", " ").title() if p.exists() else Path(sp).stem.replace("-", " ").title()
        safe_src = sanitize_filename(src_title)
        link = f"[[{safe_src}|{src_title}]]" if safe_src != src_title else f"[[{src_title}]]"
        source_lines.append(f"- {link}")

    linked = sorted(set(extract_wikilinks(body)))
    see_also_lines = [f"- [[{t}]]" for t in linked if t]

    sections = "\n\n## Sources\n" + "\n".join(source_lines) if source_lines else ""
    if see_also_lines:
        sections += "\n\n## See Also\n" + "\n".join(see_also_lines)
    return body + sections

def compile_concepts(config: WikiConfig, client: LLMClient, db: StateDB, force: bool = False) -> List[Path]:
    concept_names = db.concepts_needing_compile()
    if not concept_names:
        print("No concepts needing compile")
        return []

    print(f"Compiling {len(concept_names)} concept(s)")
    draft_paths = []

    for name in concept_names:
        source_paths = db.get_sources_for_concept(name)
        is_stub = db.has_stub(name)

        if not source_paths and not is_stub:
            continue

        safe_name = sanitize_filename(name)
        wiki_path = config.wiki_path / f"{safe_name}.md"

        if wiki_path.exists():
            try:
                _, existing_body = parse_note(wiki_path)
                if not force:
                    try:
                        art_rec = db.get_article(str(wiki_path.relative_to(config.root_path)))
                    except ValueError:
                        art_rec = db.get_article(str(wiki_path.name))
                    if art_rec and art_rec.content_hash != content_hash(existing_body):
                        print(f"Skipping '{name}' — manually edited (use force to override)")
                        continue
            except Exception:
                pass

        if is_stub and not source_paths:
            prompt = f'Write a brief stub wiki article for the concept: "{name}"\nKeep it under 150 words.'
            try:
                result = client.generate_structured(prompt, SingleArticle, _STUB_WRITE_SYSTEM)
                db.delete_stub(name)
            except Exception as e:
                print(f"Failed to write stub '{name}': {e}")
                continue
        else:
            sources_text, resolved_paths = _gather_sources(source_paths, config)
            if not resolved_paths:
                print(f"No readable sources for '{name}', skipping")
                continue

            rejections = db.get_rejections(name, limit=3)
            rej_text = "\n\nPREVIOUS REJECTIONS:\n" + "\n".join(r["feedback"] for r in rejections) if rejections else ""

            prompt = (
                f'Write the wiki article: "{name}"\n'
                f"IMPORTANT: Keep the content under 800 words.\n"
                f"Do NOT use inline hashtags (#tag) in the content body — use [[wikilinks]] only.\n"
                f"If the sources reveal non-obvious relationships between 2+ existing concepts, include ConnectionArticles in your output.\n"
                f"SOURCE MATERIAL:\n{sources_text}{rej_text}"
            )
            try:
                result = client.generate_structured(prompt, CompileResult, _WRITE_SYSTEM)
                for sp in resolved_paths:
                    db.mark_raw_status(sp, "compiled")
            except Exception as e:
                print(f"Failed to write '{name}': {e}")
                continue

        draft_path = config.drafts_dir / f"{safe_name}.md"
        
        if is_stub and not source_paths:
            main_article = result
        else:
            main_article = result.article
            
        body = _inject_body_sections(main_article.content, source_paths, config)
        
        meta = {
            "title": main_article.title,
            "tags": sanitize_tags(main_article.tags),
            "status": "draft",
        }
        write_note(draft_path, meta, body)
        
        try:
            draft_rel = str(draft_path.relative_to(config.root_path))
        except ValueError:
            draft_rel = str(draft_path.name)
            
        db.upsert_article(WikiArticleRecord(
            path=draft_rel,
            title=main_article.title,
            sources=source_paths,
            content_hash=content_hash(body),
            is_draft=True
        ))
        draft_paths.append(draft_path)
        print(f"Draft written: {draft_path.name}")
        
        if not is_stub and source_paths and hasattr(result, 'connections'):
            for conn in result.connections:
                conn_safe = sanitize_filename(conn.title)
                conn_draft_path = config.drafts_dir / f"{conn_safe}.md"
                conn_meta = {
                    "title": conn.title,
                    "connects": conn.connects,
                    "sources": source_paths,
                    "status": "draft",
                    "tags": ["connection"]
                }
                # No extra body injection for connections, they are self-contained
                write_note(conn_draft_path, conn_meta, conn.content)
                
                try:
                    conn_draft_rel = str(conn_draft_path.relative_to(config.root_path))
                except ValueError:
                    conn_draft_rel = str(conn_draft_path.name)
                    
                db.upsert_article(WikiArticleRecord(
                    path=conn_draft_rel,
                    title=conn.title,
                    sources=source_paths,
                    content_hash=content_hash(conn.content),
                    is_draft=True
                ))
                draft_paths.append(conn_draft_path)
                print(f"Connection Draft written: {conn_draft_path.name}")

    return draft_paths

def approve_drafts(config: WikiConfig, db: StateDB, paths: Optional[List[Path]] = None) -> List[Path]:
    if paths is None:
        paths = list(config.drafts_dir.rglob("*.md")) if config.drafts_dir.exists() else []

    published = []
    for draft_path in paths:
        if not draft_path.exists():
            continue

        meta, body = parse_note(draft_path)
        
        is_connection = "connection" in meta.get("tags", [])
        is_source = "source" in meta.get("tags", [])
        
        if is_connection:
            target = config.connections_dir / draft_path.name
        elif is_source:
            target = config.sources_dir / draft_path.name
        else:
            target = config.wiki_path / draft_path.name
            
        target.parent.mkdir(parents=True, exist_ok=True)

        meta["status"] = "published"
        meta["updated"] = datetime.now().strftime("%Y-%m-%d")
        
        write_note(target, meta, body)
        draft_path.unlink()

        try:
            draft_rel = str(draft_path.relative_to(config.root_path))
            target_rel = str(target.relative_to(config.root_path))
        except ValueError:
            draft_rel = str(draft_path.name)
            target_rel = str(target.name)

        db.publish_article(draft_rel, target_rel)
        art = db.get_article(target_rel)
        if art:
            db.upsert_article(WikiArticleRecord(
                path=target_rel,
                title=art.title,
                sources=art.sources,
                content_hash=content_hash(body),
                is_draft=False,
                created_at=art.created_at
            ))
            db.approve_article(target_rel)

        published.append(target)
        print(f"Published: {target.name}")

    return published

def reject_draft(draft_path: Path, config: WikiConfig, db: StateDB, feedback: str = ""):
    title = draft_path.stem
    draft_body = ""
    if draft_path.exists():
        try:
            meta, draft_body = parse_note(draft_path)
            title = meta.get("title", draft_path.stem)
        except Exception:
            pass

    try:
        draft_rel = str(draft_path.relative_to(config.root_path))
    except ValueError:
        draft_rel = str(draft_path.name)
        
    db.delete_article(draft_rel)
    if draft_path.exists():
        draft_path.unlink()

    if feedback:
        db.add_rejection(title, feedback, body=draft_body)
        print(f"Draft rejected with feedback: {feedback}")
