import difflib
from pathlib import Path
from typing import Set, Dict, List

from ..config import WikiConfig
from ..models import LintIssue, LintResult
from ..state import StateDB
from ..storage import parse_note, extract_wikilinks, content_hash

_REQUIRED_FIELDS = {"title", "status", "tags"}
_SYSTEM_STEMS = {"index", "log"}

def run_lint(config: WikiConfig, db: StateDB) -> LintResult:
    issues: List[LintIssue] = []

    title_index: Dict[str, Path] = {}
    inbound_index: Dict[str, Set[str]] = {}

    all_pages = []
    if config.wiki_path.exists():
        for md in sorted(config.wiki_path.rglob("*.md")):
            if ".drafts" in md.parts:
                continue
            all_pages.append(md)
            
            title_index[md.stem.lower()] = md
            try:
                meta, body = parse_note(md)
                title = meta.get("title", "")
                if title:
                    title_index[title.lower()] = md
                
                for link in extract_wikilinks(body):
                    inbound_index.setdefault(link.lower(), set()).add(md.stem)
            except Exception:
                pass

    db_articles = {a.path: a for a in db.list_articles() if not a.is_draft}
    known_keys = list(title_index.keys())

    for page in all_pages:
        if page.stem.lower() in _SYSTEM_STEMS and page.parent == config.wiki_path:
            continue

        try:
            rel_path = str(page.relative_to(config.root_path))
        except ValueError:
            rel_path = str(page.name)

        try:
            meta, body = parse_note(page)
        except Exception as exc:
            issues.append(LintIssue(path=rel_path, issue_type="parse_error", description=str(exc), suggestion="Fix syntax"))
            continue

        title = meta.get("title", page.stem)

        missing = _REQUIRED_FIELDS - set(meta.keys())
        if missing:
            issues.append(LintIssue(
                path=rel_path,
                issue_type="missing_frontmatter",
                description=f"Missing fields: {', '.join(missing)}",
                suggestion="Add required YAML frontmatter.",
                auto_fixable=True
            ))

        db_rec = db_articles.get(rel_path)
        if db_rec and content_hash(body) != db_rec.content_hash:
            issues.append(LintIssue(
                path=rel_path,
                issue_type="stale",
                description="File modified manually since last compile.",
                suggestion="Run compile force or keep edits."
            ))

        seen_broken = set()
        for link in extract_wikilinks(body):
            if link.lower() in title_index or link.lower() in seen_broken:
                continue
            seen_broken.add(link.lower())
            
            # Fuzzy match suggestion
            matches = difflib.get_close_matches(link.lower(), known_keys, n=1, cutoff=0.6)
            sugg = f"Create a page for '{link}' or remove link."
            if matches:
                correct_node = title_index[matches[0]].stem
                sugg = f"Did you mean [[{correct_node}]]?"

            issues.append(LintIssue(
                path=rel_path,
                issue_type="broken_link",
                description=f"[[{link}]] has no matching wiki page.",
                suggestion=sugg
            ))

        linked_by = inbound_index.get(title.lower(), set()) | inbound_index.get(page.stem.lower(), set())
        linked_by -= {page.stem, "index", "log"}
        if not linked_by and "sources" not in page.parts:
            issues.append(LintIssue(
                path=rel_path,
                issue_type="orphan",
                description="No other wiki page links to this page.",
                suggestion="Reference this concept from related pages."
            ))

    total = max(len(all_pages), 1)
    pages_with_issues = len({iss.path for iss in issues})
    score = round(100.0 * (1 - pages_with_issues / total), 1)

    if not issues:
        summary = f"Wiki healthy. {len(all_pages)} pages checked, no issues."
    else:
        summary = f"{len(issues)} issue(s) across {pages_with_issues} files."

    return LintResult(issues=issues, health_score=score, summary=summary)

def check_contradictions(config: WikiConfig, client) -> List[LintIssue]:
    """Use LLM to detect contradictions across all articles in the wiki."""
    wiki_content = ""
    for md in config.wiki_path.rglob("*.md"):
        if ".drafts" in md.parts:
            continue
        try:
            name = md.name
            content = md.read_text(encoding='utf-8')
            wiki_content += f"--- {name} ---\n{content}\n\n"
        except Exception:
            pass

    prompt = f"""Review this knowledge base for contradictions, inconsistencies, or
conflicting claims across articles.

## Knowledge Base

{wiki_content}

## Instructions

Look for:
- Direct contradictions (article A says X, article B says not-X)
- Inconsistent recommendations (different articles recommend conflicting approaches)
- Outdated information that conflicts with newer entries

Note: `index.md` is an auto-generated table of contents, and `log.md` is a system operation log. Do not treat them as factual knowledge, but DO evaluate them for structural inconsistencies (e.g., if index.md links to a file that doesn't exist, or if the summaries in the index contradict the actual file contents).

For each issue found, output EXACTLY one line in this format:
CONTRADICTION: [file1] vs [file2] - description of the conflict
INCONSISTENCY: [file] - description of the inconsistency

If no issues found, output exactly: NO_ISSUES

Do NOT output anything else - no preamble, no explanation, just the formatted lines."""

    issues = []
    try:
        response = client.generate_text(prompt=prompt, system_instruction="You are a knowledge base linter.")
        if "NO_ISSUES" not in response:
            for line in response.strip().split("\n"):
                line = line.strip()
                if line.startswith("CONTRADICTION:") or line.startswith("INCONSISTENCY:"):
                    issues.append(LintIssue(
                        path="(cross-article)",
                        issue_type="contradiction",
                        description=line,
                        suggestion="Resolve the conflicting claims across the files."
                    ))
    except Exception as e:
        issues.append(LintIssue(
            path="(system)",
            issue_type="contradiction_check_failed",
            description=str(e),
            suggestion="Check LLM connection."
        ))

    return issues
