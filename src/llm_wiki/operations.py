from datetime import datetime
from pathlib import Path
from typing import Optional, List

from .config import WikiConfig
from .state import StateDB
from .llm import LLMClient
from .storage import ensure_directories, write_note, sanitize_filename
from .pipeline import ingest, compile, lint, memory
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

    def flush_memory(self, context: str) -> str:
        result = memory.extract_conversation(context, self.llm)
        if "FLUSH_OK" not in result and "FLUSH_ERROR" not in result:
            memory.append_to_daily_log(result, self.config)
            append_log(self.config, "Memory flush saved to daily log")
        return result

    def get_session_context(self) -> str:
        return memory.get_session_context(self.config)

    def ingest_note(self, source_path: Path, force: bool = False):
        result = ingest.ingest_note(source_path, self.config, self.llm, self.db, force=force)
        if result:
            generate_index(self.config, self.db)
            append_log(self.config, f"Ingested {source_path.name}")
        return result

    def ingest_all(self, force: bool = False):
        processed = ingest.ingest_all(self.config, self.llm, self.db, force=force)
        if processed:
            generate_index(self.config, self.db)
            append_log(self.config, f"Batch ingested {len(processed)} notes")
        return processed

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
            pages_with_issues = len({iss.path for iss in result.issues})
            result.health_score = round(100.0 * (1 - pages_with_issues / total_pages), 1)
            
            if not result.issues:
                result.summary = f"Wiki healthy. {total_pages} pages checked, no issues."
            else:
                result.summary = f"{len(result.issues)} issue(s) across {pages_with_issues} files."
                
        append_log(self.config, f"Lint run: {result.health_score}% healthy")
        return result

    def query(self, question: str, file_back: bool = False) -> str:
        """Query the wiki to answer a question based on indexed content."""
        index_content = ""
        if self.config.index_file.exists():
            index_content = self.config.index_file.read_text(encoding='utf-8')
            
        routing_prompt = f"""
        Question: {question}
        
        Current Wiki Index:
        {index_content}
        
        Based on the index, list the exact filenames you need to read to answer this question.
        Provide them as a comma-separated list. If none, reply "None".
        """
        system_instruction = "You are an AI assistant maintaining a personal knowledge base wiki."
        
        pages_to_read_str = self.llm.generate_text(prompt=routing_prompt, system_instruction=system_instruction)
        
        context = ""
        consulted = []
        if pages_to_read_str.strip().lower() != "none":
            page_names = [p.strip() for p in pages_to_read_str.split(",")]
            for name in page_names:
                try:
                    paths = list(self.config.wiki_path.rglob(name))
                    if paths:
                        content = paths[0].read_text(encoding='utf-8')
                        context += f"--- {name} ---\n{content}\n\n"
                        consulted.append(name)
                except Exception as e:
                    pass

        answer_prompt = f"""
        Question: {question}
        
        Context from Wiki Pages:
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
                "consulted": consulted,
                "filed": datetime.now().strftime("%Y-%m-%d"),
                "status": "published"
            }
            body = f"# Q: {question}\n\n## Answer\n\n{answer}"
            write_note(qa_path, meta, body)
            generate_index(self.config, self.db)
            append_log(self.config, f"Query (filed) | {question}")
            
        return answer
