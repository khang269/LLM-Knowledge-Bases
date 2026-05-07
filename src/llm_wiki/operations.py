from datetime import datetime
from pathlib import Path
from typing import Optional, List

from .config import WikiConfig
from .state import StateDB
from .llm import LLMClient
from .storage import ensure_directories, write_note, sanitize_filename
from .pipeline import ingest, compile, lint, memory, importer
from .indexer import generate_index, append_log

class WikiManager:
    def __init__(self, config: WikiConfig, llm: LLMClient):
        self.config = config
        self.llm = llm
        ensure_directories(self.config)
        self.db = StateDB(self.config.db_path)

    def initialize(self):
        """Initialize the knowledge base structure and base files."""
        ensure_directories(self.config)
        generate_index(self.config, self.db)
        append_log(self.config, "Knowledge Base initialized")

    def import_document(self, source: str, dest: str, subfolder: Optional[str] = None) -> Path:
        """Fetch a document or URL via MarkItDown and save to the knowledge base."""
        out_path = importer.import_source(source, dest, self.config, self.llm, subfolder)
        append_log(self.config, f"Imported {source} via MarkItDown to {out_path.name}")
        return out_path

    def flush_memory(self, context: str) -> str:
        result = memory.extract_conversation(context, self.llm)
        if "FLUSH_OK" not in result and "FLUSH_ERROR" not in result:
            memory.append_to_daily_log(result, self.config)
            generate_index(self.config, self.db)
            append_log(self.config, "Memory flush saved to daily log")
        return result

    def get_session_context(self) -> str:
        return memory.get_session_context(self.config)

    def ingest_note(self, source_path: Path, force: bool = False):
        result = ingest.ingest_note(source_path, self.config, self.llm, self.db, force=force)
        if result:
            append_log(self.config, f"Ingested {source_path.name} to drafts")
        return result

    def ingest_all(self, force: bool = False):
        processed = ingest.ingest_all(self.config, self.llm, self.db, force=force)
        if processed:
            append_log(self.config, f"Batch ingested {len(processed)} notes to drafts")
        return processed

    def build(self, force: bool = False):
        """1-Click Automatic Workflow: Ingest all, compile, and approve automatically."""
        processed = self.ingest_all(force=force)
        drafts = self.compile(force=force)
        published = self.approve()
        return published

    def compile(self, force: bool = False):
        draft_paths = compile.compile_concepts(self.config, self.llm, self.db, force=force)
        if draft_paths:
            append_log(self.config, f"Compiled {len(draft_paths)} drafts")
        return draft_paths

    def approve(self, path: Optional[Path] = None):
        paths_to_approve = [path] if path else None
        published = compile.approve_drafts(self.config, self.db, paths=paths_to_approve)
        if published:
            generate_index(self.config, self.db)
            append_log(self.config, f"Approved {len(published)} drafts")
        return published

    def reject(self, draft_path: Path, feedback: str = ""):
        compile.reject_draft(draft_path, self.config, self.db, feedback=feedback)
        append_log(self.config, f"Rejected draft {draft_path.name}")

    def lint(self, llm_check: bool = False):
        result = lint.run_lint(self.config, self.db)
        
        if llm_check:
            llm_issues = lint.check_contradictions(self.config, self.llm)
            result.issues.extend(llm_issues)
            
            # Recalculate health score with LLM issues
            total_pages = max(len(list(self.config.wiki_path.rglob("*.md"))), 1)
            
            # Base score on real file errors
            actual_issues = [iss for iss in result.issues if iss.path not in ("(cross-article)", "(system)")]
            pages_with_issues = len({iss.path for iss in actual_issues})
            base_score = 100.0 * (1 - pages_with_issues / total_pages)
            
            # Penalty for LLM issues
            llm_penalty = len(llm_issues) * 5.0
            result.health_score = max(0.0, round(base_score - llm_penalty, 1))
            
            total_affected_files = len({iss.path for iss in result.issues})
            if not result.issues:
                result.summary = f"Wiki healthy. {total_pages} pages checked, no issues."
            else:
                result.summary = f"{len(result.issues)} issue(s) across {total_affected_files} files."
                
        append_log(self.config, f"Lint run: {result.health_score}% healthy")
        return result

    def query(self, question: str, file_back: bool = False) -> str:
        """Query the wiki to answer a question based on indexed content using Semantic Graph Traversal."""
        index_content = ""
        if self.config.index_file.exists():
            index_content = self.config.index_file.read_text(encoding='utf-8')
            
        routing_prompt = f"""
        Question: {question}
        
        Current Wiki Index:
        {index_content}
        
        Based on the index, list the exact link targets you need to read to answer this question.
        Use the exact text inside the double brackets [[ ]]. If there is a pipe |, use the part BEFORE the pipe.
        If the question asks about recent events, decisions, or things "we" should do, heavily prioritize reading the Daily Logs.
        Provide them as a comma-separated list. If none, reply "None".
        """
        system_instruction = "You are an AI assistant maintaining a personal knowledge base wiki."
        
        pages_to_read_str = self.llm.generate_text(prompt=routing_prompt, system_instruction=system_instruction)
        print(f"\n[DEBUG] LLM requested entry nodes: {pages_to_read_str}")
        
        context = ""
        consulted = set()
        queue = []
        if pages_to_read_str.strip().lower() != "none":
            import re
            matches = re.findall(r"\[\[(.*?)\]\]", pages_to_read_str)
            if matches:
                nodes = [m.split('|')[0].strip() for m in matches]
            else:
                nodes = [p.strip() for p in pages_to_read_str.split(",")]
            
            queue = [(n, 0) for n in nodes if n]
            
        MAX_DEPTH = self.config.query_max_depth
        MAX_CHARS = self.config.query_max_chars
        current_length = 0
        
        from .storage import parse_note, extract_wikilinks
        
        while queue and current_length < MAX_CHARS:
            target, depth = queue.pop(0)
            if target in consulted:
                continue
                
            resolved_path = None
            target_md = target if target.endswith(".md") else f"{target}.md"
            
            possible_dirs = [
                self.config.concepts_dir, 
                self.config.sources_dir, 
                self.config.connections_dir, 
                self.config.qa_dir,
                self.config.daily_dir,
                self.config.raw_path
            ]
            
            for d in possible_dirs:
                p = d / target_md
                if p.exists() and p.is_file():
                    resolved_path = p
                    break
                    
            if resolved_path:
                consulted.add(target)
                try:
                    meta, body = parse_note(resolved_path)
                    content_block = f"--- {target} ---\n{body}\n\n"
                    
                    if current_length + len(content_block) > MAX_CHARS:
                        break # Stop if adding this would overflow
                        
                    context += content_block
                    current_length += len(content_block)
                    
                    # Follow breadcrumbs: Load raw source if present in frontmatter
                    source_file = meta.get("source_file")
                    if source_file:
                        raw_path = self.config.root_path / source_file
                        if raw_path.exists() and raw_path.is_file():
                            raw_meta, raw_body = parse_note(raw_path)
                            raw_content = f"--- RAW SOURCE: {source_file} ---\n{raw_body}\n\n"
                            
                            # For raw sources, we might accept going slightly over limit to ensure we get the truth
                            if current_length + len(raw_content) <= MAX_CHARS + 10000:
                                context += raw_content
                                current_length += len(raw_content)
                                consulted.add(source_file)
                                
                    # Breadth-First: Add links to queue if within max_depth
                    if depth < MAX_DEPTH:
                        links = extract_wikilinks(body)
                        for link in links:
                            if link not in consulted:
                                queue.append((link, depth + 1))
                                
                except Exception as e:
                    print(f"[DEBUG] Failed to load {resolved_path}: {e}")

        answer_prompt = f"""
        Question: {question}
        
        Context from Semantic Graph Traversal:
        {context}
        
        Synthesize an answer using the provided context. Cite your sources using the filenames.
        """
        answer = self.llm.generate_text(prompt=answer_prompt, system_instruction=system_instruction)
        append_log(self.config, f"Query: {question}")
        
        if file_back:
            safe_name = sanitize_filename(question)[:50]
            qa_path = self.config.qa_dir / f"{safe_name}.md"
            meta = {
                "title": f"Q: {question}",
                "question": question,
                "consulted": list(consulted),
                "filed": datetime.now().strftime("%Y-%m-%d"),
                "status": "published",
                "tags": ["qa"]
            }
            body = f"# Q: {question}\n\n## Answer\n\n{answer}"
            write_note(qa_path, meta, body)
            generate_index(self.config, self.db)
            append_log(self.config, f"Query (filed) | {question}")
            
        return answer
