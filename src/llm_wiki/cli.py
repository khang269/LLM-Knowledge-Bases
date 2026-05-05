import argparse
from pathlib import Path
import dotenv
import os

from .config import default_config, GLOBAL_ENV_FILE, ensure_global_config
from .llm import LLMClient
from .operations import WikiManager

def set_global_env(key: str, value: str):
    ensure_global_config()
    dotenv.set_key(str(GLOBAL_ENV_FILE), key, value)
    print(f"Successfully set {key} in global configuration ({GLOBAL_ENV_FILE}).")

def main():
    if GLOBAL_ENV_FILE.exists():
        dotenv.load_dotenv(GLOBAL_ENV_FILE)
    dotenv.load_dotenv()
    
    parser = argparse.ArgumentParser(description="LLM Knowledge Base (Wiki) Manager")
    parser.add_argument("--provider", type=str, help="LLM Provider (gemini, openai, anthropic, groq)", default=None)
    parser.add_argument("--model", type=str, help="Model name to use with the selected provider", default=None)
    parser.add_argument("--dir", type=str, help="Root directory for the wiki (default: my-research)", default="my-research")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    subparsers.add_parser("init", help="Initialize a new LLM Knowledge Base in the specified directory")
    
    build_parser = subparsers.add_parser("build", help="1-Click Automatic Workflow: Ingest all, compile concepts, and approve everything automatically.")
    build_parser.add_argument("--force", action="store_true", help="Force ingestion and compilation even if unmodified")
    
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a new raw source into the wiki (or all if none specified)")
    ingest_parser.add_argument("source", type=str, nargs="?", help="Path to the raw source file", default=None)
    ingest_parser.add_argument("--force", action="store_true", help="Force ingestion even if already ingested")
    
    compile_parser = subparsers.add_parser("compile", help="Compile concepts into draft articles")
    compile_parser.add_argument("--force", action="store_true", help="Force compile even if manually edited")
    
    approve_parser = subparsers.add_parser("approve", help="Approve draft(s) and publish to wiki")
    approve_parser.add_argument("draft", type=str, nargs="?", help="Path to specific draft (approves all if omitted)", default=None)
    
    reject_parser = subparsers.add_parser("reject", help="Reject a draft with feedback")
    reject_parser.add_argument("draft", type=str, help="Path to draft to reject")
    reject_parser.add_argument("--feedback", type=str, help="Feedback for rejection", required=True)
    
    query_parser = subparsers.add_parser("query", help="Query the wiki")
    query_parser.add_argument("question", type=str, help="The question to ask")
    query_parser.add_argument("--file-back", action="store_true", help="File the answer back into the knowledge base as a Q&A article")
    
    lint_parser = subparsers.add_parser("lint", help="Perform a health check on the wiki")
    lint_parser.add_argument("--llm", action="store_true", help="Enable LLM contradiction checking")
    
    flush_parser = subparsers.add_parser("flush", help="Extract important knowledge from a conversation transcript and append to daily log")
    flush_parser.add_argument("transcript", type=str, help="Path to the conversation transcript file")

    subparsers.add_parser("session-context", help="Output current wiki index and recent daily log for session context injection")
    
    config_parser = subparsers.add_parser("config", help="Manage global configuration and API keys")
    config_sub = config_parser.add_subparsers(dest="config_command", help="Config commands")
    
    config_set = config_sub.add_parser("set", help="Set a configuration value (provider, model)")
    config_set.add_argument("key", choices=["provider", "model"], help="The key to set")
    config_set.add_argument("value", type=str, help="The value to set")
    
    config_set_key = config_sub.add_parser("set-key", help="Set an API key globally")
    config_set_key.add_argument("provider", choices=["GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY"], help="The API key to set")
    config_set_key.add_argument("value", type=str, help="The API key value")
    
    args = parser.parse_args()
    
    from .config import WikiConfig
    config = WikiConfig(root_path=Path(args.dir).resolve())
    
    llm = LLMClient(provider=args.provider, model=args.model)
    wiki = WikiManager(config, llm)
    
    if args.command == "init":
        wiki.initialize()
        print(f"Initialized LLM Knowledge Base in {config.root_path}")
        
    elif args.command == "build":
        print("Running 1-Click Build Workflow...")
        published = wiki.build(force=args.force)
        if published:
            print(f"\nBuild complete! {len(published)} files updated and published to the live wiki.")
        else:
            print("\nBuild complete! No new updates were needed.")
        
    elif args.command == "ingest":
        if args.source:
            source_path = Path(args.source)
            if not source_path.exists():
                print(f"Error: Source file {source_path} does not exist.")
                return
            print(f"Ingesting {source_path}...")
            wiki.ingest_note(source_path, force=args.force)
        else:
            print("Ingesting all raw notes...")
            wiki.ingest_all(force=args.force)
            
    elif args.command == "compile":
        print("Compiling concepts to drafts...")
        drafts = wiki.compile(force=args.force)
        if not drafts:
            print("No drafts compiled.")
            
    elif args.command == "approve":
        target = Path(args.draft) if args.draft else None
        print(f"Approving draft(s)...")
        published = wiki.approve(target)
        if not published:
            print("No drafts found to approve.")
            
    elif args.command == "reject":
        draft_path = Path(args.draft)
        if not draft_path.exists():
            print(f"Error: Draft {draft_path} does not exist.")
            return
        wiki.reject(draft_path, feedback=args.feedback)
        
    elif args.command == "query":
        print(f"Querying: {args.question}...")
        answer = wiki.query(args.question, file_back=args.file_back)
        print("\n--- Answer ---")
        print(answer)
        if args.file_back:
            print("\nAnswer filed successfully to qa directory.")
            
    elif args.command == "lint":
        print(f"Running health check (lint) {'with LLM ' if args.llm else ''}...")
        report = wiki.lint(llm_check=args.llm)
        print("\n--- Lint Report ---")
        print(f"Health Score: {report.health_score}%")
        print(report.summary)
        if report.issues:
            print("\nIssues:")
            for issue in report.issues:
                print(f"- [{issue.issue_type}] {issue.path}: {issue.description} ({issue.suggestion})")
                
    elif args.command == "flush":
        transcript_path = Path(args.transcript)
        if not transcript_path.exists():
            print(f"Error: Transcript file {transcript_path} does not exist.")
            return
        
        print("Extracting memory from conversation...")
        context = transcript_path.read_text(encoding='utf-8')
        result = wiki.flush_memory(context)
        print("\n--- Flush Result ---")
        print(result)

    elif args.command == "session-context":
        print(wiki.get_session_context())
        
    elif args.command == "config":
        if args.config_command == "set":
            if args.key == "provider":
                set_global_env("LLM_PROVIDER", args.value)
            elif args.key == "model":
                set_global_env("LLM_MODEL", args.value)
        elif args.config_command == "set-key":
            set_global_env(args.provider, args.value)
        else:
            config_parser.print_help()
            
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
