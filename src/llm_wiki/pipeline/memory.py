from datetime import datetime, timedelta, timezone
from pathlib import Path
from ..config import WikiConfig
from ..llm import LLMClient

_FLUSH_SYSTEM = """Review the conversation context below and respond with a concise summary
of important items that should be preserved in the daily log.
Do NOT use any tools — just return plain text.

Format your response as a structured daily log entry with these sections:

**Context:** [One line about what the user was working on]

**Key Exchanges:**
- [Important Q&A or discussions]

**Decisions Made:**
- [Any decisions with rationale]

**Lessons Learned:**
- [Gotchas, patterns, or insights discovered]

**Action Items:**
- [Follow-ups or TODOs mentioned]

Skip anything that is:
- Routine tool calls or file reads
- Content that's trivial or obvious
- Trivial back-and-forth or clarification exchanges

Only include sections that have actual content. If nothing is worth saving,
respond with exactly: FLUSH_OK
"""

def extract_conversation(context: str, client: LLMClient) -> str:
    """Extract important knowledge from raw conversation context."""
    prompt = f"## Conversation Context\n\n{context}"
    try:
        response = client.generate_text(prompt=prompt, system_instruction=_FLUSH_SYSTEM)
        return response.strip()
    except Exception as e:
        return f"FLUSH_ERROR: {e}"

def append_to_daily_log(content: str, config: WikiConfig, section: str = "Session") -> Path:
    """Append memory flush content to today's daily log."""
    today = datetime.now().strftime('%Y-%m-%d')
    log_path = config.daily_dir / f"{today}.md"

    if not log_path.exists():
        config.daily_dir.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"# Daily Log: {today}\n\n## Sessions\n\n## Memory Maintenance\n\n",
            encoding="utf-8",
        )

    time_str = datetime.now().strftime("%H:%M")
    entry = f"### {section} ({time_str})\n\n{content}\n\n"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)
        
    return log_path

def get_session_context(config: WikiConfig, max_chars: int = 20_000) -> str:
    """Assemble index and recent daily logs to inject into session context."""
    parts = []
    
    # Date
    today_dt = datetime.now()
    parts.append(f"## Today\n{today_dt.strftime('%A, %B %d, %Y')}")
    
    # Index
    if config.index_file.exists():
        parts.append(f"## Knowledge Base Index\n\n{config.index_file.read_text(encoding='utf-8')}")
    else:
        parts.append("## Knowledge Base Index\n\n(empty - no articles compiled yet)")
        
    # Recent Log
    recent_log = "(no recent daily log)"
    for offset in range(2):
        date_str = (today_dt - timedelta(days=offset)).strftime('%Y-%m-%d')
        log_path = config.daily_dir / f"{date_str}.md"
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8").splitlines()
            recent = lines[-30:] if len(lines) > 30 else lines
            recent_log = "\n".join(recent)
            break
            
    parts.append(f"## Recent Daily Log\n\n{recent_log}")
    
    context = "\n\n---\n\n".join(parts)
    if len(context) > max_chars:
        context = context[:max_chars] + "\n\n...(truncated)"
        
    return context
