# OpenCode LLM Knowledge Base

A Python-based, tool-agnostic Local LLM Knowledge Base and Memory Compiler.

Adapted from Andrej Karpathy's LLM Knowledge Base architecture and the Claude Memory Compiler, this project allows you to seamlessly ingest external documents (articles, papers) and automatically extract knowledge from your AI coding conversations into a permanently queryable, structured markdown wiki.

Instead of relying on fragile RAG (Retrieval-Augmented Generation) with vector databases, this system uses **Index-Guided Retrieval**. It maintains a central `index.md` catalog of all your concepts, allowing the LLM to intelligently select which articles to read before synthesizing an answer.

## Features

- **Platform Integrations:** Natively hooks into AI coding agents like OpenCode to silently capture conversations and provide autonomous file management tools.
- **Multi-Provider Support:** Works with Google (Gemini), OpenAI, Anthropic, and Groq via the `instructor` library.
- **Safe & Structured (No LLM File Editing):** Uses strict Pydantic schemas and a local SQLite database to track the exact state, hashes, and links of every file. The LLM never has raw write access to your filesystem, preventing hallucinated paths or broken markdown.
- **Dual Ingestion:** Ingests raw external notes (`wiki/raw/`) and continuously flushes daily AI conversation transcripts (`wiki/daily/`).
- **Multi-Format Imports:** Uses `microsoft/markitdown` to natively convert PDFs, Word docs, Excel, YouTube transcripts, and raw web URLs directly into Markdown.
- **LLM Vision OCR:** Automatically routes images and diagrams found inside imported PDFs/PPTs through your chosen LLM provider (Gemini/Anthropic/OpenAI) to generate rich Markdown descriptions.
- **Autonomic Synthesis:** Automatically compiles raw sources into atomic Concept articles and detects cross-cutting insights to generate Connection articles.
- **Drafting & Approval System:** New knowledge is generated into a `.drafts/` folder. You review and approve before it officially enters your knowledge base.
- **Compounding Q&A:** Ask complex questions and the system will synthesize an answer, citing sources via `[[wikilinks]]`, and optionally save the answer permanently to a `qa/` folder to make future queries smarter.
- **Advanced Linting:** Fast structural health checks (broken links, orphans, missing YAML) combined with optional LLM-driven contradiction hunting.

## Folder Architecture

The library automatically manages the following Obsidian-compatible structure:

```text
my-research/
├── raw/                 # External source materials (articles, papers, images, repos)
├── daily/               # Chronological AI conversation memory logs
├── wiki/                # The compiled, LLM-managed knowledge base
│   ├── concepts/        # Atomic knowledge articles
│   ├── connections/     # Cross-cutting insights linking 2+ concepts
│   ├── sources/         # Auto-generated summaries of raw inputs
│   ├── qa/              # Filed answers to complex queries
│   ├── index.md         # Master catalog - the core retrieval mechanism
│   ├── log.md           # Append-only chronological build log
│   └── .drafts/         # Articles waiting for your human approval
└── _meta/               
    └── state.db         # SQLite database tracking file hashes and relationships
```

## Platform Integrations

While this repository provides a standalone Python engine, you can fully integrate it into AI coding assistants so that it automatically runs in the background of your projects.

### 🔌 OpenCode Integration
We provide a native TypeScript plugin for OpenCode that automates session extraction and exposes the knowledge base to the AI as native tools.
👉 **[Read the OpenCode SETUP.md Guide](.opencode/SETUP.md)**

*(More platform integrations coming soon!)*

---

## Standalone CLI Installation

We provide two cross-platform installation scripts that will seamlessly install the `llm-wiki` executable globally to your system PATH using `pipx`.

**On Mac / Linux:**
```bash
curl -sL https://raw.githubusercontent.com/khang269/LLM-Knowledge-Bases/main/install.sh | bash
```

**On Windows (PowerShell):**
```powershell
Invoke-WebRequest -Uri https://raw.githubusercontent.com/khang269/LLM-Knowledge-Bases/main/install.ps1 -OutFile install.ps1; .\install.ps1
```

*(Note: These scripts will automatically install Python 3 and pipx if they are missing from your system, and apply a high timeout to handle the large dependencies).*

### Global Configuration (Required)
Once installed globally, you don't need a `.env` file in every single project! You can securely set your API keys and provider preferences globally using the CLI. **You must set a provider and API key before running any workflows:**

```bash
# Set your default provider and model (google, openai, anthropic, or groq)
llm-wiki config set provider google
llm-wiki config set model gemini-2.5-flash

# Set your API keys (These are stored securely in ~/.llm-wiki/.env)
llm-wiki config set-key GOOGLE_API_KEY your_api_key_here
llm-wiki config set-key ANTHROPIC_API_KEY your_api_key_here
```

---

## Usage

Once installed, you can manage your knowledge base directly via the `llm-wiki` CLI command. By default, it operates on a folder named `my-research` in your current directory, but you can target any project folder using the `--dir` flag.

### 1. Initialization
Bootstrap the folder structure and SQLite database for a new project:
```bash
llm-wiki --dir "my-project-kb" init
```

### 2. Import External Documents (PDFs, Web URLs, YouTube)
Download and convert external formats directly into your knowledge base using the integrated `markitdown` pipeline. It supports Vision OCR for images using your configured LLM provider.
```bash
# Convert a local PDF into the raw/papers folder
llm-wiki --dir "my-project-kb" import /path/to/paper.pdf --dest raw --subfolder papers

# Download and convert a YouTube video transcript into the raw/videos folder
llm-wiki --dir "my-project-kb" import "https://www.youtube.com/watch?v=..." --dest raw --subfolder videos

# Download a web article straight into today's daily log (wiki/daily/YYYY-MM-DD/)
llm-wiki --dir "my-project-kb" import "https://example.com/article" --dest daily
```

### 3. 1-Click Automatic Build (Recommended)
If you want to bypass the manual review queue and instantly sync everything, use the `build` command. This will recursively ingest all files, extract their concepts, auto-compile the relationships, and publish them directly to your live wiki.
```bash
llm-wiki --dir "my-project-kb" build
```

### 4. The Staged Workflow (For strict control)
If you prefer to manually review everything before it touches your wiki, you can run the pipeline step-by-step:

**A. Ingest:** Extracts concepts to the database and creates Source Summaries in the `.drafts/` folder.
```bash
llm-wiki --dir "my-project-kb" ingest
```

**B. Compile:** Analyzes the database and writes synthesized Concept and Connection articles into the `.drafts/` folder.
```bash
llm-wiki --dir "my-project-kb" compile
```

**C. Approve & Reject:** Review the generated Markdown files in `wiki/.drafts/`.
```bash
# Publish all drafts to the live wiki
llm-wiki --dir "my-project-kb" approve

# Or reject a draft with feedback for the LLM to learn from next time
llm-wiki --dir "my-project-kb" reject wiki/.drafts/concept_name.md --feedback "Make it more concise."
```

### 5. Memory Flush (Conversation Capture)
Pass a raw conversation transcript from an AI coding agent to extract architectural decisions, action items, and lessons learned. The output is appended chronologically to today's `daily/` log.
```bash
llm-wiki --dir "my-project-kb" flush path/to/transcript.txt
```

### 6. Session Context Injection
Output the master `index.md` catalog alongside the most recent daily log. You can pipe this directly into your AI agent's system prompt so it instantly "remembers" the context of the project.
```bash
llm-wiki --dir "my-project-kb" session-context
```

### 7. Querying & Compounding Knowledge
Ask the knowledge base complex questions. It will read the index, select the relevant articles, and synthesize an answer. Use `--file-back` to permanently save the answer to `wiki/qa/` and update the index.
```bash
llm-wiki --dir "my-project-kb" query "What is our standard authentication strategy?" --file-back
```

### 8. Linting & Health Checks
Run static analysis to find broken links, missing YAML frontmatter, and orphan pages.
```bash
# Fast, free structural checks
llm-wiki --dir "my-project-kb" lint

# Include LLM-driven contradiction hunting (reads the whole wiki to find conflicting claims)
llm-wiki --dir "my-project-kb" lint --llm
```

## Overriding Providers and Models

You can dynamically override the `.env` defaults for a specific task via the CLI:
```bash
llm-wiki --provider anthropic --model claude-3-5-sonnet-latest compile
llm-wiki --provider openai --model gpt-4o query "..."
llm-wiki --provider groq --model llama-3.3-70b-versatile ingest
```

## Testing
To run the automated end-to-end test suite:
```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v -s
```